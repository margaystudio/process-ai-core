# Configuración de Ambientes

Este documento describe cómo configurar y ejecutar la aplicación en diferentes ambientes: **local**, **test** y **production**.

## Estructura de Archivos

### Backend (FastAPI)

```
process-ai-core/
├── .env                    # Variables de entorno (no versionado)
├── .env.local              # Configuración local (opcional, no versionado)
├── .env.test               # Configuración test (no versionado)
├── .env.production         # Configuración production (no versionado)
├── .env.example            # Plantilla de variables (versionado)
├── run_api_local.sh        # Script para ejecutar en local
├── run_api_test.sh         # Script para ejecutar en test
└── run_api_prod.sh         # Script para ejecutar en production
```

### Frontend (Next.js)

```
ui/
├── .env.local              # Configuración local (no versionado)
├── .env.test               # Configuración test (no versionado)
├── .env.production         # Configuración production (no versionado)
├── .env.local.example      # Plantilla local (versionado)
├── .env.test.example       # Plantilla test (versionado)
└── .env.production.example # Plantilla production (versionado)
```

## Configuración Inicial

### 1. Backend

1. Copia la plantilla de variables:
   ```bash
   cp .env.example .env.local
   ```

2. Edita `.env.local` con tus valores:
   ```env
   ENVIRONMENT=local
   OPENAI_API_KEY=tu-api-key
   DATABASE_URL=sqlite:///data/process_ai_core.sqlite
   API_PORT=8000
   CORS_ORIGINS=http://localhost:3000,http://localhost:3001
   ```

3. Para test y production, crea archivos similares:
   ```bash
   cp .env.example .env.test
   cp .env.example .env.production
   ```

### 2. Frontend

1. Copia la plantilla para local:
   ```bash
   cd ui
   cp .env.local.example .env.local
   ```

2. Edita `.env.local`:
   ```env
   NEXT_PUBLIC_ENVIRONMENT=local
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_SUPABASE_URL=tu-url-de-supabase
   NEXT_PUBLIC_SUPABASE_ANON_KEY=tu-anon-key
   ```

3. Para test y production:
   ```bash
   cp .env.test.example .env.test
   cp .env.production.example .env.production
   ```

## Ejecución por Ambiente

### Local (Desarrollo)

**Backend:**
```bash
# Opción 1: Usar script
chmod +x run_api_local.sh
./run_api_local.sh

# Opción 2: Manual
export ENVIRONMENT=local
uvicorn api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd ui
npm run dev:local
# O simplemente:
npm run dev
```

### Test

**Backend:**
```bash
chmod +x run_api_test.sh
./run_api_test.sh
```

**Frontend:**
```bash
cd ui
# Asegúrate de tener .env.test configurado
npm run dev:test
```

### Production

**Backend:**
```bash
chmod +x run_api_prod.sh
./run_api_prod.sh
```

**Frontend:**
```bash
cd ui
# Asegúrate de tener .env.production configurado
npm run build:prod
npm run start
```

## Variables de Entorno por Ambiente

### Backend

#### Local
- `ENVIRONMENT=local`
- `DATABASE_URL=sqlite:///data/process_ai_core.sqlite`
- `API_PORT=8000`
- `CORS_ORIGINS=http://localhost:3000,http://localhost:3001`
- `LOG_LEVEL=INFO`

#### Test
- `ENVIRONMENT=test`
- `DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/process_ai_test`
- `API_PORT=8001`
- `CORS_ORIGINS=https://test.yourapp.com`
- `LOG_LEVEL=INFO`

#### Production
- `ENVIRONMENT=production`
- `DATABASE_URL=postgresql+psycopg://user:pass@prod-db:5432/process_ai`
- `API_PORT=8000`
- `CORS_ORIGINS=https://yourapp.com`
- `LOG_LEVEL=WARNING`

### Frontend

#### Local
- `NEXT_PUBLIC_ENVIRONMENT=local`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_SUPABASE_URL=` (opcional, puede estar vacío)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=` (opcional)

#### Test
- `NEXT_PUBLIC_ENVIRONMENT=test`
- `NEXT_PUBLIC_API_URL=http://localhost:8001`
- `NEXT_PUBLIC_SUPABASE_URL=https://test-project.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=test-anon-key`

#### Production
- `NEXT_PUBLIC_ENVIRONMENT=production`
- `NEXT_PUBLIC_API_URL=https://api.yourapp.com`
- `NEXT_PUBLIC_SUPABASE_URL=https://prod-project.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=prod-anon-key`

## Diferencias Clave entre Ambientes

### Local
- ✅ Hot reload habilitado
- ✅ Logging detallado (INFO/DEBUG)
- ✅ SQLite para desarrollo rápido
- ✅ CORS permisivo (localhost)
- ✅ Sin autenticación estricta (opcional)

### Test
- ✅ Hot reload habilitado
- ✅ Logging detallado
- ✅ Base de datos separada (PostgreSQL recomendado)
- ✅ Supabase configurado con proyecto de test
- ✅ CORS restringido a dominio de test

### Production
- ❌ Hot reload deshabilitado
- ⚠️ Logging mínimo (WARNING/ERROR)
- ✅ Base de datos optimizada (PostgreSQL)
- ✅ Supabase configurado con proyecto de producción
- ✅ CORS restringido a dominio de producción
- ✅ Múltiples workers para mejor rendimiento

## Seguridad

### ⚠️ Importante

1. **Nunca versiones archivos `.env`** - Están en `.gitignore`
2. **Usa proyectos separados de Supabase** para test y production
3. **Usa bases de datos separadas** para cada ambiente
4. **Rota las API keys regularmente** en producción
5. **Usa secretos gestionados** (AWS Secrets Manager, Vault, etc.) en producción

## Troubleshooting

### El backend no carga las variables de entorno

1. Verifica que el archivo `.env.*` existe
2. Verifica que las variables no tienen espacios alrededor del `=`
3. Usa `export $(cat .env.local | grep -v '^#' | xargs)` manualmente

### El frontend no conecta con el backend

1. Verifica `NEXT_PUBLIC_API_URL` en `.env.local`
2. Verifica que el backend está corriendo en el puerto correcto
3. Verifica CORS en el backend

### Supabase no funciona en test/prod

1. Verifica que las credenciales son correctas
2. Verifica que el proyecto de Supabase está activo
3. Verifica que las URLs de callback están configuradas en Supabase

