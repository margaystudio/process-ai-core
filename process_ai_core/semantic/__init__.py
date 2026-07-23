"""Capa semántica de Process AI.

Pipeline (brief "Capa de relaciones y conocimiento" §4):

    Documento aprobado
      → SemanticExtractionService  (extractor de entidades + normalizador)
      → RelationService            (matching exacto → fuzzy → embedding,
                                    duplicados, relaciones candidatas)
      → Revisión humana            (confirm / edit / reject — API)
      → Red documental confirmada  (la consulta TytoQueryService)

Gobernanza: la IA solo propone (status=candidate); nada es oficial hasta que
un humano lo confirma (ADR-006). Tyto usa únicamente documentos aprobados y
relaciones confirmadas (ADR-002).
"""

from .normalize import normalize_name  # noqa: F401
from .extraction import SemanticExtractionService, ExtractedEntity, ExtractedRelation  # noqa: F401
from .relations import RelationService  # noqa: F401
from .chunking import ChunkIndexService, split_markdown_into_chunks  # noqa: F401
from .tyto import TytoQueryService  # noqa: F401
from .tyto_answer import TytoAnswerService  # noqa: F401
