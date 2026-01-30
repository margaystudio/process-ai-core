# Cómo Vincular un Usuario Local con Supabase Auth

Este documento explica cómo vincular un usuario creado en la base de datos local con Supabase Auth.

## Contexto

El sistema usa **Supabase Auth** para autenticación, pero mantiene una **base de datos local** (SQLite/PostgreSQL) con información de usuarios, workspaces, documentos, etc.

La vinculación se hace mediante el campo `external_id` en la tabla `users`, que almacena el **Supabase User ID** (el `sub` del JWT).

## Flujo de Vinculación

### Opción 1: Vinculación Automática (Recomendado)

Cuando un usuario se autentica en Supabase por primera vez, el sistema lo vincula automáticamente:

1. **Usuario se autentica en Supabase** (email/password, OAuth, Magic Link)
2. **Supabase retorna un JWT** con el `sub` (User ID de Supabase)
3. **Frontend llama a `/api/v1/auth/sync-user`** con:
   - `supabase_user_id`: El `sub` del JWT
   - `email`: Email del usuario
   - `name`: Nombre del usuario
4. **Backend sincroniza** usando `create_or_update_user_from_supabase()`:
   - Si el usuario existe por `email` → actualiza `external_id`
   - Si el usuario existe por `external_id` → actualiza datos
   - Si no existe → crea nuevo usuario con `external_id`

**Ventaja**: Automático, no requiere intervención manual.

### Opción 2: Crear Usuario en Supabase Primero

Si ya tienes el usuario creado en la BD local y quieres vincularlo:

1. **Crear usuario en Supabase Auth**:
   - Dashboard de Supabase: Authentication > Users > Add User
   - O usando la API de Supabase
   - O esperar a que el usuario se registre normalmente

2. **Obtener el Supabase User ID**:
   - Dashboard: Users > [usuario] > UUID (es el `id`)
   - O desde el JWT después de login: `data.user.id`
   - O desde la consola del navegador:
     ```javascript
     const { data } = await supabase.auth.getUser()
     console.log(data.user.id)
     ```

3. **Vincular manualmente**:
   ```bash
   python tools/link_user_to_supabase.py
   ```
   O actualizar directamente en la BD:
   ```sql
   UPDATE users 
   SET external_id = '<SUPABASE_USER_ID>', 
       auth_provider = 'supabase'
   WHERE email = 'sdalto@margaystudio.io';
   ```

### Opción 3: Crear Usuario en Supabase y Vincular Automáticamente

1. **Crear usuario en Supabase Auth** (Dashboard o API)
2. **El usuario inicia sesión** en la UI
3. **El sistema lo vincula automáticamente** mediante `sync-user`

## Pasos Detallados para tu Caso

### Paso 1: Crear Usuario en BD Local

```bash
python tools/create_super_admin.py
```

Esto crea el usuario `sdalto@margaystudio.io` en la BD local.

### Paso 2: Crear Usuario en Supabase Auth

**Opción A: Desde el Dashboard**
1. Ir a Supabase Dashboard > Authentication > Users
2. Click en "Add User" o "Invite User"
3. Ingresar email: `sdalto@margaystudio.io`
4. Configurar contraseña o enviar invitación
5. Copiar el **UUID** del usuario (es el Supabase User ID)

**Opción B: Desde la UI de la App**
1. Ir a `/login`
2. Hacer click en "Sign up" o "Sign in"
3. Registrar/iniciar sesión con `sdalto@margaystudio.io`
4. Supabase creará el usuario automáticamente

### Paso 3: Vincular Usuario

**Si usaste Opción A (Dashboard):**
```bash
python tools/link_user_to_supabase.py
# Ingresar email: sdalto@margaystudio.io
# Ingresar Supabase User ID: (el UUID copiado)
```

**Si usaste Opción B (UI):**
El sistema lo vincula automáticamente cuando el usuario inicia sesión.

### Paso 4: Verificar Vinculación

```sql
SELECT id, email, name, external_id, auth_provider 
FROM users 
WHERE email = 'sdalto@margaystudio.io';
```

Deberías ver:
- `external_id`: El UUID de Supabase
- `auth_provider`: `'supabase'`

## Estructura de Datos

### Tabla `users` (BD Local)

```sql
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,           -- UUID local
    email VARCHAR(200) UNIQUE,           -- Email único
    name VARCHAR(200),                    -- Nombre
    external_id VARCHAR(255),             -- Supabase User ID (sub del JWT)
    auth_provider VARCHAR(50),            -- 'supabase' | 'local' | 'google' | etc.
    ...
);
```

### JWT de Supabase

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // Este es el external_id
  "email": "sdalto@margaystudio.io",
  "aud": "authenticated",
  "role": "authenticated",
  ...
}
```

## Endpoints Relevantes

### `POST /api/v1/auth/sync-user`

Sincroniza un usuario desde Supabase a la BD local.

**Request:**
```json
{
  "supabase_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "sdalto@margaystudio.io",
  "name": "Santiago Dalto",
  "auth_provider": "supabase",
  "metadata": {}
}
```

**Response:**
```json
{
  "user_id": "local-uuid-here",
  "email": "sdalto@margaystudio.io",
  "name": "Santiago Dalto",
  "created": false  // true si se creó, false si se actualizó
}
```

### `POST /api/v1/auth/verify-token`

Valida un token JWT de Supabase y retorna información del usuario.

## Troubleshooting

### El usuario no se vincula automáticamente

1. Verificar que el endpoint `/api/v1/auth/sync-user` se llama después del login
2. Verificar que `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` están configurados
3. Revisar logs del backend para errores

### Error: "User not found" al hacer login

1. Verificar que el usuario existe en Supabase Auth
2. Verificar que el email coincide exactamente (case-sensitive en algunos casos)
3. Verificar que el usuario puede iniciar sesión en Supabase

### El usuario tiene `external_id` NULL

1. El usuario aún no se ha vinculado con Supabase
2. Ejecutar `link_user_to_supabase.py` para vincular manualmente
3. O esperar a que el usuario inicie sesión y se vincule automáticamente

## Scripts Disponibles

- `tools/create_super_admin.py`: Crea usuario super admin en BD local
- `tools/link_user_to_supabase.py`: Vincula usuario local con Supabase manualmente
- `tools/reset_to_production_ready.py`: Resetea BD manteniendo datos estáticos
