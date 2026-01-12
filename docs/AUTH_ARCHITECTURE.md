# Arquitectura de Autenticación y Autorización

## Stack Tecnológico

### Frontend (Next.js)
- **NextAuth.js (Auth.js)** - Manejo de OAuth y sesiones
- **JWT** - Tokens para comunicación con backend
- **Cookies HTTP-only** - Almacenamiento seguro de sesiones

### Backend (FastAPI)
- **python-jose** - Validación de JWT
- **passlib** - Hashing de contraseñas (si usamos auth local)
- **python-multipart** - Ya está instalado

## Flujo de Autenticación

### 1. Login con OAuth (Google, Facebook, etc.)

```
Usuario → NextAuth.js → Proveedor OAuth → Callback → NextAuth.js
  ↓
NextAuth crea/actualiza User en DB
  ↓
NextAuth genera JWT
  ↓
JWT almacenado en cookie HTTP-only
  ↓
Frontend usa JWT en headers para API calls
```

### 2. Comunicación Frontend ↔ Backend

```
Frontend (Next.js)
  ↓ (JWT en Authorization header)
Backend (FastAPI)
  ↓ (Valida JWT)
Backend verifica permisos
  ↓
Respuesta
```

## Estructura de JWT

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "name": "User Name",
  "auth_provider": "google",
  "external_id": "google_user_id",
  "iat": 1234567890,
  "exp": 1234571490
}
```

## Configuración de NextAuth.js

### Proveedores OAuth
- Google OAuth 2.0
- Facebook Login
- GitHub (opcional)
- Microsoft (opcional)

### Callbacks
- **signIn**: Verificar/crear usuario en DB
- **jwt**: Agregar datos al token JWT
- **session**: Formatear datos de sesión

## Integración con Backend

### Endpoints del Backend
1. `POST /api/v1/auth/verify-token` - Validar JWT
2. `GET /api/v1/auth/user` - Obtener datos del usuario autenticado
3. `POST /api/v1/auth/sync-user` - Sincronizar usuario desde NextAuth

### Middleware de Autenticación
```python
async def verify_jwt_token(token: str) -> dict:
    """Valida JWT y retorna payload"""
    # Validar firma
    # Verificar expiración
    # Retornar datos del usuario
```

### Protección de Endpoints
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    payload = verify_jwt_token(token.credentials)
    return payload
```

## Base de Datos

### Modelo User (ya existe)
- `id`: UUID
- `email`: Email único
- `name`: Nombre
- `external_id`: ID del proveedor OAuth
- `auth_provider`: "google" | "facebook" | "local"
- `auth_metadata_json`: Tokens, refresh tokens, etc.

### Flujo de Creación de Usuario
1. Usuario se autentica con OAuth
2. NextAuth recibe datos del proveedor
3. NextAuth busca usuario por `email` o `external_id + auth_provider`
4. Si no existe, crea nuevo usuario
5. Si existe, actualiza metadata si es necesario
6. Retorna JWT con datos del usuario

## Variables de Entorno

### Frontend (.env.local)
```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=tu-secret-key-muy-segura

# Google OAuth
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret

# Facebook OAuth
FACEBOOK_CLIENT_ID=tu-facebook-app-id
FACEBOOK_CLIENT_SECRET=tu-facebook-app-secret

# Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)
```env
JWT_SECRET_KEY=tu-jwt-secret-key (debe coincidir con NEXTAUTH_SECRET)
JWT_ALGORITHM=HS256
```

## Implementación por Fases

### Fase 1: Setup Básico
1. Instalar NextAuth.js
2. Configurar Google OAuth
3. Crear página de login
4. Proteger rutas con middleware

### Fase 2: Integración con Backend
1. Crear endpoint de verificación de JWT
2. Agregar middleware de autenticación en FastAPI
3. Actualizar endpoints para usar autenticación
4. Sincronizar usuarios entre NextAuth y DB

### Fase 3: Múltiples Proveedores
1. Agregar Facebook OAuth
2. Agregar otros proveedores según necesidad

### Fase 4: Autorización
1. Integrar con sistema de permisos existente
2. Verificar permisos en endpoints
3. Middleware de autorización por rol

## Seguridad

### JWT
- Firma con secret key compartido
- Expiración corta (1 hora)
- Refresh tokens para renovación
- HTTP-only cookies para almacenamiento

### OAuth
- State parameter para CSRF protection
- PKCE para clientes públicos (si aplica)
- Validación de redirect URIs

### Backend
- Validar JWT en cada request
- Verificar expiración
- Rate limiting en endpoints de auth

## Migración desde Sistema Actual

1. Mantener compatibilidad temporal con `localStorage.getItem('userId')`
2. Migrar gradualmente a NextAuth
3. Actualizar `useUserId` hook para usar NextAuth
4. Eliminar código de desarrollo (localStorage)



