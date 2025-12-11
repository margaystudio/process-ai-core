from pathlib import Path

from openai import OpenAI

from .config import get_settings


def get_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY no está configurada en el .env")
    return OpenAI(api_key=settings.openai_api_key)


def transcribe_audio(path: str, prompt: str | None = None) -> str:
    """
    Transcribe un archivo de audio local usando el endpoint de transcriptions
    y el modelo gpt-4o-mini-transcribe (o el que configures en .env).
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
            # opcional: prompt para mejorar precisión con contexto del negocio
            prompt=prompt or "",
            response_format="json",
        )

    # Para gpt-4o(-mini)-transcribe, la respuesta es un objeto con .text  [oai_citation:1‡Plataforma OpenAI](https://platform.openai.com/docs/guides/speech-to-text?utm_source=chatgpt.com)
    return transcription.text


def generate_process_document_json(prompt: str) -> str:
    """
    Llamada al modelo de texto para generar el JSON del documento de proceso.

    POR AHORA: devuelve un JSON de ejemplo (mock), así podés probar fin a fin
    sin gastar tokens de texto. Después reemplazamos esto por un llamado real
    a client.responses o client.chat.completions.
    """
    # TODO luego:
    # client = get_client()
    # settings = get_settings()
    # response = client.responses.create(
    #     model=settings.openai_model_text,
    #     input=[
    #         {
    #             "role": "system",
    #             "content": "Sos un consultor senior de procesos...",
    #         },
    #         {
    #             "role": "user",
    #             "content": prompt,
    #         },
    #     ],
    #     response_format={"type": "json_object"},
    # )
    # return response.output[0].content[0].text

    return """
    {
      "process_name": "Proceso genérico de ejemplo",
      "objetivo": "Ejemplo: disponer de información confiable para tomar decisiones.",
      "contexto": "Documento generado a partir de insumos enriquecidos (mock).",
      "alcance": "Desde el evento disparador hasta la salida principal.",
      "inicio": "Evento disparador del proceso.",
      "fin": "Salida generada y comunicada al destinatario.",
      "incluidos": "Actividades principales del proceso.",
      "excluidos": "Procesos de soporte y actividades externas.",
      "frecuencia": "Diaria",
      "disparadores": "Fin de jornada operativa.",
      "actores_resumen": "Actor A, Actor B, Área X.",
      "sistemas": "Sistema 1, Sistema 2.",
      "inputs": "Datos de entrada necesarios.",
      "outputs": "Documentos / reportes generados.",
      "pasos": [
        {
          "order": 1,
          "actor": "Actor A",
          "action": "Realiza la primera actividad.",
          "input": "Input inicial",
          "output": "Resultado intermedio",
          "risks": "Riesgo típico del paso 1"
        },
        {
          "order": 2,
          "actor": "Actor B",
          "action": "Valida y continúa el flujo.",
          "input": "Resultado intermedio",
          "output": "Salida final",
          "risks": "Riesgo típico del paso 2"
        }
      ],
      "variantes": "Cuando hay feriados, cambios de horario o condiciones especiales.",
      "excepciones": "Cuando faltan datos o se detectan inconsistencias.",
      "metricas": "Métricas clave del proceso (tiempos, volúmenes, errores).",
      "almacenamiento_datos": "Repositorios / sistemas donde quedan los datos.",
      "usos_datos": "Qué áreas usan estos datos y para qué.",
      "problemas": "Problemas típicos observados en el proceso actual.",
      "oportunidades": "Oportunidades de automatización y mejora.",
      "preguntas_abiertas": "Dudas a validar con el cliente sobre el proceso.",
      "videos": []
    }
    """