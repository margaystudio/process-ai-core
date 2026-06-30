# Plan de pruebas — Fase 0 (Cimientos)

> **Alcance:** 0.1 Migraciones (Alembic) · 0.2 Abstracción de providers de IA · 0.3 Tipo de documento (catálogo + UI). Incluye los renombres `document_type→domain` y `document_kind→document_type`, y el baseline congelado.
>
> **Cómo usar:** ejecutá cada bloque en orden. Cada prueba tiene **pasos** y **resultado esperado**. Marcá ✅/❌ en la tabla final.

---

## 0. Prerrequisitos

```bash
cd /Users/santi/src/OSP/process-ai-core
# Backend usa el venv del repo:
.venv/bin/python --version          # 3.12.x
.venv/bin/alembic --version         # alembic instalado
# Docker para los PG efímeros de las pruebas de migración:
docker ps                           # daemon corriendo
```

- **DB de pruebas de migración:** Postgres **efímero** en Docker (aislado, descartable). No tocar sandbox/prod para esto.
- **DB para UI/E2E:** la que apunta tu `.env` (sandbox `nbigc…`).
- **Nota sobre la suite:** la suite completa **no corre limpia en local** por un tema preexistente del `.env` (fuerza `DATABASE_SCHEMA=process_ai` sobre tests que asumen SQLite). Esos fallos (`test_cross_tenant_isolation`, `test_membership_sync`, `test_superadmin_context`, `test_tenant_workspace_mapping`, `test_version_workflow`) son **preexistentes**, no de Fase 0.

Levantar un Postgres efímero (se reutiliza en el Bloque A):
```bash
docker run -d --rm --name pai_test_pg -e POSTGRES_PASSWORD=pai -e POSTGRES_DB=paidb -p 55440:5432 postgres:16-alpine
until docker exec pai_test_pg pg_isready -U postgres; do sleep 1; done
export TEST_URL="postgresql+psycopg://postgres:pai@localhost:55440/paidb"
```

---

## Bloque A — Migraciones (0.1) + baseline congelado

### A1. Base nueva desde cero → `upgrade head`
**Pasos:**
```bash
PROCESS_AI_BOOTSTRAP=1 ENVIRONMENT=test DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai \
  .venv/bin/alembic upgrade head
PROCESS_AI_BOOTSTRAP=1 ENVIRONMENT=test DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai \
  .venv/bin/alembic current
```
**Esperado:** corre **una sola** migración (`0001_baseline`); `current` muestra `0001_baseline (head)`.

```bash
docker exec pai_test_pg psql -U postgres -d paidb -At -c \
 "SELECT count(*) FROM information_schema.tables WHERE table_schema='process_ai' AND table_name<>'alembic_version';"
docker exec pai_test_pg psql -U postgres -d paidb -At -c \
 "SELECT column_name FROM information_schema.columns WHERE table_schema='process_ai' AND table_name='documents' AND column_name IN ('domain','document_type','document_kind') ORDER BY 1;"
```
**Esperado:** **23** tablas. Columnas de `documents`: `document_type` y `domain` (**NO** `document_kind`).

### A2. Sin drift (el esquema == los modelos)
```bash
PROCESS_AI_BOOTSTRAP=1 ENVIRONMENT=test DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai \
  .venv/bin/alembic revision --autogenerate -m "drift_check"
```
**Esperado:** el archivo generado en `alembic/versions/` tiene `def upgrade()` con **solo `pass`** (sin cambios). **Borralo** después: `rm alembic/versions/*drift_check*.py`.

### A3. Smoke test automatizado (upgrade + downgrade)
```bash
ALEMBIC_SMOKE_DATABASE_URL="$TEST_URL" .venv/bin/pytest tests/test_migrations_smoke.py -v
```
**Esperado:** **2 passed** (`test_upgrade_head_creates_module_schema`, `test_downgrade_base_drops_tables`).

### A4. "Migración futura" funciona sin trucos (valida el baseline congelado)
Esto prueba la promesa: agregar algo nuevo es flujo Alembic normal.
**Pasos:**
1. Agregá temporalmente una columna a un modelo, ej. en `process_ai_core/db/models.py` en `Workspace`: `test_col: Mapped[str | None] = mapped_column(String(10), nullable=True)`.
2. ```bash
   PROCESS_AI_BOOTSTRAP=1 DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai \
     .venv/bin/alembic revision --autogenerate -m "tmp_test_col"
   ```
   **Esperado:** el archivo generado tiene `op.add_column('workspaces', ... 'test_col' ...)` — **sin guards**.
3. ```bash
   PROCESS_AI_BOOTSTRAP=1 DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai .venv/bin/alembic upgrade head
   PROCESS_AI_BOOTSTRAP=1 DATABASE_URL="$TEST_URL" DATABASE_SCHEMA=process_ai .venv/bin/alembic downgrade -1
   ```
   **Esperado:** upgrade agrega la columna, downgrade la quita, sin errores.
4. **Revertí:** `git checkout process_ai_core/db/models.py` y `rm alembic/versions/*tmp_test_col*.py`.

### A5. Ambientes reales en `0001_baseline`, sin drift
```bash
# Sandbox (usa tu .env):
.venv/bin/alembic current          # -> 0001_baseline (head)
.venv/bin/alembic revision --autogenerate -m "drift_sandbox"   # upgrade() == pass ; luego borralo
```
**Esperado:** `current` = `0001_baseline`; drift vacío (el esquema de sandbox coincide con los modelos). *(Prod: ya verificado en `0001_baseline` vía Supabase.)*

---

## Bloque B — Abstracción de providers de IA (0.2)

### B1. Tests unitarios de providers
```bash
.venv/bin/pytest tests/test_ai_providers.py -v
```
**Esperado:** **6 passed** (complete_json pasa params correctos, fachada delega, factory elige modelo por tier).

### B2. `import openai` solo en el provider (DoD)
```bash
grep -rnE "import openai|from openai" --include="*.py" process_ai_core api | grep -v __pycache__
```
**Esperado:** **una sola línea** → `process_ai_core/ai/openai_provider.py`.

### B3. Comportamiento de generación sin cambios (E2E, requiere OPENAI_API_KEY)
**Pasos (UI):** levantá la app (Bloque C setup) → `/processes/new` → crear un proceso con un archivo de **texto** corto (o audio) → Generar.
**Esperado:** se genera el documento (transcribe/lee → JSON → PDF) igual que antes. El refactor de providers no rompió el pipeline.

### B4. Tier barato configurable (opcional)
**Pasos:** en `.env`, `OPENAI_MODEL_TEXT_CHEAP=gpt-4o-mini` → reiniciar backend.
**Esperado:** `get_llm_provider("cheap")` usa ese modelo; `get_llm_provider("strong")` sigue usando `OPENAI_MODEL_TEXT`. (Hoy ningún call-site usa "cheap", así que **no cambia el comportamiento** — es prep.)

---

## Bloque C — Tipo de documento (0.3)

### Setup app
```bash
# Backend (terminal 1):
.venv/bin/uvicorn api.main:app --reload --port 8000
# Frontend (terminal 2):
cd ui && npm run dev
```
> Asegurate de que el catálogo esté seedeado en la DB que use el backend:
> `.venv/bin/python tools/seed_catalogs.py` (sandbox ya tiene los 11 tipos).

### C1. Endpoint de catálogo
```bash
curl -s http://localhost:8000/api/v1/catalog/document_type | python3 -m json.tool
```
**Esperado:** **11** opciones (procedimiento, instructivo, manual_interno, manual_externo, politica, normativa, formulario, checklist, tramite, faq_validada, presupuesto) con `value`/`label`/`sort_order`.

### C2. Selector en el alta (UI)
**Pasos:** `/processes/new` → mirar el formulario.
**Esperado:** aparece el campo **"Tipo de documento"** (dropdown) con los 11 tipos; default **Procedimiento**.

### C3. Persistencia y ficha (UI)
**Pasos:** crear un proceso eligiendo, ej., **Política** → al terminar, ir a la ficha del documento.
**Esperado:** la ficha muestra **"Tipo de documento: Política"**. **NO** debe aparecer un campo "Tipo: process" (el discriminador interno está oculto).

### C4. Persistencia en API/DB
```bash
# tomá el id del documento creado (de la URL /documents/<id>) y:
curl -s -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/v1/documents/<id> | python3 -m json.tool | grep -E "document_type|domain"
```
**Esperado:** la respuesta trae `"document_type": "politica"` y `"domain": "process"`. (El token sale de la sesión Supabase; o verificá directo en DB.)

Verificación directa en DB (alternativa sin token):
```bash
docker exec ... # o psql a sandbox:
SELECT name, domain, document_type FROM process_ai.documents ORDER BY created_at DESC LIMIT 3;
```
**Esperado:** el documento nuevo tiene `domain='process'` y `document_type='politica'`.

---

## Bloque D — Renombres / regresión

### D1. Sin rastros de los nombres viejos
```bash
grep -rn "document_kind" --include="*.py" process_ai_core api | grep -v __pycache__   # esperado: vacío
grep -rEn "document_kind|documentKind|DocumentKind|DOCUMENT_KIND" ui/app ui/lib ui/components | grep -v node_modules  # esperado: vacío
```
**Esperado:** **0 ocurrencias** en código activo (los `tools/migrate_*.py` históricos pueden tener `document_type` viejo — se ignoran).

### D2. Catálogo migrado
```bash
# en la DB del backend:
SELECT domain, count(*) FROM process_ai.catalog_option WHERE domain LIKE 'document%' GROUP BY domain;
```
**Esperado:** una sola fila → `document_type | 11`. **No** debe existir `document_kind`.

### D3. Documentos existentes siguen funcionando (UI)
**Pasos:** abrir un documento que ya existía **antes** de Fase 0 (de la lista en `/workspace`).
**Esperado:** carga normal (el rename de columnas no rompió datos existentes); muestra su "Tipo de documento".

### D4. Happy path completo (UI)
**Pasos:** crear proceso (con tipo de documento) → enviar a aprobación → aprobar (con otro usuario/rol aprobador) → ver aprobado.
**Esperado:** todo el ciclo funciona; el rename `domain`/`document_type` no afectó generación, versionado ni aprobación.

### D5. Typecheck del frontend
```bash
cd ui && npx tsc --noEmit
```
**Esperado:** **0 errores**.

---

## Bloque E — Regresión backend acotada

```bash
.venv/bin/pytest tests/test_ai_providers.py tests/test_migrations_smoke.py \
  tests/test_storage.py tests/test_media_document_extraction.py tests/test_artifact_signing.py -q
```
> (`test_migrations_smoke` se saltea si no pasás `ALEMBIC_SMOKE_DATABASE_URL`.)
**Esperado:** todo **passed** (estos tocan los módulos modificados y no requieren la DB de la suite que falla por el `.env`).

---

## Limpieza
```bash
docker stop pai_test_pg          # elimina el PG efímero (--rm)
# borrá cualquier migración drift_* / tmp_* que haya quedado en alembic/versions/
ls alembic/versions/             # debe quedar solo: 0001_baseline.py, 0001_baseline.sql
```

---

## Checklist de resultados

| # | Prueba | Resultado |
|---|---|---|
| A1 | Base nueva: 23 tablas, `domain`+`document_type` | ⬜ |
| A2 | Drift vacío | ⬜ |
| A3 | Smoke test 2 passed | ⬜ |
| A4 | Migración futura sin guards (add/up/down) | ⬜ |
| A5 | Sandbox en `0001_baseline`, drift vacío | ⬜ |
| B1 | Providers: 6 passed | ⬜ |
| B2 | `import openai` solo en el provider | ⬜ |
| B3 | Generación E2E sin cambios | ⬜ |
| C1 | `GET /catalog/document_type` = 11 | ⬜ |
| C2 | Selector "Tipo de documento" en el alta | ⬜ |
| C3 | Ficha muestra el tipo; sin "Tipo: process" | ⬜ |
| C4 | API/DB persiste `document_type`+`domain` | ⬜ |
| D1 | 0 rastros de `document_kind` | ⬜ |
| D2 | Catálogo: solo `document_type`/11 | ⬜ |
| D3 | Documentos viejos cargan OK | ⬜ |
| D4 | Happy path crear→aprobar | ⬜ |
| D5 | Frontend `tsc` 0 errores | ⬜ |
| E | Regresión backend acotada passed | ⬜ |
