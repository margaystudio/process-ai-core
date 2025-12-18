# process-ai-core
Motor de generación automática de documentación de procesos a partir de audio, video e imágenes.

---

## 🎯 Objetivo

`process-ai-core` es un **core técnico** para transformar conocimiento operativo informal
(videos, audios, capturas de pantalla y notas) en **documentación de procesos estructurada**, consistente y reutilizable.

El sistema:
- Transcribe audio y video
- Infiere pasos operativos automáticamente
- Extrae capturas relevantes desde videos
- Incorpora evidencia visual aportada por el usuario
- Genera documentación en **JSON → Markdown → PDF**
- Soporta **perfiles de documento** (operativo / gestión)

El usuario **no necesita saber cuántos pasos hay ni cómo documentarlos**: el sistema infiere la estructura.

---

## 🧠 Principio de diseño

> El humano aporta material bruto.  
> El sistema infiere estructura, pasos y evidencia.

---

## 🧱 Arquitectura general

```
input/
 ├── audio/
 ├── video/
 ├── evidence/
 └── text/

        │
        ▼
[ ingest / discover_raw_assets ]
        │
        ▼
[ media.enrich_assets ]
        │
        ▼
[ build_prompt_from_enriched ]
        │
        ▼
[ LLM → JSON estructurado ]
        │
        ▼
[ parse_process_document ]
        │
        ▼
[ render_markdown + DocumentProfile ]
        │
        ▼
[ Pandoc → PDF ]
```

---

## 📁 Estructura del proyecto

```
process_ai_core/
├── run_demo.py
├── cli.py
├── media.py
├── ingest.py
├── llm_client.py
├── doc_engine.py
├── document_profiles.py
├── domain_models.py
├── config.py
├── export/
│   └── pdf_pandoc.py
├── db/
│   ├── database.py
│   └── models_*.py
└── prompt_context.py
```

---

## 📥 Inputs soportados

### Audio (`input/audio/`)
- `.m4a`, `.mp3`, `.wav`
- Se transcribe completo

### Video (`input/video/`)
- `.mp4`, `.mov`, `.mkv`
- Transcripción con timestamps
- Inferencia automática de pasos
- Extracción de frames relevantes

### Evidencia visual (`input/evidence/`)
- Imágenes sueltas del usuario
- No se asignan manualmente a pasos

### Texto (`input/text/`)
- Notas, procedimientos previos

---

## 🧬 Enriquecimiento de assets

Para cada tipo de asset:
- **audio**: transcripción simple
- **video**: audio → pasos → frames → selección
- **image**: evidencia visual
- **text**: lectura directa

---

## 📄 Renderizado

El documento final se genera en:
- JSON estructurado
- Markdown
- PDF (Pandoc + XeLaTeX)

---

## 🛠️ Requisitos

- Python 3.10+
- ffmpeg
- pandoc + xelatex
- OPENAI_API_KEY en `.env`

---

## 🚀 Ejecución demo

```bash
python tools/run_demo.py \
  --process-name "Nombre del proceso" \
  --mode gestion \
  --audience direccion \
  --detail-level estandar \
  --formality alta
```

---

## ✨ Filosofía

Documentar procesos no debería ser un trabajo manual.
El valor está en el conocimiento, no en el formateo.
