# Plan de Implementación de Autenticación

## Paso 1: Instalación y Setup Inicial

### 1.1 Instalar dependencias

```bash
cd ui
npm install next-auth@beta  # Versión 5 (Auth.js) - más moderna
# O si prefieres la versión estable:
npm install next-auth@4
```

### 1.2 Crear estructura de archivos

```
ui/
├── app/
│   ├── api/
│   │   └── auth/
│   │       └── [...nextauth]/
│   │           └── route.ts      # NextAuth handler
│   └── login/
│       └── page.tsx               # Página de login
├── lib/
│   └── auth.ts                    # Configuración de NextAuth
└── middleware.ts                   # Middleware para proteger rutas
```

## Paso 2: Configuración de NextAuth

### 2.1 Variables de entorno (.env.local)

```env
# NextAuth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=tu-secret-key-generada-aleatoriamente

# Google OAuth
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret

# Facebook OAuth (opcional por ahora)
FACEBOOK_CLIENT_ID=tu-app-id
FACEBOOK_CLIENT_SECRET=tu-app-secret

# Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2.2 Generar NEXTAUTH_SECRET

```bash
openssl rand -base64 32
```

## Paso 3: Implementación Frontend

### 3.1 Configurar NextAuth (lib/auth.ts)

- Configurar proveedores (Google, Facebook)
- Callbacks para crear/actualizar usuarios en DB
- Generar JWT con datos del usuario

### 3.2 Crear API Route (app/api/auth/[...nextauth]/route.ts)

- Handler de NextAuth
- Configuración de callbacks

### 3.3 Crear página de login (app/login/page.tsx)

- Botones para Google, Facebook
- Redirección después de login

### 3.4 Middleware de protección (middleware.ts)

- Proteger rutas que requieren autenticación
- Redirigir a /login si no está autenticado

## Paso 4: Integración con Backend

### 4.1 Endpoints del Backend

1. `POST /api/v1/auth/sync-user` - Sincronizar usuario desde NextAuth
2. `POST /api/v1/auth/verify-token` - Validar JWT
3. `GET /api/v1/auth/user` - Obtener usuario autenticado

### 4.2 Middleware de autenticación en FastAPI

- Validar JWT en requests
- Extraer datos del usuario
- Inyectar usuario en contexto

### 4.3 Actualizar helpers de DB

- Función para crear/actualizar usuario desde OAuth
- Buscar usuario por email o external_id

## Paso 5: Actualizar Frontend Existente

### 5.1 Actualizar hooks

- `useUserId` - Usar NextAuth session
- `useUserRole` - Mantener lógica existente

### 5.2 Actualizar API client

- Agregar JWT a headers automáticamente
- Manejar errores de autenticación

### 5.3 Actualizar componentes

- Mostrar nombre/avatar del usuario
- Botón de logout
- Proteger rutas

## Paso 6: Testing

1. Login con Google
2. Login con Facebook
3. Verificar JWT en backend
4. Verificar permisos
5. Logout

## Orden de Implementación Recomendado

1. ✅ Setup básico de NextAuth
2. ✅ Configurar Google OAuth
3. ✅ Crear página de login
4. ✅ Proteger rutas con middleware
5. ✅ Integrar con backend (sync user)
6. ✅ Agregar JWT validation en backend
7. ✅ Actualizar hooks y componentes
8. ✅ Agregar Facebook OAuth
9. ✅ Testing completo

## Notas Importantes

- Mantener compatibilidad temporal con localStorage durante migración
- Los usuarios existentes necesitarán hacer login una vez
- Considerar migración de datos si hay usuarios de prueba


