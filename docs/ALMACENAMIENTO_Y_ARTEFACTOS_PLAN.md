# Plan de Implementación — Almacenamiento, Artefactos y Fuentes

> **Fecha:** 2026-06-24
> **Estado:** Diseño cerrado, listo para implementar.
> **Alcance:** Durabilidad y defensa de auditoría del PDF aprobado, las imágenes y las
> fuentes de origen. Deja sentadas las fundaciones que asume `docs/RAG_IMPLEMENTATION_PLAN.md`.
> **No incluye:** el RAG en sí (ver ese doc; es un track aparte).

---

## 0. Resumen ejecutivo

Hoy el contenido canónico vive bien (Postgres, `document_versions.content_json/markdown/html`,
inmutable al aprobar). Pero los **artefactos renderizados** (PDF + imágenes de evidencia/frames)
viven en **disco local efímero** (`output/{run_id}/...`), referenciados por path relativo. En
un deploy containerizado (GCP) eso desaparece en cada redeploy → el PDF aprobado y sus imágenes
se pierden y el endpoint firmado devuelve 404. Además, las **fuentes de origen** se borran sin
dejar rastro de auditoría (`Run.input_manifest_json` existe pero nadie lo escribe).

Tres objetivos:
1. **Durabilidad + auditoría**: el PDF de la versión aprobada y sus imágenes pasan a object
   storage, con hash SHA-256 y trazabilidad.
2. **Referencias estables**: md y json dejan de usar paths relativos al `run_id` efímero.
3. **Trazabilidad de fuentes sin guardar los bytes pesados**: manifiesto + hash + transcripción.

---

## 1. Principios

- **El contenido canónico (JSON + MD/HTML) no se toca**: ya está en Postgres y es la fuente
  de verdad y del RAG.
- **El PDF y las imágenes NO son fuente de verdad**: son render determinístico. Pero el PDF/imagen
  de la versión **APROBADA** sí es artefacto de auditoría → se congela y se guarda con hash.
- **Lo no-aprobado es efímero**: drafts y runs intermedios se renderizan en temp y no se persisten.
- **Las fuentes crudas pesadas se borran por default**; se retiene manifiesto + transcripción.
  Conservar los originales es opt-in (feature de plan / toggle por workspace).

---

## 1.bis Decisiones tomadas y pre-condición

**Pre-condición — sistema NO productivo:** no hay datos de auditoría que preservar. Por lo tanto:
- **Sin backfill** de versiones ya aprobadas. No se re-renderizan PDFs viejos.
- **Sin fallback de transición** disco→storage. Corte limpio.
- Se **borra `output/` completo** y los datos de prueba (sqlite/Postgres dev) antes de arrancar.

**Decisión — backend de blobs: Supabase Storage.**
Razones: ya estás en Supabase para auth (JWT/JWKS) y Postgres, y el RAG usará pgvector en el
mismo Postgres. Mantener los blobs en Supabase Storage minimiza piezas de infra, comparte el
mismo `workspace_id` para aislamiento, trae signed URLs nativas y es S3-compatible. El costo de
los PDFs aprobados es despreciable (~25 KB c/u). **Escape hatch:** como todo pasa por la interfaz
`BlobStorage`, si el costo crece (sobre todo por originales retenidos/video) mover ese tipo de blob
a GCS más adelante es cambiar una implementación, sin tocar el resto del código.

**Decisión — tabla `Artifact`: se elimina.**
El artefacto auditable pasa a vivir en columnas de `document_versions` (PDF aprobado + hash). Los
drafts/runs se renderizan en temp y no se persisten, así que no hay nada que indexar en una tabla
de artefactos. La migración la dropea (no hay datos productivos que preservar).

---

## 2. Fases

### Fase A — Abstracción de almacenamiento (fundación, sin cambio de comportamiento)

**Objetivo:** desacoplar el código del filesystem local.

- Nuevo paquete `process_ai_core/storage/` con interfaz `BlobStorage`:
  `put(key, bytes, content_type)`, `get(key)`, `exists(key)`, `delete(key)`,
  `signed_url(key, ttl)`.
- Implementaciones:
  - `LocalDiskStorage` → comportamiento actual (`output_dir`), para local/test.
  - `SupabaseStorage` → producción (decisión tomada; ver §1.bis).
- Selección por config: `STORAGE_BACKEND=local|supabase` en `process_ai_core/config.py`.
- **Esquema de claves canónico** (reemplaza `output/{run_id}/...`):
  ```
  workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/document.pdf
  workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/assets/{asset_id}.{ext}
  ```
  Los runs efímeros siguen en temp local; solo lo que se aprueba va a una clave canónica.
- Refactor `api/routes/artifacts.py`: en vez de leer `Path(output_dir)/run_id/filename`,
  resolver vía `BlobStorage`. La firma HMAC propia se mantiene, o se delega en la signed URL
  del proveedor (decisión menor; recomendado mantener la HMAC propia para no acoplar la UI).

**Archivos:** `process_ai_core/storage/*` (nuevo), `config.py`, `api/routes/artifacts.py`.
**Migración:** ninguna.

---

### Fase B — Congelar artefactos al aprobar (auditoría)

**Objetivo:** que el PDF e imágenes que el cliente aprobó sean inmutables y recuperables byte a byte.

- **Migración** `002_add_approved_artifacts.sql`:
  - Agrega columnas en `document_versions`:
    - `pdf_storage_key   TEXT NULL`
    - `pdf_sha256        VARCHAR(64) NULL`
    - `pdf_generated_at  TIMESTAMP NULL`
    - `pdf_render_engine VARCHAR(50) NULL`  (ej. `weasyprint-60.1`, para auditar drift)
  - **Dropea la tabla `artifacts`** (sin datos productivos que preservar; ver §1.bis).
- En la transición a `APPROVED` (hoy en `api/routes/documents.py` / `validations.py`):
  1. Renderizar el PDF desde `content_html` (fuente de verdad de export, `content_source.py`).
  2. Subir a la clave canónica de la versión vía `BlobStorage`.
  3. Calcular SHA-256 y persistir las 4 columnas.
  4. Subir también las imágenes que la versión referencia a `.../assets/`.
- **Quitar la persistencia en disco del PDF/JSON/MD de runs NO aprobados**: hoy
  `documents.py:951-1001` escribe a `output/{run_id}/` y crea filas `Artifact` para cada run.
  Para draft/in_review eso se renderiza en `tempfile` y no se persiste. Eliminar también las
  llamadas a `create_artifact` / uso del modelo `Artifact` en todo el código (`db/helpers.py`,
  rutas) en línea con el drop de la tabla.

**Archivos:** `api/routes/documents.py`, `api/routes/validations.py`, `process_ai_core/db/models.py`
(quitar `Artifact`), `process_ai_core/db/helpers.py`, `migrations/002_*.sql`.

---

### Fase C — Imágenes como ciudadanas de primera clase + referencias estables

**Objetivo:** que md y json no dependan de paths relativos efímeros y que el JSON vincule
imagen ↔ paso (clave para el asistente y RAG).

- **Asset con ID estable**: cada imagen recibe un `asset_id` y se referencia por clave
  canónica, no por `assets/evidence/img1.png` relativo al run.
- **Markdown**: en vez de `![](assets/evidence/img1.png)`, guardar un marcador de asset
  (ej. `![](asset://{asset_id})`) que se resuelve a signed URL al renderizar PDF o al servir.
- **JSON**: agregar la referencia **estructurada** de la imagen dentro del paso/sección al que
  pertenece (no la mención de texto suelta actual en `material_referencia`). Esto lo necesita
  el asistente proactivo ("en este paso mirá esta captura") y un RAG multimodal futuro.
- **Versionado de assets**: hoy `documents.py:1772` hace `shutil.copytree` de assets entre runs.
  Reemplazar por copia de claves en `BlobStorage` ligada al `version_id`.

**Archivos:** renderer/builder de `process_ai_core/domains/processes/`, `export/pdf_*`,
`api/routes/documents.py`.

---

### Fase D — Manifiesto de fuentes + transcripción + retención

**Objetivo:** trazabilidad de origen sin cargar los binarios pesados.

- **Poblar `Run.input_manifest_json`** (hoy queda en `{}`). Por cada fuente subida, antes de
  borrar el temp dir (`process_runs.py:113`, `documents.py:836`):
  ```json
  {"sources":[{"id":"vid1","kind":"video","filename":"...","size":...,
    "sha256":"...","duration_s":...,"uploaded_by":"user_id"}]}
  ```
- **Persistir transcripciones / texto extraído** de audio y video (texto barato; es la evidencia
  real del contenido y futuro insumo de RAG). En el manifiesto o en una tabla lateral.
- **Retención de originales = opt-in**: por default se borran los binarios (comportamiento actual,
  correcto por costo y PII). Workspaces que lo requieran (auditoría regulada) pueden activar
  retención N meses en cold storage → feature de plan en `SubscriptionPlan.features_json`.

**Archivos:** `api/routes/process_runs.py`, `api/routes/documents.py`, opcional migración.

---

### Fase E — Ciclo de vida y contabilidad de storage

- Job/TTL que limpia temp dirs huérfanos y drafts viejos.
- Poblar `WorkspaceSubscription.current_storage_gb` (existe, no se calcula) sumando assets +
  originales retenidos + context_files. **No** contar el PDF aprobado contra el límite (es ~25 KB,
  es el core de la propuesta de valor — no se recorta en ningún plan).
- `max_storage_gb` se aplica a context_files + evidencia + originales retenidos.

---

### Fase F — Tests

Foco en lo que toca auditoría y multi-tenancy (no cobertura exhaustiva):

- **Storage abstraction:** suite que corre contra `LocalDiskStorage` y `SupabaseStorage` con el
  mismo contrato (`put`/`get`/`signed_url`/`delete`/`exists`) — un solo set de tests parametrizado.
- **Inmutabilidad + hash:** al aprobar, el PDF se sube una vez; `pdf_sha256` coincide con el byte
  stream subido; re-aprobar o regenerar no muta el PDF de una versión ya `APPROVED`.
- **Aislamiento multi-tenant:** las claves canónicas incluyen `workspace_id`; un workspace no puede
  resolver una signed URL de otro (test sobre la firma HMAC de `artifact_signing.py` + clave).
- **Referencias estables (Fase C):** `asset://{id}` resuelve a la clave correcta; el md/json de una
  versión no apunta a paths del `run_id`.
- **Manifiesto (Fase D):** tras un run, `input_manifest_json` queda poblado con sha256 por fuente y
  el temp dir se borró.

---

## 3. Secuenciación recomendada

0. **Limpieza inicial** (§1.bis): borrar `output/` y datos de prueba. Sistema no productivo → corte limpio.
1. **A + B** (durabilidad + auditoría). Lo urgente e independiente.
2. **C** (referencias estables de imágenes) — habilita el resto y limpia deuda de render.
3. **D** (manifiesto + transcripción) — barato, alto valor de auditoría.
4. **E** (lifecycle/contabilidad) — cuando haya volumen real.
5. **F** (tests) — en paralelo, junto con cada fase.

El RAG (su propio plan) puede arrancar en paralelo a D/E, pero se beneficia de C.

---

## 4. ¿Esto deja listo el RAG?

**Parcialmente.** Esto construye las *fundaciones*, no el RAG. Mapeo contra
`docs/RAG_IMPLEMENTATION_PLAN.md`:

| Requisito del RAG | Lo cubre este plan? |
|---|---|
| Fuente canónica chunkable (`content_json` de versión APROBADA) | ✅ Ya existe; intacto |
| Indexar solo `APPROVED` + `is_current` | ✅ Disciplina de versionado ya existe |
| Metadata para visibilidad por rol (`folder_path`, `audience`, permisos) | ✅ Ya en el modelo (`folder_permissions`, `operational_roles`) |
| JSON con imágenes vinculadas a pasos (multimodal / "mirá esta captura") | ⚠️ **Lo agrega la Fase C** |
| Transcripciones como evidencia indexable | ⚠️ **Lo agrega la Fase D** |
| `content_hash` para reindexar solo lo que cambió | ⚠️ Conviene calcularlo al aprobar (Fase B lo facilita) |
| **pgvector** habilitado en Supabase | ❌ Pendiente — es del plan de RAG (Fase R0) |
| Tabla `document_chunks` + embeddings | ❌ Pendiente — plan de RAG |
| Pipeline indexación + retrieval + generación con citas | ❌ Pendiente — plan de RAG |

**Conclusión:** con A–D quedás con la *materia prima* impecable (contenido aprobado, inmutable,
con imágenes y transcripciones bien referenciadas y trazables). El RAG en sí —pgvector,
`document_chunks`, embeddings, retrieval permission-aware, UI del chat— sigue siendo el track
de `RAG_IMPLEMENTATION_PLAN.md`. Lo único de *este* plan que es prerequisito real para que el RAG
salga limpio es **la Fase C** (vínculo imagen↔paso en el JSON) y **la Fase D** (transcripciones);
el resto del RAG no depende del refactor de storage y puede empezar cuando quieras.
