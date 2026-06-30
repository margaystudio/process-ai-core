# Resumen de cambios en `develop` — santidalto (Santiago Dalto)

> **Generado:** 2026-06-25  
> **Base de comparación:** `develop` vs `main`  
> **Autor principal del análisis:** commits de `santidalto <santiagodalto@gmail.com>`  
> **Tu usuario git:** Ignacio Azaretto (`ignacioazaso@gmail.com`)

---

## 1. Panorama general

| Métrica | Valor |
|---------|-------|
| Commits de santidalto en `develop` (no en `main`) | **61** |
| Commits tuyos (Ignacio) en el mismo rango | **38** |
| Archivos tocados en el diff total `main...develop` | **~249** |
| Líneas (+ / −) | **+23.494 / −11.106** |
| Estado de tu rama local | Al día con `origin/develop` |

**Importante:** `develop` no es solo trabajo de tu compañero. Hay merges y features tuyas de marzo (GD7, GD10, GD17, GDD3, roles, etc.). Este documento se centra en lo que hizo **santidalto**, que es la mayor parte del delta reciente.

---

## 2. Lo más reciente (24–25 jun 2026) — prioridad alta

Estos **10 commits** son el bloque más nuevo y el que más impacto tiene en backend e infra. Si retomás el proyecto hoy, **empezá por acá**.

| Commit | Fecha | Descripción |
|--------|-------|-------------|
| `3b1dc94` | 2026-06-24 | Almacenamiento durable de artefactos + auditoría de PDF y fuentes |
| `51fa4b3` | 2026-06-24 | Validar carpeta antes del pipeline + fix N+1 y doble-creación en UI |
| `f9d9251` | 2026-06-24 | Auth: leer apps desde `tenant_modules` (ya no `applications` deprecated) |
| `a3b6113` | 2026-06-24 | Sync sube solo artefactos servibles, no originales pesados |
| `bdc22d4` | 2026-06-25 | Storage organizado por tenant: `workspaces/{ws}/...` |
| `ec78c05` | 2026-06-25 | Contabilidad de uso: `current_storage_gb` por tenant |
| `b6b66eb` | 2026-06-25 | Liberar bucket al borrar + prune de huérfanos (E3) |
| `a7f3f31` | 2026-06-25 | Enforcement de `max_storage_gb` + editor-uploads por tenant |
| `2b154cd` | 2026-06-25 | Refactor: `documents.py` → paquete de sub-routers |
| `2542e41` | 2026-06-25 | Validación del output LLM con esquema Pydantic + reintento |

**Impacto aproximado del bloque:** 49 archivos, +5.190 / −2.788 líneas (entre `4b8e411` y `2542e41`).

---

## 3. Detalle por área (bloque jun 24–25)

### 3.1 Storage y artefactos (cambio estructural)

**Problema que resuelve:** PDFs e imágenes vivían en disco local efímero (`output/{run_id}/...`). En Cloud Run eso se pierde en cada redeploy → 404 en endpoints firmados y sin auditoría.

**Solución implementada:**

- Nuevo paquete `process_ai_core/storage/`:
  - `base.py` — interfaz `BlobStorage`
  - `local.py` — desarrollo/tests
  - `supabase.py` — producción
  - `factory.py`, `keys.py`, `accounting.py`, `sync.py`
- Claves canónicas por tenant:
  ```
  workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/document.pdf
  workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/assets/{asset_id}.{ext}
  ```
- Config: `STORAGE_BACKEND=local|supabase` en `process_ai_core/config.py`
- Al aprobar versión: PDF con hash SHA-256 en columnas de `document_versions`
- Tabla `artifacts` **eliminada** (migración `003_drop_artifacts_table.sql`)
- Manifiesto de fuentes: `process_ai_core/input_manifest.py`, `assets_json.py`
- Herramientas CLI:
  - `tools/prune_storage.py` — limpiar huérfanos en bucket
  - `tools/recompute_storage.py` — recalcular uso por tenant
- Límites: enforcement de `max_storage_gb` + uploads del editor
- Al borrar documento: libera espacio en bucket

**Migraciones SQL nuevas:**

| Archivo | Qué hace |
|---------|----------|
| `migrations/002_approved_pdf_artifact.sql` | Columnas PDF aprobado + hash en `document_versions` |
| `migrations/003_drop_artifacts_table.sql` | Drop de tabla `artifacts` |

**Tests nuevos/actualizados:**

- `tests/test_storage.py`
- `tests/test_storage_limit.py`
- `tests/test_prune.py`
- `tests/test_freeze_integration.py`
- `tests/test_input_manifest.py`
- `tests/test_assets_json.py`

**Doc de diseño (leer primero):** `docs/ALMACENAMIENTO_Y_ARTEFACTOS_PLAN.md`

---

### 3.2 Refactor API de documentos

El monolito `api/routes/documents.py` (~2.600 líneas) se partió en:

```
api/routes/documents/
├── __init__.py      # router principal
├── _helpers.py      # utilidades compartidas
├── crud.py          # CRUD de documentos
├── content.py       # contenido / editor
├── versions.py      # versiones y aprobación
└── runs.py          # ejecuciones de pipeline
```

También se extrajeron módulos auxiliares:

- `api/routes/_freeze.py` — congelar artefactos al aprobar
- `api/routes/_run_paths.py` — resolución de paths de runs

**Si tocás endpoints de documentos, ya no busques en un solo archivo.**

---

### 3.3 Auth y multi-tenant

- `api/workspace_client.py`: Process AI lee módulos/apps desde **`tenant_modules`**, no desde la tabla `applications` (deprecated).
- Alineado con la integración Margay Workspace (JWT/JWKS, contexto de tenant).

---

### 3.4 Carpetas (fix UI + backend)

- Validación de carpeta **antes** de arrancar el pipeline (evita runs inválidos).
- Fixes en UI:
  - `ui/components/processes/FolderCrud.tsx`
  - `ui/components/processes/FolderTree.tsx`
- Problemas corregidos: consultas N+1 y doble creación de carpetas.

---

### 3.5 LLM

- `process_ai_core/llm_client.py` y `process_ai_core/engine.py`:
  - Output del LLM validado contra esquema **Pydantic**
  - **Reintento** automático si la respuesta no cumple el schema

---

## 4. Trabajo anterior de santidalto (jun 2–9)

### 4.1 Integración Margay Workspace + multi-tenant (jun 2–4)

| Commit | Tema |
|--------|------|
| `111691d` | Etapa 1: integración margay-workspace, seguridad multi-tenant, setup local |
| `ef45cf5` | Config general workspace, selector tenant, perfil IA |
| `c6c3352` | Migración a Supabase Postgres, latencia dev remoto |
| `3ed9f48` | Fixes build producción + deploy |
| `52358bd` | SSO: `next` usa `NEXT_PUBLIC_SITE_URL` (no host interno Cloud Run) |
| `0a62177` | `connect_timeout` en engine DB (warmup no cuelga arranque) |
| `ad8e069` / `a90a98a` | `/login` redirige al hub; logout limpio |
| `34ea3bc` | Docs: `AMBIENTES`, `DB_SETUP`, `.env.production.example`, `bootstrap_db` |

**Docs clave:**

- `docs/AMBIENTES.md` — mapeo LOCAL / TEST / PROD, Supabase sandbox vs prod
- `docs/DB_SETUP_FROM_SCRATCH.md`
- `docs/INTEGRACION_MARGAY_WORKSPACE.md`

### 4.2 Migración UI a margay-ui (jun 8)

Migración masiva del frontend Process AI al design system **margay-ui**:

- Fase 0: cablear margay-ui v0.4.0
- Chrome: AppShell + Topbar + Sidebar
- Pantallas migradas: home, dashboards, workspace, onboarding, profile, review, editor Tiptap, modales, settings, listas, etc.
- Re-sync margay-ui 0.5.0 (switcher de organización en topbar)
- Fix: superadmin bypass en dashboards
- Tokens: `ui/shared/ui/tokens.css`, `tailwind-preset.ts`

### 4.3 Branding y local dev (jun 9)

- Backend local en puerto **8300** (evita choque con insights)
- Favicon Process AI (no logo Margay genérico)
- Logo Margay oficial en sidebar

### 4.4 Seguridad multi-tenant (may 28–29)

| Commit | Tema |
|--------|------|
| `70323ae` | JWT con JWKS + contexto de sesión workspace |
| `3f9f6f2` | Gate `require_process_ai_access` |
| `08f25f1` | `workspace_id` derivado del contexto en routers |
| `70d3ddc` | Mapeo tenant → Workspace get-or-create |
| `b55bdab` | Sync `WorkspaceMembership` local desde contexto tenant |
| `6cb7277` | Auth en CRUD de carpetas |

### 4.5 Merges y fixes históricos (mar 5–20)

Incluye merges de PRs (GDD1, GD7, GD10, GDD8, recover-operational-roles, GDD3, GDD6, GDD12) y fixes de DB/UI hechos por santidalto en esa etapa.

---

## 5. Qué NO es de santidalto (pero está en `develop`)

Commits tuyos (Ignacio) — marzo 2026, entre otros:

- GD17: PDF/DOCX en carga de archivos
- GD10: grabación de audio online
- GD7: teléfono celular en perfil
- GDD3, GDD8: roles, solo lectura, permisos carpetas
- Branding PDF, preguntas abiertas, visualizador PDF, etc.

Si necesitás separar responsabilidades en code review, filtrá por autor:

```powershell
git log develop --not main --author="santidalto" --oneline
git log develop --not main --author="Ignacio" --oneline
```

---

## 6. Por dónde seguir (guía práctica)

### Paso 1 — Entender el contexto (30 min)

1. Leer `docs/ALMACENAMIENTO_Y_ARTEFACTOS_PLAN.md` (diseño del storage)
2. Leer `docs/AMBIENTES.md` (cómo correr local vs test)
3. Revisar `.env.example` — nuevas vars de storage (`STORAGE_BACKEND`, Supabase, etc.)

### Paso 2 — Levantar el entorno

```powershell
cd C:\Users\Usuario\Desktop\process-Ia-Core\process-ai-core
git checkout develop
git pull origin develop
# Configurar .env según docs/AMBIENTES.md y DB_SETUP_FROM_SCRATCH.md
# Aplicar migraciones 002 y 003 si tu DB local no las tiene
```

Backend local corre en puerto **8300** (no el puerto anterior).

### Paso 3 — Explorar el código nuevo

| Si vas a trabajar en… | Empezá por… |
|----------------------|-------------|
| Storage / PDFs / buckets | `process_ai_core/storage/`, `api/routes/_freeze.py`, `docs/ALMACENAMIENTO_Y_ARTEFACTOS_PLAN.md` |
| API documentos | `api/routes/documents/` (no `documents.py`) |
| Límites por tenant | `process_ai_core/storage/accounting.py`, `tests/test_storage_limit.py` |
| Auth / tenant | `api/workspace_client.py`, `docs/INTEGRACION_MARGAY_WORKSPACE.md` |
| UI | `ui/shared/ui/`, componentes bajo `ui/components/processes/` |
| LLM / pipeline | `process_ai_core/engine.py`, `process_ai_core/llm_client.py` |
| Carpetas | `FolderCrud.tsx`, `FolderTree.tsx`, routers de folders en `api/routes/` |

### Paso 4 — Validar que entendés los cambios

```powershell
# Ver diff del bloque más reciente (storage + refactor)
git diff 4b8e411..2542e41 --stat

# Correr tests de storage
pytest tests/test_storage.py tests/test_storage_limit.py tests/test_prune.py -q
```

### Paso 5 — Decidir tu próxima tarea

Preguntas útiles antes de codear:

1. ¿Tu tarea toca **artefactos/PDF/storage**? → leé el plan de almacenamiento y probá con `STORAGE_BACKEND=local` primero.
2. ¿Tu tarea toca **endpoints de documentos**? → buscá en el sub-router correcto (`crud`, `content`, `versions`, `runs`).
3. ¿Tu tarea es **UI**? → usá componentes margay-ui; no copies estilos legacy.
4. ¿Deploy? → verificá vars Supabase del mismo proyecto (JWKS, URL, keys) según `AMBIENTES.md`.

---

## 7. Variables y config nuevas (referencia rápida)

Revisar en `.env.example` y `.env.production.example`:

- `STORAGE_BACKEND` — `local` | `supabase`
- Credenciales Supabase Storage (bucket, service role)
- `NEXT_PUBLIC_SITE_URL` — SSO redirect correcto
- Backend local: puerto **8300**

---

## 8. Riesgos / puntos de atención

1. **Migraciones pendientes:** si tu DB local es anterior a junio, aplicá `002` y `003` antes de probar aprobación de documentos.
2. **Tabla `artifacts` eliminada:** cualquier código que la referencie está obsoleto.
3. **`documents.py` ya no existe** como monolito — imports rotos si tenés branches viejos.
4. **`applications` deprecated** — la fuente de verdad de módulos es `tenant_modules`.
5. **Storage en prod:** PDFs aprobados dependen de Supabase Storage; sin bucket configurado → 404 post-deploy.
6. **Límites de storage:** tenants con `max_storage_gb` pueden bloquear uploads; ver `current_storage_gb`.

---

## 9. Comandos útiles

```powershell
# Commits recientes de tu compañero
git log develop --not main --author="santidalto" --oneline -20

# Archivos que cambió en el último bloque
git diff 4b8e411..2542e41 --name-only

# Diff de un archivo específico
git diff main...develop -- process_ai_core/storage/

# Quién tocó qué en develop
git log develop --not main --format="%an" | Sort-Object -Unique
```

---

## 10. Próximos tracks (según docs del repo)

- **RAG:** `docs/RAG_IMPLEMENTATION_PLAN.md` (asume las fundaciones de storage ya hechas)
- **Pricing/límites comerciales:** `docs/ESTRATEGIA_COMERCIAL_Y_PRICING.md`
- **MVP por etapas:** `docs/MVP_TAREAS_POR_ETAPA.md`

---

*Documento generado a partir del historial git `develop` vs `main`. Para actualizarlo, re-ejecutar el análisis git o pedir un refresh.*
