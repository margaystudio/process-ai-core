from dataclasses import dataclass
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
    videos: List[VideoRef]