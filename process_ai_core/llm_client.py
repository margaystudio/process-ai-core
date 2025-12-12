from pathlib import Path
from openai import OpenAI

from .config import get_settings
from .prompts import get_process_doc_system_prompt


def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_audio(path: str, prompt: str | None = None) -> str:
    """
    Transcribe un archivo de audio local usando el endpoint de transcriptions.
    """
    settings = get_settings()
    client = get_client()

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {audio_path}")

    with audio_path.open("rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model=settings.openai_model_transcribe,
            file=audio_file,
            prompt=prompt or "",
            response_format="json",
        )

    return transcription.text


def generate_process_document_json(prompt: str) -> str:
    """
    Usa un modelo de texto (chat.completions) para generar el JSON del documento de proceso.

    - System prompt en español uruguayo formal.
    - Fuerza JSON mode con response_format={"type": "json_object"}.
    """
    settings = get_settings()
    client = get_client()

    system_instructions = get_process_doc_system_prompt(language_style="es_uy_formal")

    completion = client.chat.completions.create(
        model=settings.openai_model_text,
        messages=[
            {
                "role": "system",
                "content": system_instructions,
            },
            {
                "role": "user",
                "content": (
                    "A continuación tenés el material bruto (texto, "
                    "transcripciones, notas). Leelo y generá el "
                    "documento de proceso en formato JSON, siguiendo "
                    "estrictamente el esquema indicado en las instrucciones.\n\n"
                    + prompt
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    # En JSON mode, el contenido es un string JSON válido en message.content
    json_str = completion.choices[0].message.content
    return json_str