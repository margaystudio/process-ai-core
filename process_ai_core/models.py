from dataclasses import dataclass
from dataclasses import field
from typing import List, Optional, Literal, Dict

RawKind = Literal["audio", "video", "image", "text"]


@dataclass
class RawAsset:
    id: str
    kind: RawKind              # "audio" | "video" | "image" | "text"
    path_or_url: str           # ruta local o URL
    metadata: Dict[str, str]   # ej: {"titulo": "...", "proceso": "..."}


@dataclass
class EnrichedAsset:
    id: str
    kind: RawKind
    raw_path: str
    metadata: Dict[str, str]
    extracted_text: str        # texto extraído (transcripción / descripción)


@dataclass
class VideoRef:
    title: str
    url: str
    duration: Optional[str] = None
    description: Optional[str] = None


@dataclass
class Step:
    order: int
    actor: str
    action: str
    input: str
    output: str
    risks: str

@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str


@dataclass
class StepPlan:
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