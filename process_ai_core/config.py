# process_ai_core/config.py
from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

"""
process_ai_core.config
======================

Gestión centralizada de configuración de la aplicación.

Este módulo define:
- La estructura de configuración (`Settings`)
- El mecanismo para cargar variables desde entorno (.env)
- Un acceso único y cacheado a la configuración (`get_settings`)

Objetivos de diseño
-------------------
1. **Fuente única de verdad**  
   Toda la app debe obtener configuración solo a través de `get_settings()`.

2. **Inmutabilidad práctica**  
   `Settings` se crea una sola vez y luego se reutiliza (cache LRU).

3. **Separación de responsabilidades**  
   - Este módulo NO decide lógica de negocio
   - Solo expone valores ya resueltos desde el entorno

4. **Facilidad de testing**  
   Al estar encapsulado, es fácil mockear `get_settings()` en tests.

Convenciones
------------
- Las variables de entorno se cargan desde un archivo `.env` si existe.
- Los defaults están pensados para desarrollo local.
- En producción, los valores deben venir del entorno real (Docker, CI, etc.).

Notas importantes
-----------------
- `load_dotenv()` se ejecuta al importar el módulo.
- Si una variable crítica (ej. API key) no está presente,
  el error se lanza en el lugar donde se usa, no acá.
"""

# Cargar variables de entorno desde .env (si existe)
load_dotenv()


@dataclass
class Settings:
    """
    Contenedor tipado de configuración global de la aplicación.

    Esta clase no contiene lógica: solo define qué valores existen
    y qué significan.

    Attributes
    ----------
    openai_api_key:
        API key de OpenAI. Debe estar presente para cualquier operación con LLM.
    openai_model_text:
        Modelo principal de texto para:
        - generación de documentos
        - inferencia de pasos
        - selección de imágenes (si soporta visión)
    openai_model_transcribe:
        Modelo de transcripción simple de audio (sin timestamps).
    openai_model_transcribe_timestamps:
        Modelo de transcripción con timestamps (segmentos o palabras).
        Usualmente Whisper.
    input_dir:
        Directorio base donde se buscan los insumos (audio, video, imágenes, texto).
    output_dir:
        Directorio base donde se escriben los resultados (JSON, Markdown, PDF, assets).
    """

    # OpenAI
    openai_api_key: str
    openai_model_text: str

    # Transcripción
    openai_model_transcribe: str              # transcripción simple (sin timestamps)
    openai_model_transcribe_timestamps: str   # transcripción con timestamps (whisper)

    # I/O
    input_dir: str = "input"
    output_dir: str = "output"

    # Rutas relativas para assets (desde output_dir)
    assets_dir: str = "assets"  # output/assets/
    evidence_dir: str = "evidence"  # output/assets/evidence/

    # URL base de la API (para construir URLs absolutas en HTML/PDF)
    api_base_url: str = "http://localhost:8000"

    # Firma de URLs de artefactos (HMAC-SHA256)
    # En producción DEBE setearse con ARTIFACT_SIGNING_SECRET; vacío solo se acepta en local/test.
    artifact_signing_secret: str = ""
    # TTL de las URLs firmadas en segundos (default: 15 minutos)
    artifact_url_ttl_seconds: int = 900

    # Almacenamiento de blobs (artefactos: PDF, imágenes, JSON/MD)
    # backend: "local" (filesystem, dev/test) | "supabase" (Supabase Storage, prod)
    storage_backend: str = "local"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "process-ai-artifacts"


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una instancia única y cacheada de `Settings`.

    Implementa un patrón tipo *singleton funcional* usando `lru_cache`,
    suficiente para la mayoría de los casos de apps backend / scripts.

    Returns
    -------
    Settings
        Configuración resuelta a partir de variables de entorno.

    Variables de entorno utilizadas
    -------------------------------
    - OPENAI_API_KEY
    - OPENAI_MODEL_TEXT (default: "gpt-4.1-mini")
    - OPENAI_MODEL_TRANSCRIBE (default: "gpt-4o-mini-transcribe")
    - OPENAI_MODEL_TRANSCRIBE_TIMESTAMPS (default: "whisper-1")

    Notas
    -----
    - Si `OPENAI_API_KEY` no está definida, NO se falla acá.
      El error se lanza cuando alguien intenta usar OpenAI.
    - El cache evita lecturas repetidas del entorno y mantiene
      consistencia durante toda la ejecución del proceso.
    """
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        artifact_signing_secret=os.getenv("ARTIFACT_SIGNING_SECRET", ""),
        artifact_url_ttl_seconds=int(os.getenv("ARTIFACT_URL_TTL_SECONDS", "900")),
        storage_backend=os.getenv("STORAGE_BACKEND", "local"),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "process-ai-artifacts"),
        openai_model_text=os.getenv(
            "OPENAI_MODEL_TEXT",
            "gpt-4.1-mini"
        ),

        # Modelos de audio
        openai_model_transcribe=os.getenv(
            "OPENAI_MODEL_TRANSCRIBE",
            "gpt-4o-mini-transcribe"
        ),
        openai_model_transcribe_timestamps=os.getenv(
            "OPENAI_MODEL_TRANSCRIBE_TIMESTAMPS",
            "whisper-1"
        ),
    )