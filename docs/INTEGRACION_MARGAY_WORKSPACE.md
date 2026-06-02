# Plan de Integración — process-ai-core como módulo de margay-workspace

> **Fecha:** 2026-05-28
> **Estado:** Diseño / corresponde a la **Etapa 1 del MVP** (`docs/CODE_REVIEW_2026-05_MVP_PLAN.md`).
> **Decisión:** process-ai-core deja de tener auth propia y se integra como **módulo
> (app `process-ai`)** del control plane `margay-workspace`.

> ⚠️ Verificar siempre el contrato vigente contra el repo `margay-workspace`
> (`/Users/santi/src/margay-workspace`) antes de implementar — este doc refleja el estado a
> 2026-05-28.

---

## 1. Por qué integrarse (no arreglar la auth aislada)

Margay tiene un **control plane** central, `margay-workspace`, que ya resuelve lo que
process-ai-core hoy hace mal y de forma insegura:

| Pregunta | Quién la responde |
|---|---|
| ¿Quién es el usuario? | margay-workspace (valida JWT de Supabase) |
| ¿A qué **tenant** (organización/estación) pertenece? | margay-workspace (`tenants`/`tenant_users`) |
| ¿A qué **apps/módulos** puede entrar y con qué rol? | margay-workspace (`applications`/`application_memberships`) |
| ¿Qué puede hacer **dentro** de process-ai (permisos finos sobre documentos)? | **process-ai-core** (RBAC local) |

Reconstruir esto por app es duplicar trabajo e introducir agujeros (como el actual). La
gestión de usuarios y el portal de apps los maneja **margay-hub**; process-ai-core confía
en el contexto de sesión.

---

## 2. Contrato real de margay-workspace (a 2026-05-28)

**Auth (copiar de `margay-workspace/app/services/auth.py`):**
- JWT de **Supabase**, validado con **JWKS** (algoritmo **ES256**, ECC P-256).
- `audience = "authenticated"`, requerir claims `sub` y `exp`.
- `sub` = `supabase_auth_user_id` (identidad canónica del ecosistema).
- JWKS URL: `https://nbigcpjmckewuhrqjzrt.supabase.co/auth/v1/.well-known/jwks.json`
- Patrón: `PyJWKClient` (lazy singleton, `cache_keys=True`).

**Endpoint de contexto de sesión** (verificado en `app/schemas/session.py`, devuelve los roles):
```
GET /api/session/context
Authorization: Bearer <supabase_jwt>

→ {
    "user":          { "id", "email", "first_name", "last_name" },
    "platform_roles":[ "superadmin", ... ],        # roles de plataforma del usuario
    "tenant_roles":  [ "tenant_admin", ... ],      # roles en el tenant ACTIVO
    "tenant":        { "id", "name", "slug" },     # tenant activo
    "tenants":       [ { "id", "name", "slug" } ], # todos los del usuario
    "applications":  [ { "key", "name", "type", "entry_url" } ]  # apps a las que tiene acceso
  }
Errores: 401 invalid_token | 404 user_not_found | 404 no_active_tenant | 500 internal_error
```
> Importante: el rol macro YA viene en `tenant_roles` y el acceso al módulo en
> `applications`. process-ai-core NO necesita consultar la DB de workspace para autorizar a
> nivel macro — alcanza con el contexto.

**Roles de tenant (los únicos 3, de `migrations/002_roles.sql` + screenshot del Hub):**
| key | label UI | uso |
|---|---|---|
| `tenant_admin` | Administrador | gestiona el tenant, invita usuarios |
| `tenant_member` | Miembro | usuario interno del tenant |
| `tenant_external_client` | Cliente externo | rol macro genérico; **la semántica la define cada módulo** (ver nota) |

> **`tenant_external_client` es genérico y su significado depende del módulo.** Ejemplos
> reales en el ecosistema: en **margay-oms** el externo es un *cliente final que pide
> mercadería* desde fuera de la estación; en **process-ai-core** (consultoría) sería *Margay
> documentando como externo* en el tenant del cliente. Mismo rol de plataforma, dominio
> distinto → otra razón para que el rol de dominio fino lo defina el módulo (§3.1), no workspace.

Roles de plataforma: incluyen `superadmin` (bypass total).

**Invitaciones (ya implementadas en workspace):** `POST /api/invitations` con
`{tenant_id, email, tenant_role_key, application_key?}`. La invitación puede asociar
**directamente la app** (`application_key`) → al aceptarla, crea `tenant_users` +
`tenant_user_roles` + `application_memberships`. O sea: invitar a alguien al tenant GPU **con
acceso a `process-ai`** ya está soportado de fábrica.

**Schema `workspace` (multi-tenant desde el día 1):**
`users`, `tenants`, `tenant_users`, `platform_roles`/`user_platform_roles`,
`tenant_roles`/`tenant_user_roles`, `applications`, `tenant_applications`,
`application_memberships`, `tenant_invitations`.

**Prod:** `https://margay-workspace-513594124246.us-central1.run.app`

---

## 3. Mapeo de conceptos

| process-ai-core (hoy) | margay-workspace | Acción |
|---|---|---|
| `Workspace` (tenant interno: Margay, GPU) | `tenant` | **Organización/estación = tenant.** Alinear `workspace_id` interno con `tenant.id`/slug. |
| `User` (tabla local) | `users` (FK a Supabase) | Dejar de gestionar usuarios localmente; usar `sub`/`user.id` del contexto. |
| `WorkspaceMembership` + `Role` | `application_memberships` + `tenant_roles` | Acceso al módulo y rol macro → de margay-workspace. **Permisos finos** (documents.approve, etc.) → quedan en process-ai-core. |
| Login / OAuth / invitaciones (UI) | margay-hub + `/api/invitations` | Subsumido por el control plane. |

**Decisión de mapeo (2026-05-28):** organización = **tenant** de margay-workspace. El dato
de tenant ya se expone en `/api/session/context`; no hay que crearlo.

### 3.1 Modelo de roles de DOS NIVELES (resuelve la pregunta abierta)

Los roles de workspace son **genéricos de plataforma** (admin/member/external_client). NO
deben contaminarse con conceptos de un solo módulo (pistero/encargado/gerencia). El reparto:

| Nivel | Decide | Fuente | Ejemplos |
|---|---|---|---|
| **Acceso + rol macro** | margay-workspace | `tenant_roles` + `applications` del contexto | ¿es `tenant_admin`? ¿tiene acceso a la app `process-ai`? |
| **Rol de dominio + permisos finos** | **process-ai-core** | RBAC local ya existente (`Role`/`Permission`) | pistero / encargado / gerencia → quién crea, quién aprueba, qué carpetas ve |

Mapeo sugerido macro → comportamiento por defecto en process-ai-core:
- `tenant_admin` → admin del módulo (puede todo, incl. aprobar).
- `tenant_member` → rol operativo por defecto; el rol de dominio fino (pistero/encargado/
  gerencia) lo asigna process-ai-core dentro del módulo.
- `tenant_external_client` → rol macro genérico; en process-ai-core lo usaríamos para
  **Margay como consultor externo** documentando en el tenant del cliente (relevante para
  consultoría, ver `docs/ESTRATEGIA_COMERCIAL_Y_PRICING.md`). NOTA: el mismo rol significa
  otra cosa en otros módulos (en margay-oms = cliente final que pide mercadería), así que el
  comportamiento concreto lo decide process-ai-core, no el rol en sí.
- `superadmin` (plataforma) → bypass.

---

## 4. Pasos de implementación

### Paso 1 — Registrar el módulo
- Alta de la app en `workspace.applications` con **key = `process_ai`** (con guion bajo; confirmado registrado 2026-05-29), name, type, `entry_url`.
- Habilitar por tenant en `tenant_applications` (al menos tenant Margay para dogfooding).

### Paso 2 — Validar el JWT de Supabase (backend)
- Reemplazar en `api/dependencies.py:105` el `verify_signature: False` por validación real
  con JWKS (ES256, `aud="authenticated"`, requerir `sub`+`exp`). Copiar `auth.py` de workspace.
- Quitar el logging sensible de tokens/emails (`api/dependencies.py`).

### Paso 3 — Resolver contexto de sesión
- Cliente a `GET /api/session/context` con el JWT entrante; cachear con **TTL corto**.
- Dependencia FastAPI que expone `current_user_id`, `current_tenant`, `tenant_roles`,
  `platform_roles` y `applications` (todo viene en la respuesta, no hay que ir a la DB).
- **Gate de acceso al módulo:** rechazar si la key `process_ai` no está en `applications`.
- `WORKSPACE_URL` por entorno (prod = URL de Cloud Run de arriba).

### Paso 4 — Eliminar identidad desde el cliente
- Quitar `user_id`/`workspace_id` como query params en todos los endpoints
  (`api/routes/documents.py:50` y los demás). Derivar SIEMPRE del contexto.
- Filtrar todas las queries por el `tenant` del contexto.

### Paso 5 — Mapear tenant ↔ workspace interno
- Resolver el `Workspace` interno a partir del `tenant.id`/slug del contexto (crear-si-no-existe
  en el primer acceso, o sincronizar).

### Paso 6 — RBAC fino local
- Mantener los permisos sobre documentos/versiones en process-ai-core, pero como capa
  **debajo** del acceso al módulo y el rol macro que vienen del control plane.

### Paso 7 — Frontend + SSO entre subdominios (sesión compartida)
- process-ai-core se abre como app desde **margay-hub** (que ya hace login + portal).
- **process-ai-core NO implementa pantalla de login.** Si no hay sesión, redirige al hub
  para autenticar y vuelve (el código compartido `shared/auth/lib/callback.ts` ya soporta
  `next` + `allowedOrigins`).
- **Cómo se comparte la sesión (decidido 2026-05-28):** los módulos son **subdominios de
  `margaystudio.io`** (`hub.`, `process.`, `oms.`, …). La sesión de Supabase se comparte vía
  **cookie en el dominio padre** `.margaystudio.io`. Esto NO es una limitación de Supabase:
  hoy `@supabase/ssr` setea la cookie en el host exacto porque **falta configurar `domain`**.

  Estrategia adoptada: **cookie `.margaystudio.io` + login únicamente en el hub.**

  Configurar `cookieOptions.domain` en los TRES lugares (hoy ninguno lo hace):
  - browser client (`shared/auth/lib/supabase-browser.ts` → `createBrowserClient(..., { cookieOptions })`)
  - server client (`lib/supabase/server.ts`)
  - callback (`shared/auth/lib/callback.ts`, que ya setea `path`/`sameSite`/`secure` pero no `domain`)

  ```ts
  const isProd = process.env.NODE_ENV === 'production'
  cookieOptions: isProd
    ? { domain: '.margaystudio.io', sameSite: 'lax', secure: true, path: '/' }
    : undefined   // en localhost: comportamiento por defecto (host exacto)
  ```
  - `sameSite: 'lax'` alcanza (los subdominios son same-site). `secure: true` en prod.
  - Mantener `allowedOrigins` del callback con la lista de subdominios de módulos.
- Tras login en el hub, todos los subdominios ven la cookie → el usuario NO vuelve a loguear.
- **Dominios DISTINTOS (no subdominios) no pueden compartir cookie** — no es el caso de
  Margay, pero tenerlo presente si algún módulo viviera en otro dominio.

### Paso 7.1 — Redirect inteligente post-login (cliente de un solo módulo no conoce el hub)

**Objetivo de producto:** un cliente que contrató un solo módulo (ej. solo process-ai) no
debería siquiera enterarse de que el hub existe. El hub es detalle de implementación, no su
producto.

El dato para decidir YA existe: `applications[]` del `/api/session/context` dice a cuántos
módulos tiene acceso el usuario, y `platform_roles`/`tenant_roles` si es admin.

**Dos disparadores, tratados distinto:**

- **Caso A — entró por la URL de un módulo** (ej. `process.margaystudio.io` sin sesión):
  el redirect al login del hub lleva `next=<url del módulo>`. Tras login, **SIEMPRE vuelve al
  `next`** (al módulo que pidió), sin importar cuántos módulos tenga. Respeta el intent; no
  ve el hub. (Decidido 2026-05-28.)

- **Caso B — entró directo al hub** (`hub.margaystudio.io`, sin `next`): tras login, el hub
  evalúa `applications`:
  - **1 solo módulo y no es admin** → redirige directo a ese módulo (no muestra el portal).
  - **varios módulos o es admin** → muestra el portal del hub para que elija.

**Acceso al portal del hub para clientes de un solo módulo (decidido 2026-05-28):**
**"Inaccesible de hecho", NO bloqueo duro.** El redirect del Caso B ya logra que nunca usen
el portal. No se bloquea con 404/403 porque:
- El portal solo muestra las apps del PROPIO usuario → no hay fuga de info de otros tenants/clientes.
- Si mañana al cliente se le agrega un 2º módulo, deja de rebotar automáticamente (sin tocar código).
- El bloqueo duro es una mejora reversible que se suma después si un cliente grande lo exige.

**Regla de seguridad innegociable (independiente del redirect):** el acceso real lo valida
el **backend de cada módulo** contra `applications` (Paso 3, gate de acceso). El cliente de
process-ai no entra a `oms.margaystudio.io` aunque adivine la URL, porque el backend de oms
lo rechaza. El comportamiento del hub es UX; la autorización es backend.

**`allowedOrigins`:** el `next` se valida contra la lista de subdominios de módulos
(`shared/auth/lib/next.ts` → `resolveNext`) para evitar redirect a sitios externos. Mantener
esa lista poblada.

### Paso 8 — Aislamiento verificado
- Test automatizado: "tenant A no puede leer datos de tenant B".
- (Defensa en profundidad) RLS en Postgres sobre tablas con `tenant`/`workspace_id`.

---

## 5. Riesgos / cosas a confirmar antes de codear

- **RESUELTO — `/api/session/context` basta:** devuelve `platform_roles`, `tenant_roles`,
  `tenant`, `tenants` y `applications`. No hace falta leer la DB de workspace para autorizar
  a nivel macro.
- **RESUELTO — roles de estación:** modelo de DOS niveles (§3.1). pistero/encargado/gerencia
  viven como RBAC fino EN process-ai-core; NO se agregan a workspace.
- **Coordinación entre repos:** registrar la app `process-ai` y habilitarla por tenant es
  trabajo en `margay-workspace` (tablas `applications`/`tenant_applications`), no en este
  repo. **Santi se encarga de agregar `process-ai` a workspace** (confirmado 2026-05-28) —
  process-ai-core solo necesita la `key` final de la app para el gate de acceso.
- **Migración de datos existentes:** los usuarios/workspaces locales actuales hay que
  mapearlos a users/tenants de workspace (o descartarlos si son de prueba).
- **RESUELTO — key de la app:** `process_ai` (con guion bajo). Registrada en workspace
  (2026-05-29). El gate de acceso debe comparar EXACTO contra esta key.
