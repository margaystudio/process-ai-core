# Code Review & Plan a MVP — Process AI Core

> **Fecha:** 2026-05-28
> **Autor del review:** análisis técnico asistido (Claude) + Santiago (Margay Studio)
> **Decisiones de alcance tomadas en esta sesión:**
> - MVP = **documentación + workflow** (sin RAG ni auditorías en esta fase)
> - Primer despliegue = **dogfooding en Margay Studio**, luego piloto en GPU (estación de servicio)
> - RAG y auditorías trimestrales = **fase 2** (ver `docs/RAG_IMPLEMENTATION_PLAN.md`)
> - **Auth/usuarios:** integrar process-ai-core como **módulo (app `process-ai`) del control
>   plane `margay-workspace`**, NO arreglar una auth standalone. El tenant (organización /
>   estación) ya existe en margay-workspace. Ver §3.1 y `docs/INTEGRACION_MARGAY_WORKSPACE.md`.

---

## Estado de avance (actualizado 2026-07-10)

Contraste del plan contra el código real. Resumen: **~90% cerrado** — los 3 bloqueantes
críticos y las etapas duras (0/1/2) están resueltas.

**Bloqueantes (§3):**
- 3.1 Seguridad multi-tenant / JWT → ✅ **resuelto**: JWKS real en `api/dependencies.py`
  (sin `verify_signature:False`), `api/workspace_client.py` consume `GET /api/session/context`,
  identidad ya no viene por query param. Tests de aislamiento cross-tenant en `tests/`.
- 3.2 Secretos en git → ✅ **resuelto**: no hay `.env*` reales trackeados; `.env.production`
  en `.gitignore`.
- 3.3 SQLite → Postgres → ✅ **resuelto**: `DATABASE_URL` Postgres obligatorio, SQLite
  rechazado en prod/test; Alembic adoptado (migraciones 0001→0006).

**Etapas (§4):**
- Etapa 0 (Higiene) → ✅ (cola menor: borrar los ~21 `tools/migrate_*.py` que Alembic reemplazó).
- Etapa 1 (Integración margay-workspace + multi-tenant) → ✅.
- Etapa 2 (Postgres + Alembic) → ✅.
- Etapa 3 (Endurecer pipeline IA) → 🟡 **casi cerrada**:
  - ✅ Bug multi-video (`media.py`): `enrich_assets` ya no descarta assets tras el primer video.
  - ✅ Stub `GET /process-runs/{id}`: implementado (consulta real + aislamiento por tenant).
  - ✅ Manejo de errores de OpenAI: cliente con timeout + reintentos con backoff
    (rate-limit/5xx/timeout) y `AIProviderError` que hace diagnosticable un fallo de
    transcripción/generación. Vars `OPENAI_TIMEOUT_SECONDS` / `OPENAI_MAX_RETRIES`.
  - ⏸️ Feedback de progreso real en la UI durante generación (diferido; UI → margay-frontend).
- Etapa 4 (Dogfooding) → 🟢 pila deployada en prod; falta lo operativo (cargar procesos + feedback).
- Etapa 5 (Piloto GPU) → ⬜ no arrancada.

**Nota:** la **capa semántica (Tyto/RAG)** — que el plan ubicaba en *fase 2 (§5)* — ya está en
construcción (rama `feat/capa-semantica` + `feature/semantic-hardening`), con migraciones 0005/0006
aplicadas en sandbox y prod. O sea, se empezó fase 2 en paralelo.

---

## 1. TL;DR

El motor de generación de documentos con IA **funciona de punta a punta de verdad**
(audio/video/texto → JSON → Markdown → PDF), y todo el flujo editorial (versiones,
revisión, aprobación/rechazo, branding en PDF) está construido y con tests.

Lo que falta para vender **no es el "core de IA"** — es la **capa de SaaS confiable**:
seguridad multi-tenant, migración real a Postgres, e higiene de secretos. Las dos
features estrella del pitch comercial (chat RAG y auditorías trimestrales) están en
**0%**: solo viven en los docs.

Resumen: está hecho el ~70% difícil (la IA), falta el ~30% aburrido pero **innegociable**
para cobrarle a un tercero.

---

## 2. Qué está realmente construido

| Área | Estado | Evidencia |
|---|---|---|
| **Pipeline IA** | ✅ Funciona | Transcripción Whisper, video→pasos→frames con visión, generación de JSON — llamadas reales a OpenAI en `process_ai_core/llm_client.py`, orquestado en `process_ai_core/engine.py`. Modelos: `gpt-4.1-mini`, `gpt-4o-mini-transcribe`, `whisper-1`. |
| **Workflow editorial** | ✅ Funciona | Versionado con máquina de estados (DRAFT→IN_REVIEW→APPROVED/REJECTED/OBSOLETE), segregación de funciones (quien crea no aprueba), export PDF con branding. Tests sólidos en `tests/`. |
| **API** | 🟡 Amplia | 13 routers, CRUD completo en documentos/procesos/workspaces/invitaciones/suscripciones. `GET /process-runs/{id}` es un stub que siempre da 404 (`api/routes/process_runs.py:428`). |
| **Modelo de datos** | ✅ Rico | Workspaces (tenant), RBAC (roles/permisos), folders jerárquicos, versiones, suscripciones, invitaciones, AuditLog. Sin tabla de embeddings/RAG. |
| **Frontend Next.js** | ✅ Sustancial | ~20 pantallas reales (login, workspace, alta de proceso, upload, vista/corrección de documento, cola de aprobación, onboarding). Next 14 + Supabase + Tiptap. |
| **Auth / multi-tenancy** | 🔴 Inseguro hoy / solución clara | La auth actual (Supabase directo) está rota (ver §3.1), PERO la solución no es arreglarla aislada: **integrarse al control plane `margay-workspace`**, que ya resuelve identidad + tenant + acceso. El tenant ya existe en la plataforma. |
| **RAG / chat / auditorías** | 🔴 No existe | Cero código. Solo conceptual en docs. |
| **DB prod** | 🔴 Sin terminar | Corre en SQLite. 17 scripts de migración a mano (`tools/migrate_*.py`), sin Alembic. |

---

## 3. Bloqueantes críticos para vender

### 3.1 Seguridad multi-tenant rota (CRÍTICO) — y la solución es integrarse al control plane

**El problema (estado actual):**
- **JWT sin verificar firma:** en `api/dependencies.py:105` el token se decodifica con
  `jwt.decode(token, options={"verify_signature": False})`. Un token falsificado con
  cualquier `sub` es aceptado.
- **Identidad desde el cliente:** en `api/routes/documents.py:50` (y otros endpoints) el
  `user_id`/`workspace_id` contra el que se chequean permisos **viene como query param**.
- **Sin RLS** en la base.

**Combinados:** un cliente podría leer los documentos de **otra estación de servicio**.
Inaceptable para un SaaS que vende confidencialidad operativa.

**La solución NO es arreglar la auth aislada de process-ai-core.** Margay ya tiene un
**control plane multi-tenant**, `margay-workspace`, que es la fuente de verdad de identidad,
tenant y acceso a apps. process-ai-core debe integrarse como **módulo** (app `process-ai`):

- **Identidad:** validar el **JWT de Supabase** con **JWKS (ES256)**, `aud="authenticated"`,
  exigir `sub`+`exp`. Código de referencia listo para copiar: `margay-workspace/app/services/auth.py`.
- **Tenant + acceso:** resolver vía `GET /api/session/context` de margay-workspace, que
  devuelve `user`, `tenant` (activo), `tenants[]` y `applications[]`. **El tenant ya existe**
  (tablas `tenants`/`tenant_users` en el schema `workspace`) — la organización/estación =
  `tenant` de margay-workspace.
- **`user_id` y `tenant`** se derivan del token/contexto, **nunca** del cliente.
- **Permisos finos** (sobre documentos/versiones) quedan en process-ai-core.

Plan detallado de integración: `docs/INTEGRACION_MARGAY_WORKSPACE.md`.

> **Nota sobre la auth propia actual** (login con Supabase, OAuth Google/Facebook,
> invitaciones, tabla `users` local en process-ai-core): queda **subsumida** por el control
> plane. El login y el portal de apps los maneja `margay-hub`; process-ai-core deja de ser
> responsable de la gestión de usuarios y pasa a confiar en el contexto de sesión.

### 3.2 Secretos en git

`.env.production` está trackeado (con `DATABASE_URL` de prod). Purgar del historial y
**rotar** credenciales antes de cualquier exposición.

### 3.3 SQLite en vez de Postgres

No aguanta concurrencia ni el modelo SaaS. Falta el corte real a Supabase Postgres + un
sistema de migraciones de verdad (Alembic).

---

## 4. Plan a MVP vendible (~7–8 semanas)

> Filosofía: **no construir features nuevas.** Endurecer y estabilizar el motor que ya
> funciona. El orden prioriza arrancar dogfooding en Margay pronto, sin arrastrar deuda
> que después duela en GPU.

### Etapa 0 — Higiene y base (1 semana)
1. **Purgar secretos de git.** Sacar `.env.production` del tracking, `.gitignore` correcto, **rotar** credenciales expuestas.
2. **Consolidar branches.** ~11 ramas de feature sin mergear (GDD3/4/6/8/10/12...). Decidir cuáles entran a `develop` y cuáles se descartan.
3. **Limpiar código muerto.** `doc_engine.py` duplica el builder/parser que ahora vive en `domains/processes/`. `.pyc` huérfanos (`models_v2`, `context_files`, `operational_roles`).
4. **Quitar logging sensible.** Los `logger.info` en `api/dependencies.py` filtran prefijos de tokens y emails.

### Etapa 1 — Integración con margay-workspace + seguridad multi-tenant (2–2.5 semanas) — *bloqueante*
> Detalle paso a paso en `docs/INTEGRACION_MARGAY_WORKSPACE.md`.
1. **Registrar el módulo** `process-ai` en margay-workspace (`workspace.applications`) y habilitarlo por tenant (`tenant_applications`).
2. **Validar el JWT de Supabase con JWKS (ES256)** en `api/dependencies.py:105` (reemplazar `verify_signature: False`). Copiar el patrón de `margay-workspace/app/services/auth.py`.
3. **Resolver identidad + tenant + acceso vía `GET /api/session/context`** (cachear con TTL corto). `user_id` y `tenant` salen de acá, **nunca** del query param (`api/routes/documents.py:50` y todos los demás).
4. **Mapear organización ↔ tenant:** alinear el `workspace_id` interno de process-ai-core con el `tenant.id`/slug de margay-workspace.
5. **Auditoría de aislamiento por endpoint** + test "tenant A no puede leer datos de tenant B".
6. **(Defensa en profundidad) RLS en Postgres** una vez migrado.

### Etapa 2 — Postgres real + migraciones (1 semana)
1. **Corte de SQLite → Supabase Postgres** como base por defecto en dev y prod.
2. **Adoptar Alembic.** Reemplazar los 17 scripts manuales de `tools/migrate_*.py`.
3. **Seed reproducible:** catálogos, planes de suscripción, roles/permisos base.

### Etapa 3 — Endurecer el pipeline IA (1 semana)
1. **Bug multi-video:** `process_ai_core/media.py:500` retorna después del primer video y descarta los demás en silencio.
2. **Manejo de errores de OpenAI:** timeouts, rate limits, fallos de transcripción.
3. **Completar el stub** `GET /process-runs/{id}` (`api/routes/process_runs.py:428`).
4. **Feedback de progreso** en la UI durante la generación (puede tardar minutos con video).

### Etapa 4 — Dogfooding en Margay (1 semana + uso continuo)
1. **Deploy de staging** con la pila real (Next.js + FastAPI + Supabase Postgres), accesible como app desde margay-hub.
2. **Tenant Margay** en margay-workspace + acceso al módulo `process-ai`; documentar 5–10 procesos reales internos.
3. **Loop de feedback:** registrar fricciones de UX y errores.

### Etapa 5 — Preparación piloto GPU (post-dogfooding)
**Tenant GPU** en margay-workspace (probablemente ya existe), acceso al módulo `process-ai`,
roles de estación (pistero / encargado / gerencia) sobre el RBAC fino de process-ai-core, y
procesos clave (recepción de mercadería, arqueos, cierre de turno).

---

## 5. Fuera de alcance del MVP (fase 2)

- **RAG / chat sobre documentos** → ver `docs/RAG_IMPLEMENTATION_PLAN.md`
- **Auditorías trimestrales** (calificar procesos, hallazgos, acciones correctivas, informe)

Son las features de mayor valor del pitch, pero son trabajo nuevo y no bloquean el primer
despliegue interno.
