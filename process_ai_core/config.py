from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()


@dataclass
class Settings:
    # OpenAI
    openai_api_key: str
    openai_model_text: str

    # Transcripción
    openai_model_transcribe: str              # transcripción simple (sin timestamps)
    openai_model_transcribe_timestamps: str   # transcripción con timestamps (whisper)

    # I/O
    input_dir: str = "input"
    output_dir: str = "output"


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings (pattern singleton sencillo),
    cargada a partir de las variables de entorno.
    """
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model_text=os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini"),

        # modelos de audio
        openai_model_transcribe=os.getenv(
            "OPENAI_MODEL_TRANSCRIBE",
            "gpt-4o-mini-transcribe"
        ),
        openai_model_transcribe_timestamps=os.getenv(
            "OPENAI_MODEL_TRANSCRIBE_TIMESTAMPS",
            "whisper-1"
        ),
    )