from __future__ import annotations

"""
process_ai_core.domain_models
=============================

Modelos de dominio (dataclasses) usados a lo largo del pipeline.

Objetivo
--------
Este módulo define las estructuras de datos "neutras" del sistema: objetos simples
(POPOs) que representan:

- Insumos crudos (`RawAsset`) descubiertos en input/
- Insumos enriquecidos (`EnrichedAsset`) listos para construir prompts
- Referencias a material audiovisual (`VideoRef`)
- Representación de un proceso (`ProcessDocument`) y sus pasos (`Step`)
- Estructuras auxiliares para video/timestamps (`TranscriptSegment`, `StepPlan`)

Principios de diseño
--------------------
- Dataclasses sin lógica pesada: este módulo NO debe hablar con OpenAI, DB, ni IO.
- Tipado explícito para ayudar a Cursor, linters, tests y lectura humana.
- Mantener backwards-compatibility: cambios acá impactan en parsing/render/prompt.

Notas de interoperabilidad
--------------------------
- `RawKind` se usa en `RawAsset` y `EnrichedAsset`. Actualmente incluye "image"
  tanto para evidencia subida por usuario como para capturas extraídas de video.
- `metadata` es libre (dict[str, str]) para soportar campos evolutivos sin
  migraciones inmediatas.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


# ============================================================
# Tipos base
# ============================================================

RawKind = Literal["audio", "video", "image", "text"]
"""
Tipos de insumo soportados por el pipeline.

- audio: archivos de audio (m4a/mp3/wav) para transcripción directa.
- video: archivos de video (mp4/mov/mkv) para:
    1) extraer audio,
    2) transcribir con timestamps,
    3) inferir pasos,
    4) extraer capturas por paso.
- image: imágenes sueltas (evidencia) o capturas extraídas de video.
- text: notas o instrucciones escritas (txt/md).
"""


# ============================================================
# Assets: crudos y enriquecidos
# ============================================================

@dataclass
class RawAsset:
    """
    Representa un insumo "crudo" tal cual se descubre en el filesystem (o URL).

    Se crea típicamente en el paso de ingestión (`discover_raw_assets`),
    antes de cualquier procesamiento (transcripción, copia, extracción de frames).

    Attributes:
        id:
            Identificador corto y estable dentro de una corrida.
            Ejemplos: "aud1", "vid1", "img1", "txt1".

        kind:
            Tipo del asset. Controla el flujo que se aplica en `media.enrich_assets()`.

        path_or_url:
            Ubicación del insumo:
            - usualmente ruta local (str)
            - eventualmente una URL (por ejemplo, referencia a un video externo)

        metadata:
            Diccionario libre con atributos del asset.
            Ejemplos comunes:
            - {"titulo": "Correr job", "url": "https://...", "proceso": "GPU"}
            - {"titulo": "Foto ticket", "fecha": "2025-12-18"}
    """
    id: str
    kind: RawKind
    path_or_url: str
    metadata: Dict[str, str]


@dataclass
class EnrichedAsset:
    """
    Representa un insumo luego de ser "enriquecido" por el pipeline.

    A diferencia de `RawAsset`, este modelo ya contiene `extracted_text`,
    que es lo que se usa como entrada principal para el prompt del LLM.

    Ejemplos de `extracted_text` según tipo:
    - audio: transcripción completa (texto)
    - text: contenido del archivo (texto)
    - image: una referencia estructurada (NO markdown), p.ej:
        "[IMAGEN:img1] titulo='...' archivo='assets/evidence/img1_x.png'"
    - video: transcripción completa + referencia del archivo local/URL, p.ej:
        "...texto..."
        "[VIDEO_REF:vid1] titulo='...' archivo='assets/vid1_demo.mp4' url='...optional...'"

    Attributes:
        id:
            Identificador del asset enriquecido.
            Importante: para capturas extraídas de video suele generarse un id derivado,
            ej: "vid1_img01".

        kind:
            Tipo del asset. Se mantiene dentro de los mismos valores de `RawKind`.

        raw_path:
            Path original del insumo (string), tal como vino en el RawAsset.
            Nota: en video/image puede diferir del archivo copiado a output/assets.

        metadata:
            Metadatos enriquecidos o propagados.
            Ejemplos útiles:
            - {"paso_sugerido": "3"} para capturas extraídas de video
            - {"source_video": "vid1"} para rastreabilidad
            - {"titulo": "..."} para captions y prompt

        extracted_text:
            Texto normalizado para el prompt (fuente de verdad para el LLM).
            Este campo NO debe contener markdown de imágenes, para evitar que el modelo
            "dibuje" el documento. El render de imágenes se hace luego.
    """
    id: str
    kind: RawKind
    raw_path: str
    metadata: Dict[str, str]
    extracted_text: str


# ============================================================
# Referencias a video en el documento final
# ============================================================

@dataclass
class VideoRef:
    """
    Representa una referencia a un video dentro del documento final (JSON).

    Se usa en `ProcessDocument.videos` para mantener trazabilidad hacia material audiovisual.

    Attributes:
        title:
            Título humano del video (p.ej. "Demo Cloud Run").

        url:
            URL pública/privada si existe. Puede ser "" si el video es local.

        duration:
            Duración opcional en formato libre (p.ej. "2:35" o "00:02:35").

        description:
            Descripción breve opcional: qué muestra el video / qué contexto aporta.
    """
    title: str
    url: str
    duration: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# Documento de proceso: pasos y estructura
# ============================================================

@dataclass
class Step:
    """
    Representa un paso del proceso dentro del documento final.

    Este modelo está pensado para ser:
    - simple de renderizar (tabla o lista)
    - simple de validar
    - estable para evolucionar

    Attributes:
        order:
            Número de paso (1..N). Se usa para orden y para asociar capturas.

        actor:
            Responsable del paso (p.ej. "Operario", "Encargado", "Sistema").

        action:
            Acción principal del paso, formulada de forma operativa.

        input:
            Insumos necesarios para ejecutar el paso (datos, documentos, accesos).

        output:
            Resultado esperado del paso (estado, artefacto, registro).

        risks:
            Riesgos/errores frecuentes o consideraciones de seguridad/compliance.
    """
    order: int
    actor: str
    action: str
    input: str
    output: str
    risks: str


@dataclass
class TranscriptSegment:
    """
    Segmento de transcripción con timestamps.

    Se usa principalmente como estructura puente entre:
    - `transcribe_audio_with_timestamps()` (output)
    - `plan_steps_from_transcript_segments()` (input)

    Attributes:
        start_s:
            Tiempo de inicio (segundos) del segmento.

        end_s:
            Tiempo de fin (segundos) del segmento.

        text:
            Texto transcripto correspondiente a ese rango.
    """
    start_s: float
    end_s: float
    text: str


@dataclass
class StepPlan:
    """
    Planificación de pasos inferidos desde un video (transcripción + timestamps).

    Esta estructura NO es necesariamente el documento final:
    es un artefacto intermedio para extraer evidencia visual y mapear a pasos.

    Flujo típico:
    1) Se obtiene `TranscriptSegment[]` del video.
    2) El LLM infiere pasos: `order/start_s/end_s/summary/importance`.
    3) El sistema calcula tiempos candidatos y extrae frames.
    4) El LLM elige la mejor imagen por paso.
    5) Se guarda como `EnrichedAsset(kind="image")` + `images_by_step`.

    Attributes:
        order:
            Número ordinal del paso inferido.

        start_s / end_s:
            Ventana temporal aproximada del paso (segundos).

        summary:
            Resumen textual del paso (lo que guía selección de captura).

        importance:
            Prioridad del paso:
            - "high": crítico (seguridad, control, ejecución principal)
            - "medium": normal
            - "low": detalle accesorio

        candidate_frames:
            Lista de rutas locales a frames candidatos extraídos por ffmpeg.

        selected_frame:
            Ruta elegida (si se elige alguna). Puede ser None.

        selected_title:
            Caption sugerido para la captura elegida. Puede ser None.
    """
    order: int
    start_s: float
    end_s: float
    summary: str
    importance: str  # "high" | "medium" | "low"
    candidate_frames: List[str]
    selected_frame: Optional[str] = None
    selected_title: Optional[str] = None


@dataclass
class ProcessDocument:
    """
    Documento completo de proceso (modelo final parseado del JSON del LLM).

    Este es el "output" semántico principal del sistema, que luego se renderiza
    a Markdown y opcionalmente a PDF.

    Nota:
    - Muchos campos son strings libres (para evitar schemas rígidos temprano).
    - `pasos` es la parte más estructurada.
    - `videos` permite adjuntar referencias audiovisuales en paralelo.

    Attributes:
        process_name:
            Nombre del proceso.

        objetivo:
            Objetivo del proceso.

        contexto:
            Contexto o descripción general.

        alcance:
            Descripción del alcance (a veces redundante con inicio/fin).

        inicio / fin:
            Definición de qué dispara el inicio y cuándo se considera finalizado.

        incluidos / excluidos:
            Qué entra y qué no entra en el proceso.

        frecuencia / disparadores:
            Cuándo ocurre (frecuencia) y qué eventos lo disparan.

        actores_resumen:
            Resumen de roles y responsabilidades.

        sistemas:
            Sistemas involucrados (Cloud Run, BigQuery, etc.).

        inputs / outputs:
            Entradas y salidas principales del proceso (a nivel macro).

        pasos:
            Lista de pasos operativos en orden.

        variantes / excepciones:
            Variantes y casos especiales.

        metricas:
            Indicadores sugeridos para medir el proceso.

        almacenamiento_datos / usos_datos:
            Aspectos de datos (dónde se guarda, para qué se usa), útil para compliance.

        problemas / oportunidades:
            Riesgos/problemas actuales y oportunidades de mejora.

        preguntas_abiertas:
            Incertidumbres o decisiones pendientes.

        material_referencia:
            Campo legacy/compat (texto libre). En algunos prompts previos se usaba.
            Hoy se recomienda usar `videos` y evidencia visual.

        videos:
            Lista de referencias a videos asociados al proceso.
    """
    process_name: str
    objetivo: str
    contexto: str
    alcance: str
    inicio: str
    fin: str
    incluidos: str
    excluidos: str
    frecuencia: str
    disparadores: str
    actores_resumen: str
    sistemas: str
    inputs: str
    outputs: str
    pasos: List[Step]
    variantes: str
    excepciones: str
    metricas: str
    almacenamiento_datos: str
    usos_datos: str
    problemas: str
    oportunidades: str
    preguntas_abiertas: str
    material_referencia: str
    videos: List[VideoRef] = field(default_factory=list)