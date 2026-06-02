# Checklist — Integrar un módulo nuevo al ecosistema Margay

> Fecha: 2026-06-01
> Basado en la integración de process-ai-core (Etapa 1).
> Seguir este checklist para que cualquier módulo nuevo quede alineado al control plane
> de margay-workspace, comparta sesión con el hub, y tenga el mismo nivel de seguridad.

---

## 1. Registrar la app en margay-workspace

En el hub (`hub.margaystudio.io/admin/applications`), crear la aplicación con:
- `key`: slug único del módulo (ej. `process_ai`, `oms`, `insights`)
- `name`: nombre visible
- `type`: `tenant_extension`
- `entry_url`: URL del módulo en prod (ej. `https://process.margaystudio.io`)

Habilitar la app para los tenants que corresponda en `/admin/tenants/{id}`.

Agregar la URL del módulo a `ALLOWED_NEXT_ORIGINS` en `margay-hub/ui/app/page.tsx`.

---

## 2. Backend (FastAPI + Python)

### 2.1 Dependencias
```
httpx>=0.27.0
pyjwt[cryptography]>=2.8.0
```

### 2.2 Variables de entorno requeridas
```bash
SUPABASE_URL=https://nbigcpjmckewuhrqjzrt.supabase.co
SUPABASE_JWKS_URL=https://nbigcpjmckewuhrqjzrt.supabase.co/auth/v1/.well-known/jwks.json
WORKSPACE_URL=https://margay-workspace-513594124246.us-central1.run.app
{MODULE}_APP_KEY=<key registrada en workspace, ej. process_ai>
ARTIFACT_SIGNING_SECRET=<secreto random, obligatorio en prod>
ARTIFACT_URL_TTL_SECONDS=900   # opcional, default 900
ENVIRONMENT=production         # o local/test
```

### 2.3 Validación del JWT de Supabase

Copiar el patrón de `api/dependencies.py` de process-ai-core:
- `PyJWKClient` lazy singleton contra `SUPABASE_JWKS_URL`
- `algorithms=["ES256", "RS256"]`, `audience="authenticated"`, require `sub`+`exp`
- Función `_decode_and_verify_supabase_jwt(token)` → payload

Referencia canónica: `margay-workspace/app/services/auth.py`

### 2.4 Cliente de contexto de workspace

Copiar `api/workspace_client.py` de process-ai-core y ajustar:
- `WorkspaceSessionContext` (schemas espejo de workspace)
- `fetch_workspace_context(token)` → contexto con caché TTL 30s
- `get_workspace_context` → dependencia FastAPI
- `require_{module}_access` → gate que verifica la key del módulo en `ctx.applications`
- `sync_workspace_access` → dependencia de router que crea/sincroniza User + Workspace local + Membership
- `resolve_tenant_workspace_id(ctx)` → id del Workspace local (get-or-create)

### 2.5 Modelo de datos local

Agregar columna `tenant_id` (unique, nullable, indexed) al modelo de "workspace/organización"
local. La función `get_or_create_workspace_for_tenant(session, tenant_id, name, slug)` crea
el workspace local la primera vez que entra un tenant.

### 2.6 RBAC local (si el módulo lo necesita)

Mapeo de roles macro → roles locales (ajustar según el dominio del módulo):
```python
"superadmin" (platform) → rol de mayor privilegio local
"tenant_admin"           → admin
"tenant_member"          → rol operativo base
"tenant_external_client" → viewer (o el que corresponda al dominio)
```
`sync_membership_from_context` crea/actualiza la membership local en cada request.

### 2.7 Seguridad en endpoints

- Todo endpoint que recibe un id de recurso por path → verificar que
  `recurso.workspace_id == resolve_tenant_workspace_id(ctx)` → 404 si no coincide.
- Nunca aceptar `workspace_id` o `user_id` del cliente (query/body). Siempre del contexto.
- Archivos servidos (PDFs, imágenes generadas) → proteger con URLs firmadas HMAC.
  Copiar `api/artifact_signing.py` de process-ai-core.

### 2.8 Verificación final
```bash
grep -rn "verify_signature" api/   # → vacío
grep -rn "workspace_id.*Query\|workspace_id.*Body" api/routes/   # → vacío
```

---

## 3. Frontend (Next.js 14 + @supabase/ssr)

### 3.1 Variables de entorno requeridas
```bash
NEXT_PUBLIC_SUPABASE_URL=https://nbigcpjmckewuhrqjzrt.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key del proyecto compartido>
NEXT_PUBLIC_HUB_URL=https://hub.margaystudio.io   # localhost: http://localhost:3001
NEXT_PUBLIC_API_URL=https://<url del backend>
```

### 3.2 Cookie de dominio padre (compartir sesión con el hub)

En `lib/supabase/client.ts`:
```ts
const isProd = process.env.NODE_ENV === 'production'
return createBrowserClient(url, key, {
  cookieOptions: isProd
    ? { domain: '.margaystudio.io', sameSite: 'lax', secure: true, path: '/' }
    : undefined,
})
```

En `lib/supabase/server.ts`, en el `setAll`:
```ts
cookieStore.set(name, value, {
  ...options,
  ...(isProd ? { domain: '.margaystudio.io' } : {}),
})
```

### 3.3 Callback de Supabase

`app/auth/callback/route.ts` — intercambia el code por sesión con los mismos cookieOptions.
Validar el parámetro `next` contra `ALLOWED_ORIGINS` antes de redirigir.
NO llamar a syncUser ni ningún endpoint de auth propio — el usuario se auto-sincroniza
vía `sync_workspace_access` en el primer request al backend.

```ts
const ALLOWED_ORIGINS = [
  'https://<modulo>.margaystudio.io',
  'https://hub.margaystudio.io',
  'http://localhost:3000',
  'http://localhost:3001',
]
```

### 3.4 Middleware: redirect al hub si no hay sesión

`lib/supabase/middleware.ts` — cuando no hay sesión:
```ts
const HUB_URL = process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io'
const loginUrl = new URL(`${HUB_URL}/login`)
loginUrl.searchParams.set('next', request.nextUrl.href)
return NextResponse.redirect(loginUrl)
```

### 3.5 Sin login propio

El módulo NO implementa pantalla de login. El login es del hub.
Si existía una pantalla `/login`, eliminarla.

### 3.6 Supabase redirect URLs

En el dashboard de Supabase (proyecto `nbigcpjmckewuhrqjzrt`):
Authentication → URL Configuration → Redirect URLs → agregar:
```
https://<modulo>.margaystudio.io/auth/callback
http://localhost:3000/auth/callback   # para dev local
```

---

## 4. Despliegue

Seguir el patrón de `margay-gpu-ops` (Cloud Run + ops scripts):

```bash
# API
cp ops/api/prod.config.toml.example ops/api/prod.config.toml
python ops/api/release.py --env prod --version vX.Y.Z
python ops/api/deploy.py --env prod

# UI
cp ops/ui/prod.config.toml.example ops/ui/prod.config.toml
python ops/ui/release.py --env prod --version vX.Y.Z
python ops/ui/deploy.py --env prod
```

Infra: Cloud Run (us-central1), imagen en Artifact Registry `margay-services`,
service accounts `process-ai-api-sa@margay-platform-prod.iam.gserviceaccount.com`
y `process-ai-ui-sa@margay-platform-prod.iam.gserviceaccount.com`.

Secretos sensibles (`ARTIFACT_SIGNING_SECRET`, `OPENAI_API_KEY`, etc.) → Secret Manager,
referenciados en `ops/api/prod.config.toml` bajo `[secrets]`.

---

## 5. Verificación post-integración

- [ ] Sin sesión → redirige a `hub.margaystudio.io/login?next=<url del módulo>`
- [ ] Con sesión en el hub → entra al módulo sin re-login (cookie compartida en prod)
- [ ] Usuario con 1 sola app no-admin → hub lo manda directo al módulo
- [ ] `grep -rn "verify_signature" api/` → vacío
- [ ] Test de aislamiento cross-tenant en verde
- [ ] PDF/artifacts firmados cargando en iframes
