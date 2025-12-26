# Configuración de Supabase para Ambiente de Test

Esta guía te ayudará a configurar Supabase para el ambiente de test, permitiéndote probar la autenticación y autorización sin afectar el ambiente de producción.

## Paso 1: Crear Proyecto de Supabase para Test

1. Ve a [https://supabase.com](https://supabase.com) e inicia sesión
2. Haz clic en **"New Project"**
3. Configura el proyecto:
   - **Name**: `process-ai-test` (o el nombre que prefieras)
   - **Database Password**: Elige una contraseña segura (guárdala)
   - **Region**: Selecciona la región más cercana
   - **Pricing Plan**: Free tier es suficiente para test
4. Espera a que se cree el proyecto (puede tardar 1-2 minutos)

## Paso 2: Obtener Credenciales de Supabase

1. En el Dashboard de Supabase, ve a **Settings** → **API**
2. Encontrarás las siguientes credenciales:

### Project URL (para ambos)
- En la parte superior de la página, encontrarás el **Project URL**: `https://xxxxx.supabase.co`
  - Este valor va en ambos archivos (backend y frontend)

### Para el Frontend (`ui/.env.test`)
- **Publishable key** (en la sección "Publishable key")
  - Esta es la clave pública, segura para usar en el navegador
  - Copia el valor completo (empieza con `sb_publishable_...`)
  - Este valor va en → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - ⚠️ Nota: Aunque el nombre del archivo dice "ANON_KEY", usa la **Publishable key**

### Para el Backend (`.env.test`)
- **Secret key** (en la sección "Secret keys")
  - ⚠️ **IMPORTANTE**: Esta es una clave secreta, nunca la expongas en el frontend
  - Haz clic en el ícono del ojo 👁️ para revelar la clave completa
  - Copia el valor completo (empieza con `sb_secret_...`)
  - Este valor va en → `SUPABASE_SERVICE_ROLE_KEY`
  - ⚠️ Nota: Aunque el nombre del archivo dice "SERVICE_ROLE_KEY", usa la **Secret key**

### Nota sobre las nuevas API keys
Supabase ha actualizado su sistema de API keys. Si ves una pestaña "Legacy anon, service_role API keys", puedes usar esas también, pero las nuevas son:
- **Publishable key** = antigua "anon key"
- **Secret key** = antigua "service_role key"

## Paso 3: Configurar Variables de Entorno

### Backend (`.env.test`)

Edita el archivo `.env.test` en la raíz del proyecto:

```env
# ... otras configuraciones ...

# SUPABASE CONFIGURATION (TEST)
SUPABASE_URL=https://tu-proyecto-test.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Frontend (`ui/.env.test`)

Edita el archivo `ui/.env.test`:

```env
# ... otras configuraciones ...

# SUPABASE AUTHENTICATION (TEST)
NEXT_PUBLIC_SUPABASE_URL=https://tu-proyecto-test.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Paso 4: Configurar URLs de Redirección en Supabase

1. En el Dashboard de Supabase, ve a **Authentication** → **URL Configuration**
2. Agrega las siguientes URLs:

### Site URL
```
http://localhost:3001
```

### Redirect URLs
Agrega estas URLs (una por línea):
```
http://localhost:3001/auth/callback
http://localhost:3001/**
```

Esto permite que el frontend en el puerto 3001 (ambiente de test) pueda autenticar usuarios.

## Paso 5: Configurar OAuth Providers (Opcional)

Si quieres probar autenticación con Google, Facebook, etc.:

### Google OAuth

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la API de Google+
4. Crea credenciales OAuth 2.0:
   - Tipo: **Web application**
   - **Authorized redirect URIs**: 
     ```
     https://tu-proyecto-test.supabase.co/auth/v1/callback
     ```
5. Copia el **Client ID** y **Client Secret**
6. En Supabase Dashboard:
   - Ve a **Authentication** → **Providers**
   - Habilita **Google**
   - Ingresa Client ID y Client Secret
   - Guarda

### Facebook OAuth (Opcional)

1. Ve a [Facebook Developers](https://developers.facebook.com/)
2. Crea una nueva app
3. Agrega "Facebook Login" como producto
4. Configura OAuth Redirect URIs:
   ```
   https://tu-proyecto-test.supabase.co/auth/v1/callback
   ```
5. En Supabase Dashboard:
   - Habilita **Facebook**
   - Ingresa App ID y App Secret

## Paso 6: Probar la Configuración

### 1. Iniciar Backend en modo Test

```bash
./run_api_test.sh
```

Deberías ver en los logs:
```
🚀 Iniciando API en ambiente: test
🌐 CORS origins configurados: ['http://localhost:3001', ...]
```

### 2. Iniciar Frontend en modo Test

```bash
cd ui
npm run dev:test
```

El frontend debería iniciar en `http://localhost:3001`

### 3. Probar Autenticación

1. Ve a `http://localhost:3001/login`
2. Prueba los diferentes métodos:
   - **Email + Password**: Crea un usuario primero
   - **Magic Link / OTP**: Ingresa tu email, recibirás un link/código
   - **Google OAuth**: Si lo configuraste, debería funcionar

### 4. Verificar Sincronización

Después de autenticarte:
1. Verifica en los logs del backend que se llamó `/api/v1/auth/sync-user`
2. Verifica en la base de datos local que se creó/actualizó el usuario

## Paso 7: Crear Usuarios de Test

### Opción 1: Desde Supabase Dashboard

1. Ve a **Authentication** → **Users**
2. Haz clic en **"Add user"**
3. Crea usuarios de prueba con diferentes roles

### Opción 2: Desde la UI

1. Ve a `http://localhost:3001/login`
2. Usa "Sign up" para crear nuevos usuarios
3. Verifica que se sincronizan con la DB local

## Troubleshooting

### Error: "Supabase credentials not configured"

- Verifica que las variables `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` estén en `.env.test`
- Verifica que el script `run_api_test.sh` esté cargando el archivo correcto

### Error: "Invalid API key"

- Verifica que copiaste las keys correctas (anon key para frontend, service_role para backend)
- Asegúrate de no tener espacios extra al copiar

### Error: "Redirect URI mismatch"

- Verifica que las URLs en Supabase Dashboard coincidan exactamente
- Incluye el protocolo (`http://`) y el puerto (`:3001`)
- Verifica que agregaste `http://localhost:3001/auth/callback`

### Error: "User not found in local database"

- El usuario se autenticó en Supabase pero no se sincronizó
- Verifica que el endpoint `/api/v1/auth/sync-user` esté funcionando
- Revisa los logs del backend para ver errores

### El frontend no conecta con Supabase

- Verifica que `NEXT_PUBLIC_SUPABASE_URL` y `NEXT_PUBLIC_SUPABASE_ANON_KEY` estén en `ui/.env.test`
- Reinicia el servidor de Next.js después de cambiar variables de entorno
- Verifica que estás usando `npm run dev:test` (no `npm run dev`)

## Buenas Prácticas

1. **Proyecto Separado**: Usa un proyecto de Supabase diferente para test y producción
2. **Base de Datos Separada**: El ambiente de test usa una DB diferente (`process_ai_core_test.sqlite`)
3. **Datos de Prueba**: Puedes crear usuarios y datos de prueba sin afectar producción
4. **Limpiar Datos**: Considera limpiar la DB de test periódicamente

## Siguiente Paso: Configurar Producción

Una vez que test esté funcionando, puedes seguir la misma guía para configurar producción, pero:
- Usa un proyecto de Supabase diferente
- Usa URLs de producción en lugar de localhost
- Configura dominios reales en las redirect URLs

