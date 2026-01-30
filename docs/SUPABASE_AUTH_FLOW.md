# Flujo de Autenticación y Vinculación con Supabase (B2B y B2C)

Este documento explica el flujo completo de autenticación y vinculación de usuarios con Supabase Auth, tanto para **B2B (organizaciones)** como para **B2C (usuarios individuales)**.

## Arquitectura General

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Next.js   │────────▶│ Supabase Auth│────────▶│   OAuth     │
│  Frontend   │         │  (Identity   │         │  Providers  │
│             │         │   Provider)  │         │  (Google)    │
└─────────────┘         └──────────────┘         └─────────────┘
       │                         │
       │ JWT Token               │
       ▼                         │
┌─────────────┐                 │
│   FastAPI   │                 │
│   Backend   │                 │
└─────────────┘                 │
       │                         │
       │ Sync User               │
       ▼                         │
┌─────────────┐                 │
│   SQLite    │◀────────────────┘
│  (SQLAlchemy│   User Data
│   Models)   │
└─────────────┘
```

## Flujo Unificado (B2B y B2C)

El flujo de autenticación es **idéntico** para B2B y B2C. La diferencia está en:
- **Cómo se crean los workspaces** (B2B requiere superadmin, B2C es automático)
- **Los permisos y roles** dentro de cada workspace
- **Los planes de suscripción** (B2B vs B2C)

### Paso 1: Usuario se Autentica en Supabase

El usuario puede autenticarse de varias formas:

#### A. Email + Password
```typescript
// Frontend (Next.js)
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'usuario@example.com',
  password: 'password123'
})
```

#### B. Magic Link / OTP
```typescript
const { data, error } = await supabase.auth.signInWithOtp({
  email: 'usuario@example.com'
})
```

#### C. OAuth (Google, etc.)
```typescript
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${window.location.origin}/auth/callback`
  }
})
```

**Resultado**: Supabase retorna un **JWT** con:
- `sub`: Supabase User ID (UUID)
- `email`: Email del usuario
- `user_metadata`: Metadata del usuario (nombre, avatar, etc.)

### Paso 2: Callback de Autenticación

Cuando el usuario se autentica (especialmente con OAuth o Magic Link), Supabase redirige a:

```
/auth/callback?code=xxx
```

El handler en `ui/app/auth/callback/route.ts`:

1. **Intercambia el código por sesión**:
   ```typescript
   const { data, error } = await supabase.auth.exchangeCodeForSession(code)
   ```

2. **Sincroniza el usuario con el backend**:
   ```typescript
   const syncResponse = await syncUser({
     supabase_user_id: data.user.id,  // El 'sub' del JWT
     email: data.user.email,
     name: metadata.name || data.user.email?.split('@')[0],
     auth_provider: 'supabase',
     metadata: { avatar_url: metadata.avatar_url, ...metadata }
   })
   ```

3. **Redirige al usuario** a `/workspace` o página solicitada

### Paso 3: Sincronización en el Backend

El endpoint `POST /api/v1/auth/sync-user` ejecuta `create_or_update_user_from_supabase()`:

```python
def create_or_update_user_from_supabase(
    session: Session,
    supabase_user_id: str,  # El 'sub' del JWT
    email: str,
    name: str,
    auth_provider: str = "supabase",
    metadata: dict | None = None,
) -> tuple[User, bool]:
```

**Lógica de vinculación**:

1. **Buscar por `external_id`** (Supabase User ID):
   - Si existe → actualizar datos (email, name, metadata)
   - Retornar usuario existente

2. **Si no existe por `external_id`, buscar por `email`**:
   - Si existe → actualizar `external_id` y `auth_provider`
   - Esto vincula un usuario pre-creado con Supabase

3. **Si no existe, crear nuevo usuario**:
   - Generar UUID local
   - Establecer `external_id = supabase_user_id`
   - Establecer `auth_provider = 'supabase'`

**Resultado**: Usuario vinculado en la BD local con:
- `id`: UUID local
- `external_id`: Supabase User ID (sub del JWT)
- `email`: Email del usuario
- `auth_provider`: 'supabase'

### Paso 4: Obtención del User ID Local

El frontend necesita el **User ID local** para hacer requests al backend. El hook `useUserId()`:

1. **Obtiene la sesión de Supabase**:
   ```typescript
   const { data: { session } } = await supabase.auth.getSession()
   ```

2. **Busca `local_user_id` en localStorage**:
   - Si existe → lo usa
   - Si no existe → llama a `/api/v1/auth/user` con el token JWT

3. **El backend valida el token y retorna el usuario local**:
   ```python
   # api/dependencies.py - get_current_user_id()
   response = supabase.auth.get_user(token)
   local_user = get_user_by_external_id(session, response.user.id)
   return local_user.id  # UUID local
   ```

4. **Guarda `local_user_id` en localStorage** para futuras requests

### Paso 5: Requests al Backend

Todas las requests al backend incluyen el token JWT:

```typescript
const response = await fetch('/api/v1/workspaces', {
  headers: {
    'Authorization': `Bearer ${token}`  // JWT de Supabase
  }
})
```

El backend:
1. Valida el token con Supabase
2. Extrae el `sub` (Supabase User ID)
3. Busca el usuario local por `external_id`
4. Retorna el `user_id` local para usar en la lógica de negocio

## Diferencias B2B vs B2C

### B2B (Organizaciones)

**Creación de Workspace**:
- Requiere **superadmin** para crear
- Se crea mediante `POST /api/v1/superadmin/workspaces`
- Se asigna un **plan de suscripción B2B** (trial, starter, professional, enterprise)
- Se crea una **invitación** para el admin de la organización

**Flujo típico**:
1. Superadmin crea workspace B2B
2. Superadmin invita al admin del cliente (email)
3. Admin recibe invitación y se registra en Supabase
4. Admin se autentica → se sincroniza automáticamente
5. Admin acepta invitación → se une al workspace con rol "owner"

**Roles en Workspace**:
- `owner`: Dueño del workspace (todos los permisos)
- `admin`: Administrador (gestión y aprobación)
- `approver`: Aprobador (aprobar/rechazar documentos)
- `creator`: Creador (crear y editar documentos)
- `viewer`: Visualizador (solo lectura)

### B2C (Usuarios Individuales)

**Creación de Workspace**:
- Cualquier usuario autenticado puede crear su propio workspace
- Se crea mediante `POST /api/v1/workspaces` con `workspace_type="user"`
- Se asigna un **plan de suscripción B2C** (free, premium)
- El usuario se asigna automáticamente como "owner"

**Flujo típico**:
1. Usuario se registra en Supabase (email/password, OAuth, Magic Link)
2. Usuario se autentica → se sincroniza automáticamente
3. Usuario crea su workspace personal (opcional, puede ser automático)
4. Usuario puede crear documentos, recetas, etc.

**Roles en Workspace**:
- Generalmente solo `owner` (el mismo usuario)
- Puede invitar a otros usuarios si el plan lo permite

## Ejemplo Completo: B2B

### 1. Superadmin crea workspace

```bash
# Superadmin (sdalto@margaystudio.io) crea workspace para cliente
POST /api/v1/superadmin/workspaces
{
  "name": "Empresa ABC",
  "slug": "empresa-abc",
  "plan_name": "b2b_trial",
  "admin_email": "admin@empresa-abc.com",
  "country": "UY",
  "business_type": "estaciones_servicio",
  "language_style": "es_uy_formal",
  "default_audience": "operativo"
}
```

**Resultado**:
- Workspace creado con `workspace_type="organization"`
- Plan de suscripción "b2b_trial" asignado
- Invitación creada para `admin@empresa-abc.com` con rol "owner"

### 2. Admin del cliente se registra

El admin recibe un email con el link de invitación o se registra directamente:

```typescript
// Frontend: /login
const { data, error } = await supabase.auth.signUp({
  email: 'admin@empresa-abc.com',
  password: 'password123'
})
```

**Resultado en Supabase**:
- Usuario creado en Supabase Auth
- UUID generado: `550e8400-e29b-41d4-a716-446655440000`

### 3. Admin inicia sesión

```typescript
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'admin@empresa-abc.com',
  password: 'password123'
})
```

**Flujo automático**:
1. Supabase retorna JWT con `sub = 550e8400-e29b-41d4-a716-446655440000`
2. Frontend llama a `/api/v1/auth/sync-user`
3. Backend crea usuario local:
   ```python
   User(
     id="local-uuid-123",  # UUID local generado
     email="admin@empresa-abc.com",
     name="Admin",
     external_id="550e8400-e29b-41d4-a716-446655440000",  # Supabase User ID
     auth_provider="supabase"
   )
   ```
4. Frontend guarda `local_user_id` en localStorage

### 4. Admin acepta invitación

```typescript
// Frontend: /invitations/accept?token=xxx
POST /api/v1/workspaces/invitations/{invitation_id}/accept
Headers: { Authorization: `Bearer ${jwt_token}` }
```

**Resultado**:
- Se crea `WorkspaceMembership` con `role_id = owner`
- Admin ahora tiene acceso al workspace

## Ejemplo Completo: B2C

### 1. Usuario se registra

```typescript
// Frontend: /login
const { data, error } = await supabase.auth.signUp({
  email: 'usuario@example.com',
  password: 'password123'
})
```

**Resultado en Supabase**:
- Usuario creado en Supabase Auth
- UUID generado: `660e8400-e29b-41d4-a716-446655440001`

### 2. Usuario inicia sesión

```typescript
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'usuario@example.com',
  password: 'password123'
})
```

**Flujo automático** (igual que B2B):
1. Supabase retorna JWT
2. Frontend sincroniza con backend
3. Usuario local creado/vinculado

### 3. Usuario crea workspace personal

```typescript
// Frontend: /onboarding o automático
POST /api/v1/workspaces
{
  "name": "Mi Workspace",
  "slug": "mi-workspace",
  "workspace_type": "user"
}
Headers: { Authorization: `Bearer ${jwt_token}` }
```

**Resultado**:
- Workspace creado con `workspace_type="user"`
- Plan de suscripción "b2c_free" asignado automáticamente
- Usuario asignado como "owner" del workspace

## Resumen del Flujo de Vinculación

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuario se autentica en Supabase                         │
│    → Supabase retorna JWT con 'sub' (User ID)              │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Frontend llama a /api/v1/auth/sync-user                  │
│    → Envía: supabase_user_id, email, name                   │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend busca/crea usuario local                         │
│    → Si existe por external_id → actualiza                 │
│    → Si existe por email → vincula (set external_id)        │
│    → Si no existe → crea nuevo                              │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Usuario vinculado:                                       │
│    - id: UUID local                                          │
│    - external_id: Supabase User ID (sub del JWT)            │
│    - auth_provider: 'supabase'                               │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Frontend guarda local_user_id en localStorage            │
│    → Usa este ID para todas las requests al backend         │
└─────────────────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Requests al backend incluyen JWT                          │
│    → Backend valida token → busca por external_id           │
│    → Retorna user_id local para lógica de negocio           │
└─────────────────────────────────────────────────────────────┘
```

## Puntos Clave

1. **Vinculación automática**: Cuando un usuario se autentica en Supabase, se sincroniza automáticamente con la BD local
2. **Vinculación por email**: Si un usuario ya existe en la BD local (creado manualmente), se vincula automáticamente cuando se autentica con el mismo email
3. **JWT siempre presente**: Todas las requests al backend incluyen el JWT de Supabase
4. **User ID local**: El backend siempre trabaja con el UUID local, no con el Supabase User ID
5. **B2B vs B2C**: La diferencia está en cómo se crean los workspaces y los permisos, no en el flujo de autenticación

## Troubleshooting

### Usuario no se sincroniza automáticamente

1. Verificar que `/api/v1/auth/sync-user` se llama después del login
2. Verificar que `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` están configurados
3. Revisar logs del backend para errores

### Error: "User not found in local database"

1. El usuario no se ha sincronizado aún
2. Ejecutar manualmente `sync-user` o esperar al próximo login
3. Verificar que el email coincide exactamente

### Usuario tiene `external_id` NULL

1. El usuario fue creado manualmente y aún no se ha autenticado en Supabase
2. Cuando se autentique, se vinculará automáticamente
3. O vincular manualmente con `tools/link_user_to_supabase.py`
