# Desglose de tareas por etapa — MVP Process AI Core

> **Fecha:** 2026-05-28
> **Cómo usar este doc:** cada tarea está pensada para ejecutarse de forma autocontenida
> (idealmente un agente/sesión por tarea o por grupo). Cada una indica: objetivo, archivos
> clave, criterio de "hecho" y dependencias. Marcá `[x]` al completar.
> **Contexto completo:** ver `CODE_REVIEW_2026-05_MVP_PLAN.md`, `INTEGRACION_MARGAY_WORKSPACE.md`,
> `RAG_IMPLEMENTATION_PLAN.md`, `ESTRATEGIA_COMERCIAL_Y_PRICING.md`.

> **Convención de prompts para agentes:** dale a cada agente (1) el objetivo de la tarea,
> (2) los archivos clave listados, (3) el criterio de hecho, y (4) que NO toque cosas fuera
> del alcance de la tarea. Pedile que corra los tests al terminar.

---

## Etapa 0 — Higiene y base

- [ ] **0.1 Purgar `.env.production` de git**
  - Objetivo: sacar el archivo del tracking, confirmarlo en `.gitignore`, purgar del historial.
  - Archivos: `.env.production`, `.gitignore`.
  - Hecho: `git ls-files` no lista `.env.production`; el historial no lo contiene; credenciales rotadas (acción manual de Santi).
  - Nota: la rotación de credenciales reales la hace Santi; el agente prepara el cambio de repo.

- [ ] **0.2 Consolidar branches**
  - Objetivo: decidir qué ramas (GDD3/4/6/8/10/12, etc.) entran a `develop` y cuáles se descartan.
  - Hecho: lista de ramas con decisión (merge/descarte); ramas muertas eliminadas.
  - Nota: requiere criterio de Santi sobre qué WIP sobrevive. NO borrar ramas sin confirmación.

- [ ] **0.3 Limpiar código muerto**
  - Objetivo: eliminar duplicación y archivos huérfanos.
  - Archivos: `process_ai_core/doc_engine.py` (duplica `domains/processes/`), `.pyc` huérfanos (`models_v2`, `context_files`, `operational_roles`).
  - Hecho: imports actualizados, tests en verde, sin referencias rotas.

- [ ] **0.4 Quitar logging sensible**
  - Objetivo: que los logs no filtren tokens/emails.
  - Archivos: `api/dependencies.py` (los `logger.info` con prefijos de token y emails).
  - Hecho: ningún log emite contenido de token ni email en INFO.

---

## Etapa 1 — Integración con margay-workspace + seguridad multi-tenant

> Precondición externa: RESUELTA — la app está registrada en margay-workspace con
> **key = `process_ai`** (con guion bajo; confirmado 2026-05-29).

- [ ] **1.1 Validar el JWT de Supabase (JWKS ES256)**
  - Objetivo: reemplazar `verify_signature: False` por validación real.
  - Archivos: `api/dependencies.py:105`. Referencia para copiar: `/Users/santi/src/margay-workspace/app/services/auth.py` (usa `PyJWKClient`).
  - Detalle: `algorithms=["ES256","RS256"]`, `audience="authenticated"`, requerir `sub`+`exp`. JWKS URL: `https://nbigcpjmckewuhrqjzrt.supabase.co/auth/v1/.well-known/jwks.json`.
  - Hecho: token inválido/forjado → 401; token válido → pasa; test de ambos casos.

- [ ] **1.2 Cliente de contexto de sesión + dependencia FastAPI**
  - Objetivo: consumir `GET /api/session/context` de workspace y exponer `current_user_id`, `current_tenant`, `tenant_roles`, `platform_roles`, `applications`.
  - Detalle: cachear con TTL corto. `WORKSPACE_URL` por entorno (prod: `https://margay-workspace-513594124246.us-central1.run.app`).
  - Hecho: dependencia inyectable que devuelve el contexto; maneja 401/404 del endpoint.
  - Depende de: 1.1.

- [ ] **1.3 Gate de acceso al módulo**
  - Objetivo: rechazar (403) si la key `process_ai` (guion bajo) no está en `applications` del contexto.
  - Hecho: usuario sin la app → 403; con la app → pasa; test.
  - Depende de: 1.2.

- [ ] **1.4 Eliminar identidad desde el cliente**
  - Objetivo: quitar `user_id`/`workspace_id` como query params en TODOS los endpoints; derivar del contexto.
  - Archivos: `api/routes/documents.py:50` y revisar todos los routers en `api/routes/`.
  - Hecho: ningún endpoint acepta `user_id`/`workspace_id` del cliente; todo sale del contexto.
  - Depende de: 1.2.

- [ ] **1.5 Mapear tenant ↔ workspace interno**
  - Objetivo: resolver el `Workspace` interno desde el `tenant.id`/slug del contexto (crear-si-no-existe o sincronizar).
  - Archivos: `process_ai_core/db/models.py` (Workspace), lógica de resolución en dependencias/servicios.
  - Hecho: cada request opera sobre el Workspace correcto según el tenant del contexto.
  - Depende de: 1.2.

- [ ] **1.6 RBAC fino bajo el rol macro**
  - Objetivo: mapear rol macro (tenant_admin/member/external_client) → comportamiento por defecto, manteniendo permisos finos locales.
  - Archivos: `process_ai_core/db/permissions.py`.
  - Hecho: tenant_admin puede aprobar; member usa rol de dominio local; ver tabla de roles en INTEGRACION_MARGAY_WORKSPACE.md §3.1.
  - Depende de: 1.2, 1.4.

- [ ] **1.7 Test de aislamiento entre tenants**
  - Objetivo: garantizar que el tenant A no puede leer datos del tenant B.
  - Archivos: `tests/`.
  - Hecho: test automatizado en verde que intenta cross-tenant y recibe 403/404.
  - Depende de: 1.4, 1.5.

- [ ] **1.8 SSO frontend: cookie de dominio padre + sin login propio**
  - Objetivo: que process-ai-core comparta sesión vía `.margaystudio.io` y no tenga login propio.
  - Archivos: `ui/lib/supabase/*` (server/client), config de cookies. Patrón compartido en `margay-hub/ui/shared/auth/`.
  - Detalle: `cookieOptions.domain='.margaystudio.io'` condicional por entorno (no en localhost); `sameSite:'lax'`, `secure:true` en prod; setear en browser+server+callback.
  - Hecho: logueado en el hub → entra a process sin re-login; sin sesión → redirige al hub.
  - Nota: este cambio toca código compartido del hub; coordinar/probar hub+process juntos.

- [ ] **1.9 Redirect inteligente post-login**
  - Objetivo: cliente de un solo módulo nunca ve el hub (Caso A: vuelve al `next`; Caso B: hub redirige si 1 módulo y no admin).
  - Archivos: lógica en el hub (`margay-hub`) + `allowedOrigins`. Ver INTEGRACION_MARGAY_WORKSPACE.md §7.1.
  - Hecho: los dos casos verificados manualmente.
  - Depende de: 1.8.

---

## Etapa 2 — Postgres real + migraciones

- [ ] **2.1 Corte SQLite → Supabase Postgres**
  - Objetivo: Postgres como base por defecto en dev y prod.
  - Archivos: `process_ai_core/db/database.py`, `.env.example`, config.
  - Hecho: la app levanta contra Postgres; tests corren contra Postgres.

- [ ] **2.2 Adoptar Alembic**
  - Objetivo: reemplazar los 17 scripts manuales `tools/migrate_*.py` por migraciones versionadas.
  - Archivos: nuevo `alembic/`, `tools/migrate_*.py` (a deprecar).
  - Hecho: `alembic upgrade head` reconstruye el schema desde cero; baseline de la estructura actual.
  - Depende de: 2.1.

- [ ] **2.3 Seed reproducible**
  - Objetivo: catálogos (audiencia/formalidad/detalle), planes de suscripción, roles/permisos base.
  - Archivos: script de seed + `process_ai_core/db/models_catalog.py`.
  - Hecho: base nueva queda usable con un comando de seed.
  - Depende de: 2.2.

---

## Etapa 3 — Endurecer el pipeline IA

- [ ] **3.1 Bug multi-video**
  - Objetivo: que un run con varios videos no descarte los posteriores en silencio.
  - Archivos: `process_ai_core/media.py:500` (return temprano).
  - Hecho: run con 2+ videos procesa todos, o documenta/avisa el límite explícitamente.

- [ ] **3.2 Manejo de errores de OpenAI**
  - Objetivo: timeouts, rate limits, fallos de transcripción no rompen con 500 crudo.
  - Archivos: `process_ai_core/llm_client.py`, `process_ai_core/engine.py`, `api/routes/process_runs.py`.
  - Hecho: errores de OpenAI se traducen a respuestas/estados manejados; el usuario ve un mensaje útil.

- [ ] **3.3 Completar `GET /process-runs/{id}`**
  - Objetivo: implementar el endpoint (hoy stub 404).
  - Archivos: `api/routes/process_runs.py:428`.
  - Hecho: devuelve estado/artefactos del run; test.

- [ ] **3.4 Feedback de progreso en UI**
  - Objetivo: mostrar progreso durante la generación (puede tardar minutos con video).
  - Archivos: `ui/app/` (pantalla de creación/upload), consumir 3.3.
  - Hecho: el usuario ve estado en vivo, no un spinner mudo.
  - Depende de: 3.3.

---

## Etapa 4 — Dogfooding en Margay

- [ ] **4.1 Deploy de staging**
  - Objetivo: pila real (Next.js + FastAPI + Supabase Postgres) accesible como app desde el hub.
  - Hecho: process-ai accesible en su subdominio de staging vía el hub.
  - Depende de: Etapas 1–3.

- [ ] **4.2 Onboarding tenant Margay + documentar procesos**
  - Objetivo: tenant Margay con acceso al módulo; documentar 5–10 procesos internos reales.
  - Hecho: 5–10 procesos aprobados en el sistema.
  - Mide (para pricing): tiempo real por proceso y costo de IA por documento.

- [ ] **4.3 Loop de feedback**
  - Objetivo: registrar fricciones de UX y errores del uso real.
  - Hecho: lista priorizada de mejoras.

---

## Etapa 5 — Preparación piloto GPU (post-dogfooding)

- [ ] **5.1 Tenant GPU + acceso a `process-ai`**
- [ ] **5.2 Roles de estación** (pistero / encargado / gerencia) sobre el RBAC fino.
- [ ] **5.3 Procesos clave** (recepción de mercadería, arqueos, cierre de turno).

---

## Notas de implementación / deuda registrada

Observaciones surgidas durante la ejecución que NO bloquean la tarea actual pero hay que
resolver/tener presente:

- **[de 1.2] `WORKSPACE_URL` default = `http://localhost:8001`** (`api/workspace_client.py:19`).
  Aceptable en dev, pero en PROD la ausencia de la env var haría que todas las sesiones fallen
  con 503 contra localhost (falla cerrado, pero error operativo confuso). → En la **Etapa 2
  (config de envs)**: hacer que en prod falte `WORKSPACE_URL` falle ruidoso al arranque, no en
  cada request. Documentar la env en `.env.example`.
- **[de 1.2] Caché de contexto con TTL 30s** (`api/workspace_client.py:20`). Un cambio de
  permisos/acceso en workspace tarda hasta 30s en reflejarse acá. Trade-off consciente para el
  MVP. Tener presente cuando un cliente pida revocación inmediata o para auditorías.
- **[de 1.1] El `detail` del 404 en la auth vieja exponía el Supabase ID** — se resuelve al
  eliminar esa auth en 1.4 (no parchear antes).
- **[de Etapa 0] `.env.example` debe documentar `SUPABASE_JWKS_URL` y `WORKSPACE_URL`** cuando
  se ordene la config (Etapa 2). Sumar también `PROCESS_AI_APP_KEY` (default `process_ai`).
- **[de 1.4a] 1.4b es BLOQUEANTE, no cosmético.** El helper `resolve_tenant_workspace_id(ctx)`
  hoy devuelve `ctx.tenant.id` directo (placeholder con TODO). Como el `Workspace` interno usa
  un UUID local propio que NO coincide con el `tenant.id` de workspace, los endpoints migrados
  filtran por un ID inexistente → devuelven vacío hasta que 1.4b implemente el get-or-create /
  mapeo tenant→Workspace local. NO desplegar dogfooding sin 1.4b.
- **[de 1.4a] Path params `workspace_id` pendientes:** `api/routes/context_files.py` y
  `api/routes/operational_roles.py` exponen `/workspaces/{workspace_id}/...` (cambio de URL,
  coordinar con UI). Resolver junto con la migración de esos routers.
- **[de 1.4b] ORDEN: 1.6 debe ir ANTES que 1.7.** Al crear el Workspace local de un tenant
  nuevo (get_or_create) NO hay membership/rol local → `has_permission(...)` daría 403 para
  todos, incluso un `tenant_admin`. Falta el puente rol macro (`ctx.tenant_roles`) → permisos
  efectivos locales = tarea **1.6**. Sin 1.6, el test de aislamiento 1.7 choca con "nadie tiene
  permisos". Hacer 1.6 → 1.7.
- **[de 1.4b] Otro script de migración manual** (`tools/migrate_add_tenant_id_to_workspaces.py`)
  + columna `workspaces.tenant_id`. Sumar al backlog de consolidación en Alembic (2.2).
- **[de 1.6] Verificar en code review:** `sync_workspace_access` es best-effort (atrapa
  `except Exception` y solo loguea, `api/workspace_client.py:270`). Confirmar que un fallo
  PARCIAL del sync (crea User+Workspace pero falla al crear membership por un error que NO sea
  IntegrityError) haga rollback de TODA la transacción — no commit por paso. Si commiteara por
  paso, el usuario vería un 403 confuso (User existe, membership no). El `get_db_session()`
  como context manager debería garantizar el rollback atómico; verificarlo.
- **[de 1.7 — DEUDA DE SEGURIDAD, no MVP-blocker] Endpoints validan contra el workspace del
  RECURSO, no contra el tenant del CONTEXTO.** Ej: `GET /api/v1/folders/{folder_id}`
  (`api/routes/folders.py:297-298`) chequea permisos contra `folder.workspace_id`, no contra el
  tenant activo. NO explotable con usuarios de un solo tenant (B no tiene membership en
  workspace de A → 403). PERO un usuario con membership en MÚLTIPLES workspaces (superadmin, o
  alguien en Margay + GPU) podría leer recursos de cualquiera de sus workspaces vía URL directa,
  sin importar el tenant activo de la sesión. Auditar TODOS los endpoints que reciben un id de
  recurso (folder_id/document_id) y validar también que `recurso.workspace_id == workspace del
  contexto`. Patrón viejo que sobrevivió a 1.4a (que solo migró los workspace_id de query/body).
- **[de 1.7 — decisión de negocio, no seguridad] 403 vs 404 al acceder a recurso ajeno.**
  RESUELTO en 1.4c/1.4d: se unificó a 404 (no revela existencia entre tenants).
- **[de 1.4d] Artifacts protegidos con URLs firmadas (HMAC+TTL).** `api/artifact_signing.py`
  (sign/verify, compare_digest, falla sin secreto en prod). Endpoint exige `?token=`. Pendiente
  FRONTEND: la UI arma URLs de artifact a mano vía `getArtifactUrl(runId, filename)` (sin token)
  en ~8 lugares — deben usar la URL YA FIRMADA que devuelve el backend (`run.artifacts.pdf`).
  Lista en el reporte de 1.4d; reparar en el bloque frontend (1.8). Sin ese fix, los PDFs no
  cargan en la UI. Nuevas envs: `ARTIFACT_SIGNING_SECRET` (obligatoria en prod),
  `ARTIFACT_URL_TTL_SECONDS` (default 900) → documentar en `.env.example` (Etapa 2).
- **[recetas] Dominio "recetas" DESHABILITADO para el MVP.** `recipe_runs` desregistrado de
  `api/main.py` (router comentado + sacado del import). Razón: experimento B2C para otro nicho
  (app mobile, sin workspace/auth) → era un agujero de auth abierto. Código intacto en
  `api/routes/recipe_runs.py`. Reactivar SOLO tras darle el hardening de la Etapa 1
  (JWT+contexto+tenant+firma de artifacts). Verificado: la app carga y no expone rutas recipe.
- **[de 1.10] Workspace "sistema" DEPRECADO** + alta de clientes duplicada eliminada.
  `api/routes/superadmin.py` eliminado, `POST /workspaces` removido, `ui/app/clients/new` y
  `ui/app/superadmin/page.tsx` borradas. Frontend detecta superadmin por `role === 'superadmin'`
  (no por `workspace_type === 'system'`). Para limpiar la fila vieja:
  `python tools/cleanup_workspace_sistema.py --dry-run` y luego sin `--dry-run`.
- **[de 1.10 — DEUDA REGISTRADA] El parámetro nuevo `platform_is_superadmin` NO se está
  pasando desde ningún endpoint.** El camino "limpio" (superadmin sin membership local) está
  cableado en `process_ai_core/db/permissions.py` pero ningún caller lo usa
  (`grep "platform_is_superadmin" api/routes/*.py` → vacío). El sistema funciona hoy porque
  `sync_workspace_access` SIGUE creando una `WorkspaceMembership` con `role='superadmin'`
  cuando el claim incluye superadmin (vía el mapeo de 1.6), y `has_permission` la lee por el
  fallback legacy. Riesgo: si alguien cambia el mapeo de 1.6, los superadmin rompen sin que
  ningún test lo detecte (los tests nuevos usan el flag, que nadie pasa). Cerrar: pasar
  `platform_is_superadmin=("superadmin" in ctx.platform_roles)` desde los endpoints (o desde
  un wrapper común) y dejar de crear membership local de superadmin. Tarea acotada para
  cuando se ordene la config (Etapa 2) o como cierre de Etapa 1 si surge fricción antes.
- **[de 1.10] Housekeeping pendiente en `ui/lib/api.ts`:** `createB2BWorkspace` y
  `listAllWorkspaces` apuntan a endpoints eliminados; los callers ya no existen pero las
  funciones siguen. Eliminar en limpieza posterior. Y `ui/app/onboarding/page.tsx` (flujo B2C
  experimental) llama a `createWorkspace` que ya no existe — fuera de MVP, evaluar si se borra
  o queda colgada.
- **[de 1.8] DECISIÓN PENDIENTE — flujo de invitaciones de process-ai:**
  `ui/app/invitations/accept/[token]/page.tsx` usa activamente `syncUser` y `checkEmailExists`
  (endpoints de `api/routes/auth.py` que se planeó eliminar en 1.4). Por eso el agente de 1.8
  los conservó. Opciones: (a) migrar el flujo de invitaciones de process-ai al de
  margay-workspace (el hub ya lo tiene en `hub/ui/app/invitations/accept`) y eliminar esta
  pantalla + `auth.py` de process-ai; (b) conservar como está para el MVP y limpiar después.
  Mientras tanto `api/routes/auth.py` sigue registrado en `main.py` con `GET /user` que tiene
  `verify_signature=False` — ese bypass específico conviene cerrar independientemente.
- **[de 1.8] Errores TypeScript pre-existentes** (no introducidos por 1.8): `app/page.tsx`,
  `workspace/[id]/settings/page.tsx` (referencias a workspaces/ES5), `ManualEditorTiptap.tsx`
  (type de effect), `invitations/accept/[token]/page.tsx` (refreshWorkspaces con arg extra).
  Resolver en limpieza de código antes del dogfooding.

---

## Dependencias entre etapas (orden sugerido)

```
Etapa 0  →  Etapa 1  →  Etapa 2  →  Etapa 3  →  Etapa 4  →  Etapa 5
            (1.1→1.2→1.3/1.4/1.5→1.6→1.7 ; 1.8→1.9 en paralelo al backend)
```
- Etapa 2 (Postgres) puede solaparse con Etapa 1, pero el test de aislamiento (1.7) y la RLS
  conviene hacerlos ya sobre Postgres.
- Etapa 3 es independiente del bloque de auth; puede ejecutarse en paralelo por otro agente.
