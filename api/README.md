# Process AI Core API

API HTTP REST para generar documentación de procesos asistida por IA.

## Instalación

```bash
# Instalar dependencias (incluye FastAPI, Pydantic, Uvicorn)
pip install -e .

# O instalar solo las dependencias de la API
pip install fastapi pydantic uvicorn[standard]
```

## Ejecución

**IMPORTANTE**: Ejecutar desde la raíz del proyecto (donde está la carpeta `api/`)

```bash
# Opción 1: Usar el script helper
./run_api.sh

# Opción 2: Ejecutar manualmente desde la raíz
cd /path/to/process-ai-core
uvicorn api.main:app --reload --port 8000

# Opción 3: Si estás en otro directorio, especificar el path
PYTHONPATH=/path/to/process-ai-core uvicorn api.main:app --reload --port 8000
```

La API estará disponible en `http://localhost:8000`

## Endpoints

### POST `/api/v1/process-runs`

Crea una nueva corrida del pipeline de documentación.

**Request (multipart/form-data):**

- `process_name` (string, requerido): Nombre del proceso
- `mode` (string, opcional): `operativo` o `gestion` (default: `operativo`) - Define la audiencia del documento
- `detail_level` (string, opcional): Nivel de detalle
- `context_text` (string, opcional): Contexto adicional del proceso (texto libre)
- `audio_files[]` (file[], opcional): Archivos de audio (.m4a, .mp3, .wav)
- `video_files[]` (file[], opcional): Archivos de video (.mp4, .mov, .mkv)
- `image_files[]` (file[], opcional): Archivos de imagen (.png, .jpg, .jpeg, .webp)
- `text_files[]` (file[], opcional): Archivos de texto (.txt, .md)

**Response:**

```json
{
  "run_id": "uuid-del-run",
  "process_name": "Nombre del proceso",
  "status": "completed",
  "artifacts": {
    "json": "/api/v1/artifacts/{run_id}/process.json",
    "markdown": "/api/v1/artifacts/{run_id}/process.md",
    "pdf": "/api/v1/artifacts/{run_id}/process.pdf"
  }
}
```

### POST `/api/v1/process-runs/{run_id}/generate-pdf`

Genera un PDF desde un run existente (sin ejecutar el pipeline completo).

Este endpoint es **más rápido y económico** que crear un nuevo run, ya que:
- No requiere llamadas a OpenAI
- Solo ejecuta Pandoc para convertir Markdown a PDF
- Reutiliza el markdown y las imágenes ya generadas

**Parámetros:**
- `run_id`: ID de la corrida existente (debe tener un `process.md` generado)

**Response:**

```json
{
  "run_id": "uuid-del-run",
  "status": "completed",
  "pdf_url": "/api/v1/artifacts/{run_id}/process.pdf",
  "message": "PDF generado exitosamente"
}
```

**Errores:**
- `404`: Si el run_id no existe o no tiene markdown
- `500`: Si falla la generación del PDF (Pandoc no instalado, errores de LaTeX, etc.)

### GET `/api/v1/artifacts/{run_id}/{filename}`

Descarga un artefacto generado (JSON, Markdown o PDF).

**Parámetros:**
- `run_id`: ID de la corrida
- `filename`: `process.json`, `process.md` o `process.pdf`

**Response:**
- Archivo solicitado con el content-type apropiado

## Ejemplos de uso con curl

### Crear un nuevo run completo

```bash
curl -X POST "http://localhost:8000/api/v1/process-runs" \
  -F "process_name=Proceso de ejemplo" \
  -F "mode=gestion" \
  -F "detail_level=detallado" \
  -F "context_text=Este proceso requiere validación de supervisor" \
  -F "video_files=@video.mp4" \
  -F "image_files=@captura1.png" \
  -F "text_files=@notas.txt"
```

### Generar PDF desde un run existente (más rápido y económico)

```bash
# Primero crear el run (sin PDF)
curl -X POST "http://localhost:8000/api/v1/process-runs" \
  -F "process_name=Proceso de ejemplo" \
  -F "video_files=@video.mp4"

# Luego generar solo el PDF (sin llamar a OpenAI)
curl -X POST "http://localhost:8000/api/v1/process-runs/{run_id}/generate-pdf"
```

### Descargar artefactos

```bash
# Descargar JSON
curl -O "http://localhost:8000/api/v1/artifacts/{run_id}/process.json"

# Descargar Markdown
curl -O "http://localhost:8000/api/v1/artifacts/{run_id}/process.md"

# Descargar PDF
curl -O "http://localhost:8000/api/v1/artifacts/{run_id}/process.pdf"
```

## Integración con UI (Next.js)

La API está configurada con CORS para permitir requests desde:
- `http://localhost:3000` (Next.js dev por defecto)
- `http://localhost:3001`

Para cambiar los orígenes permitidos, edita `api/main.py`.

## Notas

- Los archivos subidos se guardan temporalmente durante el procesamiento
- Los artefactos generados se guardan en `output/{run_id}/`
- El PDF es opcional: si falla la generación, la API no falla (solo no incluye el PDF en `artifacts`)
- **Optimización**: Usá `POST /api/v1/process-runs/{run_id}/generate-pdf` para regenerar PDFs sin costo de OpenAI

