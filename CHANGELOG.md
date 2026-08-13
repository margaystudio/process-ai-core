# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/), simplificado.
Monorepo: se versiona **por componente** con tags prefijados — `api-vX.Y.Z` y `ui-vX.Y.Z`
(norma: `margay-gcp-run-template/docs/VERSIONING.md`).

## Unreleased

## api-v0.7.0 · ui-v0.7.0 — 2026-08-13

Release del **rediseño de permisos a dos capas**, la adopción de **margay-ui 0.15.1**
(identidad Arrayán) y el estándar de estados de carga. Incluye además todo lo que
estaba en Unreleased desde v0.6.0 (directorio de usuarios, id canónico, decided_by).

> **Deploy a prod:** correr `alembic upgrade head` contra la base de prod como parte
> del deploy (migraciones `0024` con backfill y `0025` que **borra** las tablas del
> RBAC legacy y el workspace 'sistema' — hacer backup antes; `0025` no tiene downgrade
> con datos). El código y las migraciones van juntos: no hay ventana de convivencia.

### Security
- **Endpoints sin autenticación cerrados** (`tests/test_endpoints_cerrados.py` fija el
  contrato): se eliminó `POST /users/{id}/workspaces/{ws}/membership` (sin auth y con
  `role_name=owner` por default — otorgaba owner a cualquiera); los listados de
  workspaces y membresías exigen sesión y son self-only/por membresía;
  `generate-pdf` exige JWT. `require_process_ai_access` (gate de app por tenant) pasó
  de proteger solo documents a todos los routers con datos de tenant.
- **El permiso por carpeta se aplica también a versiones y PDFs**: las rutas de
  versiones, PDF congelado, preview, current-version y audit-log pasan por
  `assert_document_viewable` (antes solo chequeaban tenant: un usuario sin acceso a la
  carpeta podía leer el PDF y el historial completos).
- **Tyto ya no permite saltear el permiso por carpeta preguntando**: el retrieval
  descarta las citas de carpetas que el usuario no puede ver, antes del umbral de
  relevancia y del LLM.

### Changed
- **Modelo de permisos de tres capas a DOS** (migraciones `0024` + `0025`, alineado con
  el ADR de plataforma "Roles por módulo"). Los roles de sistema
  (owner/admin/approver/creator/viewer) se eliminaron — eran un vocabulario intermedio
  que nadie administraba, derivado por mapeo fijo del rol de tenant y con la mitad de
  los valores inalcanzables. Ahora:
  - `workspace_memberships.base_access` (`admin`|`member`|`external`) ← rol macro del
    tenant, sincronizado desde workspace usando el **rol efectivo por app**
    (`tenant_modules[].applications[].role`): un `tenant_member` puede ser admin solo
    de Process AI. El campo deprecado `applications` ya no se lee (workspace pudo
    borrar su shim de `margay_contracts`).
  - `operational_roles.access_level` (`lectura`|`edicion`|`aprobacion`, acumulativos):
    el rol del cliente define qué se puede hacer además de dónde. Evaluación por par
    (permiso, carpeta) — "aprueba en Pista, solo lee en Seguridad" ahora se puede.
    Especificación ejecutable en `tests/test_permission_context.py`.
  - Cambios de comportamiento deliberados: settings y branding del workspace son
    solo-admin; quien no tiene `documents.edit` ve solo documentos aprobados;
    `external` es tope de solo lectura siempre.
- **La UI gatea todo por `GET /users/me/capabilities`** (patrón OMS): desapareció la
  matriz de permisos hardcodeada del frontend (que ya estaba desincronizada) y el
  gating por carpeta llegó al wizard y las pantallas (`useFolderAccess`) — se acabaron
  los botones que terminaban en 403.
- **Design system margay-ui 0.5.0 → 0.15.1 e identidad Arrayán**: PlatformShell +
  ModuleSwitcher (destinos en pestaña nueva, Hub aparte), sidebar con links reales y
  el gating por capabilities intacto, assets de brand de los 7 módulos.
  `GET /users/me` reexpone `modules` para el switcher. El tenant activo sigue por
  cookie/header (el patrón 0.12 "cliente en la URL" no aplica acá) y el white-label
  0.14 no se wireó (el branding por workspace existente convive con el switcher de
  tenants).
- **Estándar de estados de carga**: `Skeleton` (única forma de carga de
  contenido/página; el shell aparece completo con skeletons en su lugar) y `Spinner`
  sobrio (solo acciones dentro de un control). Murieron el logo del margay girando y
  los ~20 spinners ad-hoc.

### Added
- `GET /users/me/capabilities`: permisos efectivos + acceso por carpeta resuelto
  (herencia incluida) + flags de gestión. Única fuente del gating de UI.
- **Visor de acceso efectivo**
  (`GET /workspaces/{id}/members/{mid}/effective-access` + botón "Ver acceso" en la
  tab Usuarios): para cada miembro, qué puede hacer en cada carpeta y POR QUÉ (qué rol
  se lo da, de qué ancestro hereda la restricción). Convierte "¿por qué Juan no puede
  aprobar acá?" en una consulta de segundos.
- **Nivel de acceso en roles operativos** (UI): selector Lectura/Edición/Aprobación al
  crear/editar, badge de nivel en listados y junto a cada rol en las pantallas de
  permisos de carpeta.
- **Indicador restringida/abierta por carpeta** (`permissions_restricted` en
  `FolderResponse` + candado en el árbol y chip en settings): comunica la regla "en
  las carpetas abiertas cada miembro actúa según su nivel máximo; para controlar
  quién hace qué, se restringe".

### Removed
- Tablas `roles`/`permissions`/`role_permissions`, columnas `role_id`/`role` de
  memberships y el workspace legacy 'sistema' (migración `0025`, que absorbe
  `cleanup_workspace_sistema.py`). El superadmin es solo por claim de plataforma +
  `base_access` del sync.
- Tools muertos: `seed_permissions.py` (ya no hay nada que sembrar),
  `create_super_admin.py`, `cleanup_workspace_sistema.py`, `migrate_to_permissions.py`,
  `migrate_workspace_sistema_description.py`.
- UI muerta: onboarding (sus endpoints no existían), `adminGating`/`useUserRole`
  (reemplazados por capabilities), `documentPermissions.ts`, `LoadingOverlay` del
  margay girando.


### Changed
- **`document_relations.confirmed_by` → `decided_by`, y `confirmed_at` → `decided_at`**
  (migración `0023`). El nombre mentía: las dos columnas se escriben en `confirm()` **y** en
  `reject()`, así que en una relación rechazada `confirmed_by` guardaba a quien la rechazó.

  No es cosmética. Son campos de gobierno: `decided_by IS NULL` es el rastro de "confirmada por
  el sistema, sin intervención humana" (autoconfirmación por umbral, ADR-006). Un `confirmed_by`
  al lado de un `status='rejected'` se lee como una contradicción, y quien filtre por él creyendo
  que trae solo confirmaciones se lleva también los rechazos.

  Se renombró **antes** de exponerlo en pantalla a propósito: el campo ya viajaba en la API y
  ninguna vista lo pintaba, así que era el momento más barato. Después de que una pantalla lo
  muestre, el nombre queda. `ALTER TABLE … RENAME COLUMN` conserva datos, tipo, FK e índices.

### Fixed
- **El puente del id canónico quedaba en NULL: el mapa vacío con el directorio lleno.** Al adoptar
  el id canónico, `UserDirectory` perdió el campo `auth_user_id` —correcto *después* de la `0022`,
  que borra la columna— y con él se fue de `_guardar_directorio`. Pero la migración todavía no
  había corrido: la columna existía, el primer barrido la dejó en NULL, y el mapeo local→canónico
  no encontró nada.

  Modo de falla silencioso y engañoso: la tabla se ve perfecta, los nombres resuelven bien en
  pantalla, y lo único roto es el mapeo — que no se nota hasta que se intenta migrar, y ahí el
  error apunta al lugar equivocado (los usuarios revocados).

  El mapa ahora tiene **dos puentes en orden**: `auth_user_id` primero —el correcto, el auth id no
  cambia nunca— y **email** como respaldo, que ambas tablas tienen sin depender del orden de
  despliegue. Es peor llave (el email se puede cambiar en el Hub y la copia local no se refresca),
  por eso va segundo y nunca primero. Si los dos están vacíos, no mapea y lo informa.

  De paso, `tools/censo_id_canonico.py` tenía su propio SQL de mapeo, duplicando el de la
  migración: ahora **importa el de la migración**. Era exactamente la deriva contra la que existe
  la guarda del inventario.

  La regla general quedó anotada en el estándar: **la escritura del puente sobrevive hasta la
  migración que lo borra, no hasta el release que la contiene.**

- **`DOCUMENT_VERIFICATION_BASE_URL` faltaba en los configs de deploy**, y el arranque falla sin
  ella fuera de local/test. Detalle en la entrada de `ops` más abajo.

### Added
- **`process_ai.users_directory` — el directorio de usuarios del módulo** (migración
  `0021`), poblado por **escritura al leer** desde
  `GET /api/tenants/{tid}/applications/{key}/directory` de Workspace. Implementa el §2 y
  §3 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`, calcado de CRM
  (`commercial.users_directory`) y dashboards (`analytics.users_directory`).

  **No reemplaza a `sync_workspace_access`**, que sigue manteniendo `users` y
  `workspace_memberships` desde `session/context` — eso ya era el §3 resuelto a mano.
  Lo que agrega es lo que `session/context` no puede dar, porque solo trae al usuario
  actual:
  - **Frescura.** `get_or_create_local_user_from_workspace` escribe `users.name` al
    CREAR la fila y después nunca más (encuentra por `external_id` y retorna). Si la
    persona se cambia el nombre en el Hub, Process AI le seguía diciendo como se llamaba
    el día que entró por primera vez. El directorio se refresca por TTL cuando cualquier
    miembro del módulo lee un nombre.
  - **Formato canónico.** `display_name` lo calcula Workspace y viaja en el DTO.
  - **Cobertura.** Alcanza a los miembros del módulo que todavía no entraron nunca.

  Reglas del estándar que se respetan: **nunca `DELETE`** (el que sale queda
  `status='revoked'` para que el histórico siga resolviendo su nombre), **degradación
  elegante** (si Workspace no responde se sirve lo vencido, y si nunca se pobló se cae a
  la proyección local: resolver nombres jamás rompe una request), y es `/directory` y
  **no** el endpoint de admin — que es el anti-patrón #7 y deja a los usuarios comunes
  sin poder resolver ningún nombre.

  `users` y `users_directory` van **separadas**: la PK las hace infusionables
  (`(tenant_id, user_id)` contra un id global con email único — meterle `status` a
  `users` haría que revocar a alguien en un tenant lo revoque en todos), y así cada
  tabla tiene **un escritor único**. `users` sigue siendo el ancla del RBAC del módulo.

  La columna `auth_user_id` es **transitoria**: puentea
  `users.external_id = users_directory.auth_user_id` mientras `users.id` siga siendo un
  uuid propio. Su criterio de salida es la migración del id canónico.

- **`process_ai.users.id` ahora es el id canónico de la plataforma** (`workspace.users.id`, §4 del
  estándar). Migración `0022_id_canonico`.

  **No es lo mismo que en OMS y dashboards, y conviene decirlo:** allá las columnas ya guardaban un
  uuid de Auth y la migración cambia el **valor de una columna**. Acá se repunta la **PRIMARY KEY
  de `users`** y hay que arrastrar todo lo que la referencia.

  El mapeo es determinístico y de dos saltos —`users.id → external_id → users_directory.auth_user_id
  → users_directory.user_id`— y pasa por `users_directory`, tabla del módulo poblada por la API.
  **Ni un `JOIN workspace.*`:** bajo el enforcement previsto (un rol de base por módulo sin `GRANT`
  sobre `workspace`) un join cross-schema fallaría adentro de la migración, con las FKs ya soltadas.

  **Son 12 sitios de referencia, no 8.** Los cuatro que un barrido por catálogo NO ve son los
  peligrosos: `tyto_query_log.user_id` y `tyto_session.user_id` (sin FK a propósito — auditoría
  desacoplada, migración `0018`) y `validations.assigned_approver_ids`, que es un array JSON
  serializado en `Text` y para Postgres es una columna de texto cualquiera. El inventario vive en
  `process_ai_core/db/id_remap.py`, lo comparten la migración y el censo, y hay una guarda que
  aborta si aparece una FK fuera de la lista (más un test que lo verifica contra el esquema real).

  **No se tocan** los `acta_*_by_name` / `acta_*_by_role` congelados (`0017`): son texto histórico,
  no ids — dicen qué decía el acta ESE día. Tampoco `users.external_id`, que sigue siendo la llave
  con la que se resuelve el `sub` del JWT.

  **Protocolo de conteo.** `tools/censo_id_canonico.py` no escribe nada y es el mismo comando antes
  y después: cuenta filas, ids distintos y huérfanas por sitio, resuelve el mapa y detecta
  colisiones. La migración repite el conteo internamente y **revierte** si algún total se movió.
  `users_id_remap` guarda `(id_viejo, id_nuevo, email)` como rastro de auditoría y para el
  `downgrade`. Ensayado de punta a punta con los tres tipos de sitio: conteos idénticos, ida y
  vuelta completa.

  **Los usuarios revocados antes del primer barrido no tienen mapeo** — `/directory` solo devuelve
  miembros activos. La migración **aborta** y los nombra; con
  `PROCESS_AI_REMAP_PERMITIR_SIN_MAPEO=1` sigue y los deja con su id local (su nombre se sigue
  resolviendo por la proyección local, pero no se refresca). Pasa hoy con 1 de 3 usuarios en prod y
  1 de 4 en test. Es un punto ciego del estándar, no de este módulo.

  Con esto `users_directory.auth_user_id` cumplió su criterio de salida y se borró: el join contra
  el directorio pasa a ser `users_directory.user_id = users.id`, directo.

### Fixed
- **La UI mostraba UUIDs crudos donde tenía que decir un nombre.** El historial decía
  "Aprobada el 3/2/2026 por 8a5f4e82-2ca9-4515-90fd-392947ec87a3"; la pantalla de
  corrección, "Rechazado por usuario: <uuid>". La causa: la UI resolvía cada id con un
  `getUser()` por separado contra `GET /api/v1/users/{id}`, que es **self-only por
  diseño** (403 para cualquier id que no sea el tuyo), y el `catch` caía al uuid. Nunca
  funcionó para nadie que no fueras vos.

  Se resuelve **en el servidor**, en lote, sobre los payloads que la UI ya pedía — sin
  endpoint de resolución nuevo y sin round-trips extra:
  - `GET /documents/{id}/versions` → `approved_by_name`, `rejected_by_name`, `created_by_name`
  - `GET /documents/{id}/validations` → `validator_user_name`
  - `GET /documents/{id}/audit-log` → `user_name` (el audit log no mostraba actor)
  - `GET /documents/{id}/current-version` → `approved_by_name`

  Los `*_name` **no son columnas**: se resuelven al leer contra `users_directory`. Es
  justo la diferencia con el anti-patrón #2 (`oms.orders.created_by_name` y sus ocho
  hermanas), donde el nombre quedó guardado y los pedidos viejos muestran para siempre
  el nombre que la persona tenía ese día. Los uuid siguen viajando: la UI los necesita
  para comparar contra el usuario actual.

  Del lado del cliente se borraron los dos `useEffect` que hacían el N+1 y el prop
  `userDisplayNames`. Cuando no hay nombre no se muestra el uuid: se omite el fragmento
  "por …" (ausencia de actor es un estado válido) o se dice "Usuario desconocido".

### Changed
- **`resolve_signatories` toma el nombre del directorio y el rol operativo de la base
  local** (`process_ai_core/db/signatories.py`). Son dos preguntas con dos fuentes
  distintas y el §1 no las mezcla: Workspace no sabe quién es "Encargado de turno" en
  una estación de servicio, y el módulo no decide cómo se escribe el nombre de una
  persona. Los `acta_*_by_name` congelados al aprobar (migración `0017`) **no se tocan**:
  son el §5 bien hecho — snapshot en registro inmutable, con el uuid al lado.
- **El módulo dejó de armar el nombre** (anti-patrón #6). `get_or_create_local_user_from_workspace`
  concatenaba `" ".join(filter(None, [first_name, last_name]))`; ahora guarda el
  `display_name` que manda Workspace. El que concatena el nombre es siempre el que
  después lo persiste: así nacieron las nueve columnas `*_by_name` de OMS.

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

### Security
- **Eliminado `GET /api/v1/users`, que era público.** Devolvía id, email, nombre y fecha de
  **todos los usuarios de todos los tenants** sin ninguna dependencia de auth y sin filtro de
  tenant: el router no declara `dependencies` y la función no tenía un solo `Depends`.
  Cualquiera que conociera la URL obtenía el padrón completo de la plataforma. Ninguna
  pantalla lo usaba. El listado de usuarios de un módulo sale de la API de Workspace
  (`/directory` para resolver nombres, `/api/admin/...` para gestionar accesos), siempre
  gateado por el JWT y scopeado al tenant y la app.

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
