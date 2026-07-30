# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/), simplificado.
Monorepo: se versiona **por componente** con tags prefijados — `api-vX.Y.Z` y `ui-vX.Y.Z`
(norma: `margay-gcp-run-template/docs/VERSIONING.md`).

## Unreleased

### Removed
- **Restos del sistema de identidad propio.** Process AI arrastraba código de una auth
  local que nunca existió de verdad: el login va al Hub (`ui/lib/hub-login.ts`), los JWT
  los emite Supabase y se validan por JWKS, y la proyección local la mantiene
  `sync_workspace_access` con escritura al leer desde `session/context`. Se eliminó:
  - `users.password_hash` — **nunca autenticó nada**. No había ruta de login ni
    verificación de contraseña; se escribía siempre en `""`. Su comentario decía "Para
    autenticación local" y era falso.
  - `workspace_invitations` — tabla, modelo y cinco helpers (`create`, `get_by_token`,
    `accept`, `list`, `pending_by_email`), **sin una sola ruta de API que los expusiera**.
    El router ya se había eliminado antes (ver `api/main.py`); esto era el resto.
    Las invitaciones son del Hub (`workspace.tenant_invitations`).
  - `POST /api/v1/users` — creaba usuarios con email y nombre a mano. Con SSO y sync
    automático no aplica; la UI no lo llamaba.
  - `updateUserProfile` en `ui/lib/api.ts` — estaba definida y **sin usar**. Aplastaba
    nombre y apellido en un campo `name`.

  **Migración en tres tiempos**, porque `password_hash` era `NOT NULL` con el default del
  lado de SQLAlchemy y no del servidor — sacarla del modelo y borrarla después habría
  dejado una ventana con todos los INSERT de usuario rotos (`NotNullViolation`):
  1. `0019_auth_muerta_compat` — la columna gana `DEFAULT ''` en el servidor. Se puede
     aplicar con el código viejo corriendo: no rompe nada y no destruye nada. A partir
     de acá el código viejo (que manda `""`) y el nuevo (que no la manda) conviven.
  2. Deploy de este release.
  3. `0020_drop_auth_muerta` — recién ahora se borran la columna y la tabla.

  Aplicar la 0020 antes del paso 2 deja la base sin la columna mientras el código
  deployado todavía la manda: `UndefinedColumn` en cada INSERT.

  **No se tocó** lo que está bien: `sync_workspace_access`, `sync_membership_from_context`,
  `users`, `workspace_memberships`, ni `roles`/`user_operational_roles` (permisos finos del
  módulo). `users.auth_provider` queda: lo escribe el sync vivo y sacarlo obligaría a tocar
  la firma de `get_or_create_user` en el camino caliente.

### Changed
- **`PUT /api/v1/users/{id}` ya no acepta `name`.** El nombre es propiedad de Workspace y
  se edita en el Hub; permitir editarlo acá separaba el dato local del canónico sin que
  volvieran a converger (el sync pisa lo del usuario, o al revés, según quién llegue
  último). El teléfono sí se queda: tiene flujo de verificación propio del módulo.
  Ver `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`.

### Fixed
- **JWKS: se elimina el default hardcodeado.** `DEFAULT_SUPABASE_JWKS_URL` apuntaba a
  `zgujorkqulkdsnmjdxtj`, que es el proyecto **Margay Platform Test**. Si faltaban
  `SUPABASE_JWKS_URL` y `SUPABASE_URL`, el módulo no fallaba: validaba tokens contra el
  emisor de otro entorno y seguía andando. Ahora levanta `RuntimeError`. Verificado que
  `ops/api/prod.config.toml` ya define `SUPABASE_URL` (a `sjujhroqaoggwbwiviqu`), así que
  el cambio no rompe el deploy actual.

### Changed
- Adopción de la norma de versionado Margay + CI/CD:
  - Un solo `ops/release.py` / `ops/deploy.py` (con `--component api|ui`) + soporte de
    `[image].dockerfile` (Dockerfile.api / Dockerfile.ui). Reemplaza los scripts por componente.
  - GitHub Actions: `release.yml` (tags `api-v*` / `ui-v*`) + `deploy-manual.yml` (dropdown
    entorno + componente). El release file se commitea a `main` (default branch; gitflow).
  - `ops/api/releases/` y `ops/ui/releases/` dejan de ignorarse (registro versión→digest).
- Cutover a europe-west1 + Supabase nuevo (api + ui). Digests de us-central1 archivados
  localmente en `ops/{api,ui}/releases/_archive-us-central1/`.
- `/` (health): expone la versión desde `APP_VERSION` en vez de un literal.

Sin tags semver previos (releases eran `sha-*`): las primeras versiones serán
`api-v0.1.0` / `ui-v0.1.0`.
