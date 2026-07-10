"""SemanticExtractionService: extractor de entidades + normalizador.

Recibe el texto de una versión aprobada de documento y devuelve entidades
(sistema, rol, área, equipo, formulario, proceso, ubicación, normativa) y
relaciones candidatas (documento → entidad) con confianza y evidencia.

Estrategia de costos (Technical Architecture §10): esta tarea pasa por revisión
humana, así que usa el tier "cheap" del factory de IA (modelo barato/local).
El LLM NO decide el matching contra la base: eso lo hace RelationService con
la cascada exacto → fuzzy → embedding.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ..ai.factory import get_llm_provider
from ..ai.providers import LLMProvider
from ..db.models_semantic import KNOWLEDGE_OBJECT_TYPES, RELATION_TYPES
from .normalize import normalize_name

logger = logging.getLogger(__name__)

# Máximo de caracteres del documento que se envían al extractor (control de costo)
_MAX_INPUT_CHARS = 24_000


@dataclass
class ExtractedEntity:
    """Entidad detectada en el documento, aún sin matchear contra la base."""
    type: str                    # sistema | rol | area | equipo | formulario | proceso | ubicacion | normativa
    canonical_name: str          # "SAP ERP"
    normalized_name: str = ""    # "sap erp" (derivado)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.normalized_name:
            self.normalized_name = normalize_name(self.canonical_name)


@dataclass
class ExtractedRelation:
    """Relación candidata documento → entidad propuesta por el extractor."""
    relation_type: str           # usa | requiere | genera | ...
    entity: ExtractedEntity
    confidence: float = 0.5      # 0..1
    evidence_text: str = ""      # fragmento que justifica la relación


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)


_SYSTEM_PROMPT = """Sos un analista de procesos que extrae entidades semánticas de documentación operativa.
Respondés SOLO JSON válido, sin texto adicional."""

_USER_PROMPT_TEMPLATE = """Analizá el siguiente documento operativo y extraé:

1. Entidades mencionadas, con su tipo. Tipos válidos:
   sistema (software: POS, SAP ERP), rol (puesto: Supervisor, Cajero),
   area (sector: Administración), equipo (hardware: impresora fiscal),
   formulario (planillas/registros: Planilla de cierre), proceso (otro proceso operativo:
   Apertura de caja), ubicacion (lugar físico), normativa (ley/norma/política).

2. Relaciones entre ESTE documento y cada entidad. Tipos válidos:
   usa (el proceso usa un sistema/equipo), requiere (necesita un rol/recurso),
   genera (produce un formulario/registro), relacionado_con (otro proceso vinculado),
   describe, aplica_a, depende_de, reemplaza_a, ejecutado_por (rol que lo ejecuta),
   aprobado_por (rol que aprueba), ubicado_en (lugar).

Reglas:
- Solo entidades realmente mencionadas en el texto; no inventes.
- `evidence` debe ser una cita textual corta (máx. 200 caracteres) del documento.
- `confidence` entre 0 y 1 según qué tan explícita es la relación.
- Usá el nombre tal como aparece (respetá mayúsculas de marcas/sistemas).

Formato de respuesta:
{{"relations": [
  {{"relation_type": "usa", "entity_type": "sistema", "entity_name": "POS",
    "confidence": 0.94, "evidence": "cita textual del documento"}}
]}}

Documento: «{title}»
---
{content}
---"""


class SemanticExtractionService:
    """Extractor de entidades y relaciones candidatas (modelo tier "cheap")."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        # Lazy: no crear el provider hasta la primera extracción (testeable sin API key)
        self._llm = llm

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider(tier="cheap")
        return self._llm

    def extract(self, *, title: str, content: str) -> ExtractionResult:
        """Extrae entidades y relaciones candidatas del contenido de un documento."""
        if not content or not content.strip():
            return ExtractionResult()

        raw = self.llm.complete_json(
            system=_SYSTEM_PROMPT,
            user=_USER_PROMPT_TEMPLATE.format(
                title=title,
                content=content[:_MAX_INPUT_CHARS],
            ),
            temperature=0.0,
        )
        return self._parse(raw)

    def _parse(self, raw: str) -> ExtractionResult:
        """Parsea y sanea la respuesta del modelo (descarta tipos inválidos)."""
        result = ExtractionResult()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("SemanticExtraction: respuesta no-JSON del modelo, se ignora")
            return result

        seen: set[tuple[str, str, str]] = set()
        for item in data.get("relations", []) or []:
            if not isinstance(item, dict):
                continue
            relation_type = str(item.get("relation_type", "")).strip().lower()
            entity_type = str(item.get("entity_type", "")).strip().lower()
            entity_name = str(item.get("entity_name", "")).strip()

            if relation_type not in RELATION_TYPES:
                logger.debug("SemanticExtraction: relation_type inválido %r", relation_type)
                continue
            if entity_type not in KNOWLEDGE_OBJECT_TYPES or entity_type == "documento":
                logger.debug("SemanticExtraction: entity_type inválido %r", entity_type)
                continue
            if not entity_name or len(entity_name) > 300:
                continue

            entity = ExtractedEntity(type=entity_type, canonical_name=entity_name)
            if not entity.normalized_name:
                continue

            key = (relation_type, entity_type, entity.normalized_name)
            if key in seen:
                continue
            seen.add(key)

            try:
                confidence = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))

            evidence = str(item.get("evidence", "")).strip()[:500]

            result.entities.append(entity)
            result.relations.append(
                ExtractedRelation(
                    relation_type=relation_type,
                    entity=entity,
                    confidence=confidence,
                    evidence_text=evidence,
                )
            )
        return result
