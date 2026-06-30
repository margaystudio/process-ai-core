# Hoja de especificación — Fase 0 (Cimientos) + Fase 1 (Evidencias)

> **Destino:** historias listas para tickets de Jira asignables a devs **junior**.
> **Criterio de tamaño:** cada historia es de 0.5–3 días. Si una crece, se parte.
> **Base de código:** rama `develop`. Backend FastAPI + SQLAlchemy en `process_ai_core/` y `api/`. Frontend Next.js 14 en `ui/`.
> **Convención de PR:** rama `feat/<key>-slug` → PR a `develop`. Cada historia entra con tests + lint en verde.

---

## 0. Decisiones de producto a cerrar ANTES de tomar los tickets marcados 🔒

Estos tickets están bloqueados hasta que producto confirme. Pongo el **default recomendado** para no frenar; si se acepta el default, se desbloquean.

| # | Decisión | Resolución |
|---|---|---|
| D1 | Catálogo cerrado de **tipos documentales** | ✅ **CERRADO.** Blueprint §5 + `presupuesto`: `procedimiento, instructivo, manual_interno, manual_externo, politica, normativa, formulario, checklist, tramite, faq_validada, presupuesto`. *(Nota: `presupuesto` es transaccional; a futuro puede pedir campos propios.)* |
| D2 | ¿Persistimos los archivos de input / construimos evidencias? | ✅ **CERRADO — v1 = input-only.** Los archivos siguen siendo **temporales** (se borran tras generar, como hoy). Para regenerar, el usuario **recarga los archivos**. **Evidencia rica y "adjuntos lite" quedan PARKEADOS** para una iteración futura. → **Toda la Fase 1 sale del primer lote.** |
| D3 | **OCR**: cloud vs. local | ✅ **CERRADO — barato/local.** Estrategia: *texto embebido del PDF (gratis, pypdf/pdfplumber) → si no hay, Tesseract local (gratis)*. Cloud (Vision/Textract) queda detrás de `OCRProvider` pero **apagado**. Cero costo variable. *(Aplica recién cuando se haga Importación; no es del primer lote.)* |
| D4 | ¿Formalizamos **migraciones con Alembic** o seguimos con SQL crudo + `create_all`? | ✅ **CERRADO — Alembic.** Es prerrequisito de las tablas nuevas. |

---

## FASE 0 — CIMIENTOS

Habilita todo lo demás. Casi todo es refactor/infra que extiende lo que ya existe.

### Épica 0.1 — Migraciones versionadas (Alembic) 🔒D4

**Contexto:** hoy las tablas se crean por `Base.metadata.create_all` y solo hay 3 SQL crudos en `migrations/`. Para sumar tablas nuevas (`evidence`, etc.) sin romper prod necesitamos migraciones versionadas y reproducibles.

#### 0.1.1 — Integrar Alembic al proyecto · `S` (1d)
- **Archivos:** nuevo `alembic.ini`, `migrations/env.py` (o `alembic/`), apuntando al `Base` de `process_ai_core/db/models.py` y al schema `process_ai`.
- **Pasos:** instalar alembic; configurar `target_metadata = Base.metadata`; `version_table_schema = "process_ai"`; leer URL de `process_ai_core/config.py`.
- **Criterios de aceptación:**
  - `alembic upgrade head` corre limpio en una BD vacía y deja el schema `process_ai` con todas las tablas actuales.
  - `alembic revision --autogenerate` detecta cambios del modelo.
  - Los 3 SQL existentes (001–003) quedan representados como baseline (migración inicial "stamp").
- **DoD:** README de `migrations/` actualizado con el comando de correr migraciones. Sin romper el arranque de la API.
- **Dependencias:** ninguna. **Es la primera tarea de todo el plan.**

#### 0.1.2 — Baseline + smoke test de migración en CI · `S` (0.5d)
- **Criterios:** un test/script que levanta BD limpia, corre `upgrade head`, valida que existen las tablas clave (`documents`, `document_versions`, …).
- **Dependencias:** 0.1.1.

---

### Épica 0.2 — Abstracción de providers de IA

**Contexto:** `process_ai_core/llm_client.py` está atado a OpenAI directamente. El Technical Architecture pide interfaces (`LLMProvider`, `TranscriptionProvider`, `EmbeddingProvider`, `OCRProvider`, `VisionProvider`) para poder meter embeddings, OCR y la estrategia "IA cara/barata". Esto es prerrequisito de Tyto (embeddings) y de OCR (Fase 1).

> **Nota para el jr:** esto es un refactor de *extracción de interfaz*, sin cambiar comportamiento. Riesgo: tocás el corazón de la generación. Hacelo con tests antes y después.

#### 0.2.1 — Definir interfaces de providers · `S` (1d)
- **Archivos:** nuevo `process_ai_core/ai/providers.py` (Protocols/ABCs): `LLMProvider.complete()/complete_json()`, `TranscriptionProvider.transcribe()`, `EmbeddingProvider.embed(texts)->vectors`, `OCRProvider.extract_text(bytes)->str`, `VisionProvider.pick_frame(...)`.
- **Criterios:** interfaces tipadas con docstrings; sin implementación todavía.
- **Dependencias:** ninguna.

#### 0.2.2 — `OpenAIProvider` implementa las interfaces (mover lógica actual) · `M` (2d)
- **Archivos:** `process_ai_core/ai/openai_provider.py`; refactor de `llm_client.py` para delegar.
- **Criterios:**
  - Toda la lógica OpenAI actual (texto, Whisper, vision-frame) vive detrás de la interfaz.
  - Los call-sites (`engine.py`, builders en `domains/`) usan la interfaz, no `openai` directo.
  - **Comportamiento idéntico:** los tests existentes de generación pasan sin cambios.
- **DoD:** no queda `import openai` fuera de `openai_provider.py`.
- **Dependencias:** 0.2.1.

#### 0.2.3 — Factory + selección por config (modelo caro/barato) · `S` (1d)
- **Archivos:** `process_ai_core/ai/factory.py`; settings en `process_ai_core/config.py`.
- **Criterios:** `get_llm_provider(tier="strong"|"cheap")` devuelve el provider según `.env`; documentado en `.env.example`.
- **Dependencias:** 0.2.2.

---

### Épica 0.3 — Catálogo de tipos documentales 🔒D1

**Contexto:** hoy el modelo solo distingue `process` vs `recipe` (polimorfismo de `Document`). El producto necesita el catálogo del Blueprint. Esto NO reemplaza el polimorfismo; agrega un atributo `document_type_code` clasificatorio.

#### 0.3.1 — Tabla/enum de tipos documentales + columna en `documents` · `M` (1.5d)
- **Archivos:** `process_ai_core/db/models.py`; migración Alembic; seed.
- **Pasos:** crear `document_kinds` (o enum) con el catálogo D1; agregar `documents.document_kind` (nullable, default `procedimiento`).
- **Criterios:**
  - Migración aplica y seedea el catálogo.
  - `GET /catalog/document-kinds` devuelve la lista (reusar `api/routes/catalog.py`).
- **Dependencias:** 0.1.1.

#### 0.3.2 — Selector de tipo documental en alta de documento · `S` (1d)
- **Archivos:** `ui/app/processes/new/page.tsx`, nuevo `ui/components/processes/DocumentKindSelector.tsx`, `ui/lib/api.ts`.
- **Criterios:** el usuario elige tipo documental al crear; se persiste; se muestra en la ficha `ui/app/documents/[id]/page.tsx`.
- **Dependencias:** 0.3.1.

---

## FASE 1 — EVIDENCIAS DE PRIMERA CLASE  ⏸️ PARKEADA (no va en el primer lote)

> **DECISIÓN (D2):** para v1 los archivos de input siguen siendo **temporales** (input-only). No se construye la entidad `evidence` ni "adjuntos lite". Si el usuario quiere regenerar, **recarga los archivos**. Toda esta fase queda como backlog para una iteración futura; el contenido de abajo se conserva como referencia de lo que implicaría.
>
> **Conocido a revisitar:** la UI actual de "reusar archivos del run anterior" / regenerar-solo-con-instrucciones es inconsistente con input-only (busca originales ya borrados). Ajuste futuro: que la regeneración pida recargar archivos.

**Contexto del pilar (referencia, no se implementa en v1):** hoy los archivos subidos son input efímero de un `run` y se consumen al generar. El modelo conceptual ("El documento conectado") exige que las **evidencias persistan, se asocien al documento y se sigan sumando**. Esta fase crea esa entidad y su UX.

### Épica 1.1 — Modelo + API de evidencias 🔒D2

#### 1.1.1 — Tabla `evidence` + migración · `M` (1.5d)
- **Archivos:** `process_ai_core/db/models.py`; migración Alembic.
- **Campos:** `id`, `document_id` (FK), `workspace_id`, `kind` (audio|video|pdf|image|interview|note|other), `original_filename`, `storage_key`, `sha256`, `content_type`, `size_bytes`, `extracted_text` (nullable), `transcript_json` (nullable), `language` (nullable), `processing_status` (pending|processing|done|error), `metadata_json`, `added_by` (FK users), `added_at`.
- **Criterios:** migración aplica; relación `Document.evidences`; índice por `document_id`.
- **Dependencias:** 0.1.1.

#### 1.1.2 — Endpoints CRUD de evidencias · `M` (2d)
- **Archivos:** nuevo `api/routes/documents/evidence.py` (registrar en `api/routes/documents/__init__.py`). **Tomar como molde `api/routes/folders.py` y `context_files.py`** (ya hacen upload multipart + storage + permisos).
- **Endpoints:**
  - `POST /documents/{id}/evidence` (multipart) → sube a storage (reusar `process_ai_core/storage/`), calcula sha256, crea fila `pending`.
  - `GET /documents/{id}/evidence` → lista.
  - `GET /documents/{id}/evidence/{eid}/download` (URL firmada, como artifacts).
  - `DELETE /documents/{id}/evidence/{eid}` → borra fila + blob (reusar liberación de bucket que ya existe).
- **Criterios:** respeta permisos por workspace/carpeta; contabiliza storage (reusar `storage/accounting.py`); audit log en `audit_logs`.
- **Dependencias:** 1.1.1.

#### 1.1.3 — Procesamiento asíncrono de evidencia (transcribir/extraer) · `M` (2d)
- **Contexto:** al subir, disparar extracción según `kind` reusando lo que ya existe en `llm_client.py` (Whisper para audio/video) + OCR (1.2) para pdf/image.
- **Criterios:** tras procesar, `extracted_text`/`transcript_json`/`language` se llenan y `processing_status=done`; en error queda `error` con mensaje en `metadata_json`. (MVP: puede ser síncrono en background task de FastAPI; no exige cola.)
- **Dependencias:** 1.1.2, 1.2.1.

---

### Épica 1.2 — OCR + detección de idioma 🔒D3

#### 1.2.1 — `OCRProvider` (cloud) detrás de la interfaz · `M` (2d)
- **Archivos:** `process_ai_core/ai/ocr_provider.py`; config + `.env.example`.
- **Criterios:** `extract_text(bytes, content_type)` devuelve texto para PDF escaneado e imagen; PDFs con capa de texto se leen sin OCR (vía extractor de texto, más barato); test con un PDF de muestra.
- **Dependencias:** 0.2.1.

#### 1.2.2 — Detección de idioma del texto extraído · `S` (0.5d)
- **Criterios:** función que detecta idioma (lib liviana tipo `langdetect` o el propio LLM) y lo guarda en `evidence.language`.
- **Dependencias:** 0.2.1.

---

### Épica 1.3 — UI "Evidencias del documento"

**Contexto UX (prototipo):** sección "Evidencias del documento" en la ficha; "Agregar evidencia" con opciones grabar audio / capturar / importar archivo; drag&drop; estados de procesamiento ("Transcribiendo…", "OCR completado"); las evidencias quedan listadas y se siguen sumando.

#### 1.3.1 — Cliente API de evidencias · `S` (0.5d)
- **Archivos:** `ui/lib/api.ts` (funciones `listEvidence`, `uploadEvidence`, `deleteEvidence`, `downloadEvidence`).
- **Dependencias:** 1.1.2.

#### 1.3.2 — Sección Evidencias en la ficha del documento · `M` (2d)
- **Archivos:** `ui/app/documents/[id]/page.tsx`; nuevo `ui/components/documents/EvidencePanel.tsx`. **Molde:** `ui/components/processes/FileList.tsx` + `FileItem.tsx` (ya muestran archivos con icono/estado).
- **Criterios:** lista evidencias con tipo, nombre, estado de procesamiento y fecha; agregar (drag&drop + botón), eliminar con confirmación; refresca al terminar el procesamiento (polling simple).
- **Dependencias:** 1.3.1.

#### 1.3.3 — Grabar audio in-app (opcional, separable) · `M` (2d)
- **Archivos:** nuevo `ui/components/documents/AudioRecorder.tsx` (MediaRecorder API) → sube como evidencia `audio`.
- **Criterios:** graba, previsualiza, sube; permisos de micrófono manejados; fallback claro si el navegador no soporta.
- **Dependencias:** 1.3.2. *(Candidata a dejar para una segunda iteración si hay que priorizar.)*

---

### Épica 1.4 — Reencuadre del alta como "crear desde evidencias" 🔒D2

#### 1.4.1 — `/processes/new` usa evidencias persistentes · `M` (2d)
- **Contexto:** hoy `/processes/new` sube archivos sueltos al run. Cambiar para que (a) cree el documento, (b) suba las evidencias a la entidad `evidence`, (c) genere la versión usando esas evidencias.
- **Archivos:** `ui/app/processes/new/page.tsx`, `ui/components/processes/FileUpload*.tsx`; backend `api/routes/documents/runs.py` para que el run lea evidencias del documento.
- **Criterios:** tras crear, las evidencias quedan visibles en la ficha (Épica 1.3) y re-consultables; generar una nueva versión puede reusar evidencias ya cargadas + nuevas.
- **Dependencias:** 1.1.2, 1.3.2.

---

## Orden sugerido de ejecución — PRIMER LOTE = SOLO FASE 0

```
0.1.1 ─► 0.1.2
   └─► 0.3.1 ─► 0.3.2
0.2.1 ─► 0.2.2 ─► 0.2.3
```

**Primer ticket que toma un jr:** `0.1.1` (Alembic). **En paralelo** otro jr puede tomar `0.2.1` (interfaces de providers). `0.3.1` (tipos documentales) arranca apenas esté `0.1.1`.

> Fase 1 (evidencias) queda parkeada (ver banner arriba). El segundo lote se define cuando se elija el próximo diferencial: **Tyto MVP** o **Importación** (ambos dependen de 0.1 y 0.2, por eso Fase 0 va primero igual).

## Reparto sugerido por seniority (primer lote)
- **Jr puro:** 0.1.2, 0.3.1, 0.3.2 (extienden patrones existentes 1:1; user-visible en el caso de tipos documentales).
- **Jr con acompañamiento / semi-senior:** 0.1.1 (Alembic), 0.2.1 / 0.2.2 / 0.2.3 (refactor del core de IA).

## Resumen de esfuerzo (primer lote)
- **Fase 0:** ~8 días-dev (0.1: 1.5d · 0.2: 4d · 0.3: 2.5d). ≈ **2 jrs × 1 semana** con dependencias respetadas.
- *Fase 1 (parkeada): ~13.5 días-dev si algún día se retoma.*

> **Nota sobre 0.2 (abstracción de providers):** es prep para el próximo diferencial (embeddings de Tyto / OCR de Importación). Hacerla ahora, con el código chico, conviene; pero si se prefiere lote mínimo, 0.2 puede esperar hasta confirmar Tyto vs Importación. 0.1 y 0.3 son valor sí o sí.
