# Análisis del Flujo de Onboarding - Problemas Identificados

## 📋 Flujo Actual (Paso a Paso)

### 1. Usuario accede a `/` (page.tsx)

**Pasos:**
1. Verifica autenticación en Supabase (`supabase.auth.getSession()`)
2. Si no está autenticado → redirige a `/login`
3. Si está autenticado → valida usuario en BD local

### 2. Validación del Usuario (`useUserValidation`)

**Pasos:**
1. Obtiene token JWT de Supabase
2. Llama a `/api/v1/auth/user` con el token
3. El backend:
   - Decodifica el JWT (sin verificar firma)
   - Extrae `sub` (Supabase User ID) y `email`
   - Busca usuario en BD local por `external_id` (Supabase User ID)
   - Si no encuentra, busca por `email`
   - Si encuentra por email pero no tiene `external_id`, lo vincula automáticamente
   - Retorna datos del usuario local

4. Si el usuario existe → guarda `user_id` en `localStorage`
5. Llama a `/api/v1/users/{user_id}/workspaces` para verificar si tiene workspaces

**Estados posibles:**
- `isValid: false` → Usuario no existe en BD local → Muestra error "Acceso no autorizado"
- `isValid: true, hasWorkspaces: false` → Usuario existe pero no tiene workspaces
- `isValid: true, hasWorkspaces: true` → Usuario válido con workspaces

### 3. Redirección según Estado

**Si `hasWorkspaces === false`:**
1. Verifica si hay invitaciones pendientes (`getPendingInvitationsByEmail`)
2. Si hay invitaciones → redirige a `/invitations/accept/{token}`
3. Si no hay invitaciones → redirige a `/onboarding`

**Si `hasWorkspaces === true`:**
1. Espera a que se carguen los workspaces
2. Redirige según el rol del usuario

### 4. Aceptar Invitación (`/invitations/accept/[token]`)

**Flujo cuando el usuario NO está autenticado:**
1. Carga detalles de la invitación (`getInvitationByToken`)
2. Muestra formulario de registro/login (Email+Password, Magic Link, Google OAuth)
3. Pre-llena el email con el email de la invitación
4. Después de autenticarse:
   - Llama a `acceptInvitationByToken(token, userId, authToken)`
   - El backend crea el usuario si no existe
   - El backend acepta la invitación y crea la membresía
   - Guarda `user_id` en `localStorage`
   - Llama a `refreshWorkspaces(userId)`
   - Redirige a `/workspace`

**Flujo cuando el usuario YA está autenticado:**
1. Carga detalles de la invitación
2. Verifica que el email del usuario autenticado coincida con el email de la invitación
3. Si coincide → acepta automáticamente (en `useEffect`)
4. Si no coincide → muestra error y botón para cerrar sesión

### 5. Crear Workspace (`/onboarding`)

**Pasos:**
1. Usuario completa formulario
2. Llama a `createWorkspace(request, userId)`
3. Si hay `userId`, llama a `addUserToWorkspace(userId, workspaceId, 'owner')`
4. Llama a `refreshWorkspaces()`
5. Redirige a `/workspace`

---

## 🐛 PROBLEMAS IDENTIFICADOS

### Problema 1: Usuario se crea pero no se persiste correctamente

**Ubicación:** `api/routes/invitations.py` - `accept_invitation_by_token`

**Problema:**
- El usuario se crea en una **sesión separada** (`get_separate_db_session()`)
- Se hace `commit()` en esa sesión separada
- Luego se intenta recuperar el usuario en la **sesión principal** (`session.query(User).filter_by(id=user.id).first()`)
- **PERO**: La sesión principal usa `Depends(get_db)`, que hace commit automático al final
- Si hay un error después de crear el usuario pero antes del commit final, el rollback puede deshacer todo

**Evidencia:**
- Logs muestran: "Usuario 76a0d228-900e-4b15-8fff-1fa3444e8622 no encontrado"
- Consulta directa a BD confirma que el usuario NO existe

**Causa raíz:**
- Múltiples sesiones de BD creando confusión
- El usuario se crea en sesión A, pero se consulta en sesión B
- El commit en sesión A puede no estar visible inmediatamente en sesión B (aislamiento de transacciones)

### Problema 2: `get_db()` hace commit automático

**Ubicación:** `api/dependencies.py` - `get_db()`

**Problema:**
```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()  # ⚠️ Commit automático al final
    except Exception:
        db.rollback()  # ⚠️ Rollback si hay error
        raise
    finally:
        db.close()
```

**Impacto:**
- Si hay un error en `accept_invitation`, el rollback deshace TODO, incluyendo el usuario creado en sesión separada
- Pero espera... el usuario se crea en sesión separada, así que NO debería deshacerse...

**Confusión:**
- El usuario se crea en sesión separada y se commitea
- Pero luego se intenta usar en la sesión principal
- Si la sesión principal hace rollback, NO afecta al usuario (ya está commiteado en otra sesión)
- **PERO**: El problema es que el usuario puede no estar disponible inmediatamente después del commit

### Problema 3: Timing entre creación y consulta

**Problema:**
1. Usuario se crea en sesión separada → `commit()`
2. Se cierra la sesión separada
3. Se intenta recuperar en sesión principal → `session.query(User).filter_by(id=user.id).first()`
4. **Puede no estar disponible inmediatamente** debido a:
   - Aislamiento de transacciones en SQLite
   - Cache de SQLAlchemy
   - El objeto `user` puede estar "desconectado" de la sesión

### Problema 4: `refreshWorkspaces` se llama antes de que el usuario esté disponible

**Ubicación:** `ui/app/invitations/accept/[token]/page.tsx`

**Problema:**
```typescript
const result = await acceptInvitationByToken(token, localUserId || null, authToken)
const finalUserId = result.user_id || localUserId
await refreshWorkspaces(finalUserId || undefined)
```

**Flujo:**
1. Backend acepta invitación y crea usuario
2. Backend retorna `user_id`
3. Frontend llama a `refreshWorkspaces(userId)`
4. Frontend llama a `/api/v1/users/{user_id}/workspaces`
5. **PERO**: El endpoint puede no encontrar el usuario porque:
   - El usuario se creó en sesión separada
   - Puede haber un delay en la propagación
   - O el usuario realmente no se persiste

### Problema 5: Múltiples commits y sesiones

**Complejidad innecesaria:**
- Usuario se crea en sesión separada → commit
- Si necesita vincular con Supabase → otra sesión separada → commit
- Invitación se acepta en sesión principal → commit
- Membresía se crea en sesión principal → commit

**Riesgo:**
- Si falla cualquier paso, puede quedar en estado inconsistente
- Múltiples puntos de fallo

---

## 🔧 SOLUCIONES PROPUESTAS

### Solución 1: Simplificar creación de usuario

**Opción A: Crear usuario en la misma sesión**
- NO usar sesión separada
- Crear usuario directamente en la sesión principal
- Hacer commit solo al final, después de aceptar la invitación
- **Riesgo**: Si falla la aceptación, el usuario queda creado sin membresía

**Opción B: Usar transacciones explícitas**
- Crear usuario en sesión separada
- Hacer commit explícito
- Esperar un momento (o hacer refresh)
- Luego usar en sesión principal
- **Problema**: Aún puede haber timing issues

**Opción C: Usar `session.merge()` en lugar de `session.query()`**
- Después de crear usuario en sesión separada
- En sesión principal, usar `session.merge(user)` en lugar de `session.query()`
- Esto asegura que el objeto esté en la sesión

### Solución 2: Simplificar flujo de aceptación

**Proponer:**
1. Todo en UNA sesión
2. Crear usuario si no existe
3. Aceptar invitación
4. Crear membresía
5. Hacer UN SOLO commit al final

**Ventajas:**
- Más simple
- Menos puntos de fallo
- Transaccional (todo o nada)

**Desventajas:**
- Si falla, se pierde todo (pero eso es lo que queremos, ¿no?)

### Solución 3: Mejorar verificación post-commit

**Después de crear usuario:**
1. Hacer commit
2. Hacer `session.refresh(user)` o `session.expire_all()`
3. Verificar con nueva query
4. Si no está, esperar un momento y reintentar

### Solución 4: Cambiar estrategia de `get_db()`

**Opción A: No hacer commit automático**
- Dejar que cada endpoint haga su propio commit
- Más control, pero más código

**Opción B: Mantener commit automático pero manejar errores mejor**
- Asegurar que operaciones críticas se hagan en sesiones separadas
- O usar `session.flush()` en lugar de `commit()` para operaciones intermedias

---

## 🎯 RECOMENDACIÓN

**Simplificar TODO el flujo:**

1. **Una sola sesión para todo:**
   - Crear usuario (si no existe)
   - Aceptar invitación
   - Crear membresía
   - Un solo commit al final

2. **Si el usuario ya existe:**
   - Buscar por email
   - Si no tiene `external_id`, vincularlo
   - Continuar con aceptación

3. **Manejo de errores:**
   - Si falla cualquier paso, hacer rollback de TODO
   - Retornar error claro al frontend
   - Frontend puede reintentar

4. **Verificación post-commit:**
   - Después del commit, hacer query directa a BD
   - Si no está, retornar error
   - Frontend puede reintentar

---

## 📝 PRÓXIMOS PASOS

1. **Simplificar `accept_invitation_by_token`:**
   - Eliminar sesiones separadas
   - Todo en una sesión
   - Un solo commit al final

2. **Mejorar logging:**
   - Agregar más logs para rastrear el flujo
   - Logs antes y después de cada commit
   - Logs de verificación post-commit

3. **Agregar retry en frontend:**
   - Si `refreshWorkspaces` falla, reintentar después de un delay
   - Mostrar mensaje al usuario

4. **Testing:**
   - Probar flujo completo desde cero
   - Verificar que el usuario se persiste
   - Verificar que la membresía se crea
   - Verificar que los workspaces se cargan
