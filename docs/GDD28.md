# GDD-28 — Wizard Nuevo documento: evidencias con procesamiento real (badges)

> **Tarea:** procesar evidencias al subirlas y mostrar badges reales en Step 1 del wizard `/documents/new`.  
> **Estado:** implementado (Bloque C — enhancement).  
> **Alcance:** backend (`process_ai_core/`, `api/`) + frontend (`ui/`).

---

## Objetivo

Reemplazar el badge fijo **"Listo para usar"** por un flujo real alineado al prototipo: al agregar una evidencia, el sistema la procesa (transcripción, extracción de texto, OCR) y muestra chips verdaderos (`Audio transcripto`, `OCR completado`, `Idioma: ES`, `N págs`, etc.). La generación del borrador puede **reusar** el texto ya extraído para evitar reprocesar.

---

## Antes / después (Step 1)

| Aspecto | Antes | Después |
|---------|-------|---------|
| Al agregar evidencia | Solo se guardaba el `File` local | Se llama a `POST /api/v1/evidence/process` |
| Badge en card | Siempre `"Listo para usar"` | `"Procesando…"` → chips reales o error |
| Datos mostrados | Hardcodeados / inventados | Solo metadata devuelta por el backend |
| Al generar borrador | `createProcessRun` reprocesaba todo | Envía `{field}_extracted_text` si ya hay texto |

---

## Decisión técnica — OCR (C1)

**Estrategia barata/local** (spec Fase 0.1, épica 1.2):

1. PDF con capa de texto → extracción con **pypdf** (sin OCR).
2. PDF escaneado / imagen → fallback **Tesseract local** vía `pytesseract`.
3. PDF escaneado renderizado con **PyMuPDF** (`fitz`) página por página.

Requiere el **binario de Tesseract** en el sistema. En Windows, configurar `TESSERACT_CMD` en `.env`.

---

## Archivos modificados / nuevos

### Backend

| Archivo | Cambio |
|---------|--------|
| `process_ai_core/ai/ocr_provider.py` | **Nuevo** — `TesseractOCRProvider` |
| `process_ai_core/ai/factory.py` | `get_ocr_provider()` |
| `process_ai_core/config.py` | `tesseract_cmd`, `ocr_languages` |
| `process_ai_core/evidence_processing.py` | **Nuevo** — procesamiento por tipo + `EvidenceResult` |
| `process_ai_core/media.py` | Reuso de `extracted_text_override` en `enrich_assets` |
| `api/routes/evidence.py` | **Nuevo** — `POST /api/v1/evidence/process` |
| `api/routes/process_runs.py` | Form fields `*_extracted_text` por tipo de archivo |
| `api/main.py` | Registro del router `evidence` |
| `pyproject.toml` | `pytesseract`, `pymupdf`, `Pillow`, `langdetect` |
| `.env.example` | `TESSERACT_CMD`, `OCR_LANGUAGES` |

### Frontend

| Archivo | Cambio |
|---------|--------|
| `ui/components/documents/wizard/data.ts` | `Evidence` extendido + `evidenceChips()` |
| `ui/lib/api.ts` | `processEvidenceFile()` |
| `ui/components/documents/wizard/NuevoDocumentoWizard.tsx` | `addEvidence` async + `generateDraft` con texto extraído |
| `ui/components/documents/wizard/EvidenceCard.tsx` | Estados processing / done / error / no_text |
| `ui/components/documents/wizard/AddEvidenceModal.tsx` | Copy actualizado (procesa al agregar) |
| `ui/lib/__tests__/evidenceChips.test.ts` | **Nuevo** — 5 tests unitarios |

---

## C1 — Endpoint de procesamiento por archivo

### Ruta

```
POST /api/v1/evidence/process
Content-Type: multipart/form-data
Authorization: Bearer {JWT}
```

**Campos:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `file` | UploadFile | Archivo (máx. 25 MB) |
| `kind` | string | `audio` \| `video` \| `image` \| `text` |

**Respuesta:**

```json
{
  "status": "done",
  "extracted_text": "...",
  "metadata": {
    "language": "ES",
    "duration_seconds": 92,
    "pages": 42,
    "used_ocr": false
  },
  "error": null
}
```

**Valores de `status`:**

| status | Significado |
|--------|-------------|
| `done` | Texto extraído/transcripto OK |
| `no_text` | Procesado pero sin contenido útil (ej. imagen vacía) |
| `error` | Fallo esperado (Tesseract ausente, `.doc` no soportado, etc.) |

### Procesamiento por tipo (`evidence_processing.py`)

| kind | Pipeline | Metadata típica |
|------|----------|-----------------|
| `audio` | `transcribe_audio` (Whisper vía OpenAI) | `language`, `duration_seconds` (ffprobe) |
| `video` | ffmpeg → audio → transcribe | `language`, `duration_seconds` |
| `text` | pypdf / python-docx / UTF-8; PDF escaneado → OCR | `pages`, `language`, `used_ocr` |
| `image` | OCR Tesseract directo | `used_ocr`, `language` |

**Detección de idioma:** `langdetect` sobre el texto extraído (mín. ~20 caracteres).

### Providers reutilizados

- `TranscriptionProvider` → `get_transcription_provider()` / `llm_client.transcribe_audio`
- `OCRProvider` → `get_ocr_provider()` / `TesseractOCRProvider`
- Extracción documentos → `_extract_text_from_document` (`media.py`)

---

## C2 — Badges reales en la UI

### Flujo al agregar evidencia

```
AddEvidenceModal → onAdd(EvidenceInput)
  └─ NuevoDocumentoWizard.addEvidence
       ├─ Agrega card con processingStatus: "processing"
       └─ processEvidenceFile(file, fileType)
            └─ POST /api/v1/evidence/process
                 └─ Actualiza card: done | no_text | error + metadata
```

### Estados en `EvidenceCard`

| `processingStatus` | UI |
|--------------------|-----|
| `processing` | Spinner + **"Procesando…"** |
| `done` / `no_text` | Chips de `evidenceChips(evidence)` |
| `error` | Badge rojo **"Error al procesar"** (+ tooltip con mensaje) |

### Chips por tipo (`evidenceChips`)

| Tipo | Chips (ejemplos) |
|------|------------------|
| Audio / Video | `Audio transcripto`, `Idioma: ES`, `1:32` |
| PDF | `Texto extraído` o `OCR completado`, `PDF procesado`, `42 págs` |
| Documento | `Texto extraído`, `Idioma: ES` |
| Imagen | `OCR completado`, `1 imagen` — o `Sin texto detectado` |

**Regla:** mostrar lo real o ocultarlo; nunca inventar datos (ej. no más `"Generado hace 18 segundos"` hardcodeado).

---

## Reuso del texto en `createProcessRun`

Al pulsar **"Crear borrador"**, además de los archivos se envían campos paralelos por índice:

| Campo archivo | Campo texto extraído |
|---------------|----------------------|
| `audio_files` | `audio_files_extracted_text` |
| `video_files` | `video_files_extracted_text` |
| `image_files` | `image_files_extracted_text` |
| `text_files` | `text_files_extracted_text` |

Si `processingStatus === 'done'` y hay `extractedText`, se envía; si no (aún procesando o error), se envía `""` y el backend **reprocesa** como fallback.

En `enrich_assets`, si `metadata.extracted_text_override` está presente, se usa en lugar de transcribir/extraer de nuevo (audio, text, image).

---

## Flujo de datos completo

```
Step 1 — Agregar evidencia
  └─ POST /api/v1/evidence/process
       └─ EvidenceCard muestra badges reales

Step 1 — Crear borrador
  └─ POST /api/v1/process-runs
       ├─ archivos (audio_files, text_files, …)
       ├─ *_extracted_text (texto pre-procesado)
       └─ enrich_assets usa extracted_text_override cuando existe

Step 2 / 3 — sin cambios (GDD-26, GDD-27)
```

---

## Criterios de aceptación

| CA | Estado |
|----|--------|
| Subir audio devuelve transcripción + idioma + duración | ✅ |
| Subir imagen devuelve OCR (con Tesseract instalado) | ✅ |
| Subir PDF devuelve texto + páginas | ✅ |
| Badges del prototipo son verdaderos (no `"Listo para usar"`) | ✅ |
| `createProcessRun` reutiliza texto ya extraído | ✅ |
| Fallback si el usuario genera antes de terminar el procesamiento | ✅ |
| `npx tsc --noEmit` en verde | ✅ |
| Tests `evidenceChips` (5) en verde | ✅ |

---

## Verificación manual (UI)

1. Levantar backend + frontend (sesión activa).
2. Ir a **`/documents/new`**.
3. **Agregar evidencia** → elegir tipo y archivo.
4. Observar: **"Procesando…"** → chips reales (o error explícito).
5. DevTools → Network: `POST .../api/v1/evidence/process` con respuesta `{ status, metadata }`.
6. **Crear borrador** → verificar en Network que `process-runs` incluye `*_extracted_text`.
7. Flujo completo Step 2 → Step 3 sin regresiones.

### Prerrequisitos por tipo

| Tipo | Requiere |
|------|----------|
| Audio / Video | `OPENAI_API_KEY`, ffmpeg/ffprobe |
| Imagen / PDF escaneado | Tesseract + `TESSERACT_CMD` (Windows) |
| PDF / Documento digital | pypdf / python-docx (pip) |

---

## Verificación automatizada

```powershell
# Frontend — badges
cd ui
npm test -- lib/__tests__/evidenceChips.test.ts
npx tsc --noEmit

# Backend — extracción base (relacionado)
cd ..
python -m pytest tests/test_media_document_extraction.py -q
```

---

## Fuera de alcance

- Persistencia de evidencias como entidad en BD (Fase 1 parkeada).
- OCR cloud (Vision/Textract) — queda detrás de `OCRProvider` pero apagado.
- Detección de idioma persistida más allá de la respuesta del endpoint.
- Tests de integración del endpoint `/evidence/process` (backlog recomendado).

---

## Relación con GDD-26 y GDD-27

| GDD | Bloque | Qué cablea |
|-----|--------|------------|
| GDD-26 | A | Step 2 — revisión y edición del borrador |
| GDD-27 | B | Step 3 — enviar a aprobación |
| **GDD-28** | **C** | **Step 1 — evidencias con badges reales** |

Con GDD-28, el wizard deja de simular el procesamiento de insumos y alinea la UX del Step 1 al prototipo, sin bloquear el flujo end-to-end ya logrado en los pasos 2 y 3.
