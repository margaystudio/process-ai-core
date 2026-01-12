# Guía de Configuración de Autenticación con Supabase

## Paso 1: Crear Proyecto en Supabase

1. Ve a https://supabase.com y crea una cuenta
2. Crea un nuevo proyecto
3. Anota los siguientes valores:
   - **Project URL** (ej: `https://xxxxx.supabase.co`)
   - **anon/public key** (para el frontend)
   - **service_role key** (para el backend, mantener secreto)

## Paso 2: Configurar OAuth Providers

### Google OAuth

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google+
4. Crea credenciales OAuth 2.0:
   - Tipo: Web application
   - Authorized redirect URIs: `https://tu-proyecto.supabase.co/auth/v1/callback`
5. Copia el **Client ID** y **Client Secret**
6. En Supabase Dashboard:
   - Ve a Authentication > Providers
   - Habilita Google
   - Ingresa Client ID y Client Secret
   - Guarda

### Facebook OAuth (Opcional)

1. Ve a [Facebook Developers](https://developers.facebook.com/)
2. Crea una nueva app
3. Agrega "Facebook Login" como producto
4. Configura OAuth Redirect URIs: `https://tu-proyecto.supabase.co/auth/v1/callback`
5. En Supabase Dashboard:
   - Habilita Facebook
   - Ingresa App ID y App Secret

## Paso 3: Configurar Variables de Entorno

### Frontend (.env.local)

```env
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend (.env)

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key
```

## Paso 4: Instalar Dependencias

### Frontend

```bash
cd ui
npm install @supabase/supabase-js @supabase/ssr
```

### Backend

```bash
pip install supabase pyjwt python-jose[cryptography]
```

O si usas el proyecto instalado:

```bash
pip install -e .
```

## Paso 5: Configurar Supabase Auth

En el Dashboard de Supabase:

1. Ve a Authentication > URL Configuration
2. Agrega tu URL de desarrollo: `http://localhost:3000`
3. Agrega tu URL de producción cuando esté lista
4. Configura redirect URLs:
   - `http://localhost:3000/auth/callback`
   - `https://tu-dominio.com/auth/callback`

## Paso 6: Probar Autenticación

1. Inicia el servidor de desarrollo:
   ```bash
   cd ui
   npm run dev
   ```

2. Ve a http://localhost:3000/login

3. Prueba los diferentes métodos:
   - Email + Password (necesitas crear un usuario primero)
   - Magic Link / OTP
   - Google OAuth

## Notas Importantes

- **Service Role Key**: NUNCA lo expongas en el frontend. Solo se usa en el backend.
- **Anon Key**: Es seguro exponerlo en el frontend, pero tiene limitaciones de seguridad (RLS).
- **Magic Links**: Los usuarios recibirán un email con un link que los autentica automáticamente.
- **OTP**: Los usuarios recibirán un código de 6 dígitos por email.

## Troubleshooting

### Error: "Invalid API key"
- Verifica que las variables de entorno estén correctamente configuradas
- Asegúrate de usar `NEXT_PUBLIC_` para variables del frontend

### Error: "Redirect URI mismatch"
- Verifica que las URLs en Supabase Dashboard coincidan exactamente
- Incluye el protocolo (http/https) y el puerto si es necesario

### Error: "User not found in local database"
- El usuario se autenticó en Supabase pero no se sincronizó con la DB local
- Verifica que el endpoint `/api/v1/auth/sync-user` esté funcionando
- Revisa los logs del backend



