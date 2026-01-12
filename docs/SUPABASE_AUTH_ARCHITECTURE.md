# Arquitectura de Autenticación con Supabase Auth

## Stack Tecnológico

### Frontend (Next.js)
- **@supabase/supabase-js** - Cliente de Supabase
- **@supabase/ssr** - Soporte para Server-Side Rendering
- **@supabase/auth-helpers-nextjs** - Helpers para Next.js App Router

### Backend (FastAPI)
- **supabase** (Python) - Cliente de Supabase para validar tokens
- **python-jose** - Validación de JWT (backup)
- **pyjwt** - Parsing de JWT

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

## Flujo de Autenticación

### 1. Email + Password

```
Usuario → Next.js → Supabase Auth.signInWithPassword()
  ↓
Supabase valida credenciales
  ↓
Supabase retorna JWT
  ↓
Next.js almacena JWT en cookies
  ↓
Next.js sincroniza usuario con DB local (si no existe)
  ↓
Frontend usa JWT en requests a FastAPI
```

### 2. Email OTP / Magic Link

```
Usuario → Next.js → Supabase Auth.signInWithOtp()
  ↓
Supabase envía email con código/link
  ↓
Usuario ingresa código o hace click en link
  ↓
Supabase valida y retorna JWT
  ↓
Next.js almacena JWT
  ↓
Sincronizar usuario con DB local
```

### 3. OAuth (Google)

```
Usuario → Next.js → Supabase Auth.signInWithOAuth()
  ↓
Redirige a Google OAuth
  ↓
Usuario autoriza en Google
  ↓
Google redirige a Supabase callback
  ↓
Supabase crea sesión y retorna JWT
  ↓
Next.js almacena JWT
  ↓
Sincronizar usuario con DB local
```

## Sincronización de Usuarios

### Modelo en DB Local (ya existe)

```python
class User(Base):
    id: str  # UUID
    email: str
    name: str
    external_id: str | None  # Supabase user ID
    auth_provider: str  # "supabase" | "google" | etc.
    auth_metadata_json: str  # Tokens, etc.
```

### Flujo de Sincronización

1. Usuario se autentica en Supabase
2. Next.js recibe JWT con datos del usuario
3. Next.js llama a `POST /api/v1/auth/sync-user` con datos de Supabase
4. Backend busca usuario por `external_id` (Supabase user ID)
5. Si no existe, crea nuevo usuario
6. Si existe, actualiza metadata
7. Retorna usuario local con permisos/roles

## Validación de Tokens en FastAPI

### Endpoint de Validación

```python
POST /api/v1/auth/verify-token
Body: { "token": "jwt_token" }
Response: { "user": {...}, "valid": true }
```

### Middleware de Autenticación

```python
async def get_current_user(token: str = Depends(security)):
    # Validar token con Supabase
    supabase_user = supabase.auth.get_user(token)
    
    # Buscar usuario local
    local_user = get_user_by_external_id(supabase_user.id)
    
    return local_user
```

## Variables de Entorno

### Frontend (.env.local)

```env
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-anon-key

# Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key
SUPABASE_JWT_SECRET=tu-jwt-secret
```

## Estructura de JWT de Supabase

```json
{
  "aud": "authenticated",
  "exp": 1234567890,
  "sub": "supabase_user_id",
  "email": "user@example.com",
  "app_metadata": {
    "provider": "google",
    "providers": ["google"]
  },
  "user_metadata": {
    "name": "User Name",
    "avatar_url": "..."
  }
}
```

## Endpoints del Backend

### 1. Sincronizar Usuario
```
POST /api/v1/auth/sync-user
Body: {
  "supabase_user_id": "...",
  "email": "...",
  "name": "...",
  "auth_provider": "google",
  "metadata": {...}
}
Response: {
  "user_id": "...",
  "created": true/false
}
```

### 2. Verificar Token
```
POST /api/v1/auth/verify-token
Body: { "token": "..." }
Response: {
  "valid": true,
  "user": {...},
  "expires_at": "..."
}
```

### 3. Obtener Usuario Autenticado
```
GET /api/v1/auth/user
Headers: { "Authorization": "Bearer <token>" }
Response: {
  "user": {...},
  "workspaces": [...]
}
```

## Protección de Rutas

### Frontend (Next.js)

```typescript
// middleware.ts
export async function middleware(request: NextRequest) {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  
  if (!session && protectedRoutes.includes(request.nextUrl.pathname)) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
}
```

### Backend (FastAPI)

```python
@router.get("/protected")
async def protected_route(user: User = Depends(get_current_user)):
    return {"message": "Hello", "user": user.email}
```

## Ventajas de esta Arquitectura

1. ✅ **Supabase maneja toda la complejidad de OAuth**
2. ✅ **No dependemos de la DB de Supabase** (solo Auth)
3. ✅ **Mantenemos control total sobre nuestra DB**
4. ✅ **Sistema de permisos/roles existente se mantiene**
5. ✅ **Fácil agregar más proveedores OAuth**
6. ✅ **Magic links y OTP sin implementar desde cero**

## Consideraciones

- Los usuarios existen en dos lugares: Supabase (auth) y DB local (datos)
- Necesitamos mantener sincronización entre ambos
- El `external_id` en DB local apunta al `sub` del JWT de Supabase
- Los permisos/roles se manejan en DB local, no en Supabase



