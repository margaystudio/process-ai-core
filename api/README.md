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

```bash
# Desde la raíz del proyecto
uvicorn api.main:app --reload --port 8000
```

La API estará disponible en `http://localhost:8000`

## Endpoints

### POST `/api/v1/process-runs`

Crea una nueva corrida del pipeline de documentación.

**Request (multipart/form-data):**

- `process_name` (string, requerido): Nombre del proceso
- `mode` (string, opcional): `operativo` o `gestion` (default: `operativo`)
- `audience` (string, opcional): Audiencia objetivo
- `detail_level` (string, opcional): Nivel de detalle
- `formality` (string, opcional): Nivel de formalidad
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

### GET `/api/v1/artifacts/{run_id}/{filename}`

Descarga un artefacto generado (JSON, Markdown o PDF).

**Parámetros:**
- `run_id`: ID de la corrida
- `filename`: `process.json`, `process.md` o `process.pdf`

**Response:**
- Archivo solicitado con el content-type apropiado

## Ejemplo de uso con curl

```bash
curl -X POST "http://localhost:8000/api/v1/process-runs" \
  -F "process_name=Proceso de ejemplo" \
  -F "mode=gestion" \
  -F "audience=direccion" \
  -F "video_files=@video.mp4" \
  -F "image_files=@captura1.png" \
  -F "text_files=@notas.txt"
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

