"""
Modelos de dominio específicos para procesos.

Contrato de salida del LLM (schema v2)
======================================

Qué cambió respecto de v1 y por qué
-----------------------------------

**Actores, riesgos y métricas dejan de ser párrafos.** En v1 eran texto libre que
el renderer volcaba crudo. Un auditor espera una matriz de riesgos con control y
evidencia por fila, no un párrafo; y el modelo ya venía escribiendo esa
estructura en prosa porque el prompt se la pedía. Ahora la devuelve como datos.

**Los pasos pierden `risks`.** El riesgo del paso se movió a la matriz de
riesgos. De paso, la tabla de pasos baja de seis a cinco columnas: seis en A4
quedaba ilegible.

**Campos opcionales.** En v1 las 23 claves eran obligatorias y string, y el
prompt insistía en no decir "no se menciona explícitamente". El resultado era un
modelo llenando 20 campos con una entrevista que cubría 8. Ahora lo que puede no
haberse relevado es `None`, y un campo ausente se omite del documento en vez de
inventarse. Solo `process_name`, `objetivo` y `pasos` son obligatorios: sin eso
no hay documento.

**Marca de inferencia estructurada.** Cada ítem estructurado lleva `confianza`,
y los campos de texto inferidos se listan en `campos_inferidos`. Es un dato, no
una frase adentro del texto, así que el renderer lo puede pintar como chip "A
VALIDAR" y la capa de revisión filtrar por él. La escala usa el mismo vocabulario
que Tyto (ADR-015): lo `relevado` es lo que sale de las fuentes y al aprobarse
pasa a ser 🟢 "aprobado"; lo `inferido` es 🔴 y necesita validación humana
(ADR-006: la IA propone, el humano valida).

**Campos eliminados.** `material_referencia` y `videos` salieron del contrato:
  - `material_referencia` solo se usaba para que el modelo escribiera Markdown de
    imágenes, que es el mecanismo duplicado del pipeline de assets — y el que NO
    se renderizaba. Sin ese uso el campo no tenía contenido propio definido.
  - `videos` hacía que el modelo copiara metadata de activos que el sistema ya
    conoce, con riesgo de alucinar los que no existen. Los videos son activos de
    entrada; si tienen que aparecer, los inserta el pipeline como las imágenes.

`almacenamiento_datos` y `usos_datos` se mantienen y AHORA SÍ se renderizan
(iban en el schema y nunca salían impresos): son contenido de gobernanza legítimo
—dónde viven los datos y para qué se usan— y su lugar natural es la sección de
sistemas y datos.

`preguntas_abiertas` se mantiene en el JSON pero NO va en el documento: es
insumo del ciclo de revisión, no contenido oficial. Ver el docstring del campo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Escala de confianza, alineada con los niveles de Tyto (ADR-015).
#: - "relevado": sale de las fuentes del relevamiento. Al aprobarse el documento
#:   pasa a ser 🟢 "aprobado" para Tyto.
#: - "inferido": lo propuso el modelo y NADIE lo validó todavía. 🔴 para Tyto,
#:   y lo que el documento pinta como "A VALIDAR".
Confianza = Literal["relevado", "inferido"]

CONFIANZA_RELEVADO = "relevado"
CONFIANZA_INFERIDO = "inferido"


# ============================================================
# Modelo de dominio (lo que consume el renderer)
# ============================================================


@dataclass
class Step:
    """Un paso del proceso. Sin `risks`: eso vive en la matriz de riesgos."""

    order: int
    actor: str
    action: str
    input: str
    output: str
    confianza: str = CONFIANZA_RELEVADO


@dataclass
class Actor:
    rol: str
    responsabilidad: str
    confianza: str = CONFIANZA_RELEVADO


@dataclass
class Riesgo:
    """Fila de la matriz de riesgos: es lo que mira un auditor."""

    riesgo: str
    control_actual: str = ""
    evidencia: str = ""
    criticidad: str = ""
    confianza: str = CONFIANZA_RELEVADO


@dataclass
class Metrica:
    indicador: str
    definicion: str = ""
    frecuencia: str = ""
    meta: str = ""
    confianza: str = CONFIANZA_RELEVADO


@dataclass
class ProcessDocument:
    """Documento completo de proceso (modelo final parseado del JSON del LLM)."""

    process_name: str
    objetivo: str
    pasos: List[Step]

    contexto: Optional[str] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    incluidos: Optional[str] = None
    excluidos: Optional[str] = None
    frecuencia: Optional[str] = None
    disparadores: Optional[str] = None
    sistemas: Optional[str] = None
    inputs: Optional[str] = None
    outputs: Optional[str] = None
    variantes: Optional[str] = None
    excepciones: Optional[str] = None
    almacenamiento_datos: Optional[str] = None
    usos_datos: Optional[str] = None
    oportunidades: Optional[str] = None

    #: NO se imprime en el documento. Es insumo del ciclo de revisión: un
    #: documento aprobado con una sección "dudas para confirmar" se contradice a
    #: sí mismo. Queda accesible en el JSON de la versión (y expuesto en
    #: `GET /documents/{id}` dentro de `metadata`) para que la capa de revisión
    #: lo levante como comentarios sobre la versión IN_REVIEW.
    preguntas_abiertas: Optional[str] = None

    actores: List[Actor] = field(default_factory=list)
    riesgos: List[Riesgo] = field(default_factory=list)
    metricas: List[Metrica] = field(default_factory=list)

    #: Nombres de campos de texto cuyo contenido el modelo infirió en vez de
    #: relevarlo. El renderer los marca "A VALIDAR".
    campos_inferidos: List[str] = field(default_factory=list)

    def es_inferido(self, campo: str) -> bool:
        return campo in self.campos_inferidos


# ============================================================
# Esquema de validación (Pydantic) — compuerta del JSON del LLM
# ============================================================

PROCESS_DOCUMENT_SCHEMA_VERSION = 2

#: Campos de texto que pueden faltar legítimamente.
_OPTIONAL_TEXT_FIELDS = (
    "contexto", "inicio", "fin", "incluidos", "excluidos",
    "frecuencia", "disparadores", "sistemas", "inputs", "outputs",
    "variantes", "excepciones", "almacenamiento_datos", "usos_datos",
    "oportunidades", "preguntas_abiertas",
)


def _to_stripped_str(value: object) -> str:
    """Coerciona cualquier escalar a string recortado; None → ''."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_optional_str(value: object) -> Optional[str]:
    """Coerciona a string recortado, o None si queda vacío."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_confianza(value: object) -> str:
    """
    Normaliza la marca de confianza. Ante cualquier valor desconocido asume
    `inferido`: el default seguro es pedir validación, no darla por hecha.
    """
    texto = str(value or "").strip().lower()
    return CONFIANZA_RELEVADO if texto == CONFIANZA_RELEVADO else CONFIANZA_INFERIDO


class _ConfianzaMixin(BaseModel):
    confianza: Confianza = CONFIANZA_INFERIDO

    @field_validator("confianza", mode="before")
    @classmethod
    def _coerce_confianza(cls, v: object) -> str:
        return _to_confianza(v)


class StepSchema(_ConfianzaMixin):
    """Validación de un paso del proceso."""

    model_config = ConfigDict(extra="ignore")

    order: int = 0
    actor: str = ""
    action: str = ""
    input: str = ""
    output: str = ""

    @field_validator("actor", "action", "input", "output", mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)

    @field_validator("order", mode="before")
    @classmethod
    def _coerce_order(cls, v: object) -> int:
        if v is None or v == "":
            return 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0


class ActorSchema(_ConfianzaMixin):
    model_config = ConfigDict(extra="ignore")

    rol: str = ""
    responsabilidad: str = ""

    @field_validator("rol", "responsabilidad", mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)


class RiesgoSchema(_ConfianzaMixin):
    model_config = ConfigDict(extra="ignore")

    riesgo: str = ""
    control_actual: str = ""
    evidencia: str = ""
    criticidad: str = ""

    @field_validator("riesgo", "control_actual", "evidencia", "criticidad", mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)


class MetricaSchema(_ConfianzaMixin):
    model_config = ConfigDict(extra="ignore")

    indicador: str = ""
    definicion: str = ""
    frecuencia: str = ""
    meta: str = ""

    @field_validator("indicador", "definicion", "frecuencia", "meta", mode="before")
    @classmethod
    def _coerce_text(cls, v: object) -> str:
        return _to_stripped_str(v)


class ProcessDocumentSchema(BaseModel):
    """
    Esquema del documento de proceso devuelto por el LLM (v2).

    Estricto en *forma* (tipos y estructura) y explícito en *ausencia*: lo que no
    se relevó llega en None y el documento lo omite, en vez de rellenarse con una
    inferencia disfrazada de hecho.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = PROCESS_DOCUMENT_SCHEMA_VERSION

    # Obligatorios: sin esto no hay documento.
    process_name: str = ""
    objetivo: str = ""

    # Opcionales: pueden no haberse relevado.
    contexto: Optional[str] = None
    inicio: Optional[str] = None
    fin: Optional[str] = None
    incluidos: Optional[str] = None
    excluidos: Optional[str] = None
    frecuencia: Optional[str] = None
    disparadores: Optional[str] = None
    sistemas: Optional[str] = None
    inputs: Optional[str] = None
    outputs: Optional[str] = None
    variantes: Optional[str] = None
    excepciones: Optional[str] = None
    almacenamiento_datos: Optional[str] = None
    usos_datos: Optional[str] = None
    oportunidades: Optional[str] = None
    preguntas_abiertas: Optional[str] = None

    pasos: List[StepSchema] = Field(default_factory=list)
    actores: List[ActorSchema] = Field(default_factory=list)
    riesgos: List[RiesgoSchema] = Field(default_factory=list)
    metricas: List[MetricaSchema] = Field(default_factory=list)

    campos_inferidos: List[str] = Field(default_factory=list)

    @field_validator("process_name", "objetivo", mode="before")
    @classmethod
    def _coerce_required_text(cls, v: object) -> str:
        return _to_stripped_str(v)

    @field_validator(*_OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def _coerce_optional_text(cls, v: object) -> Optional[str]:
        return _to_optional_str(v)

    @field_validator("pasos", "actores", "riesgos", "metricas", "campos_inferidos", mode="before")
    @classmethod
    def _none_to_list(cls, v: object) -> object:
        return [] if v is None else v

    def is_usable(self) -> bool:
        """
        Heurística de "documento servible": tiene al menos un paso o un objetivo
        con contenido. Se usa para decidir si conviene reintentar la generación.
        """
        return bool(self.pasos) or bool(self.objetivo.strip())


# ============================================================
# Compatibilidad hacia atrás (v1 → v2)
# ============================================================


def upgrade_v1_payload(data: dict) -> dict:
    """
    Convierte EN MEMORIA un payload v1 al contrato v2.

    Las versiones ya guardadas en `document_versions.content_json` son v1 y no se
    migran en la base: son contenido de versiones aprobadas, y reescribirlo
    cambiaría documentos que ya fueron firmados. Se convierte al leerlos.

    - `actores_resumen`, `problemas` y `metricas` (párrafos) pasan a un único
      ítem estructurado con el texto en el campo principal. No se intenta
      trocear la prosa: partir un párrafo por comas produciría filas falsas, y
      una matriz de riesgos con datos inventados es peor que una con una fila.
    - `risks` de cada paso se convierte en una fila de la matriz de riesgos,
      que es adonde se mudó.
    - Todo lo convertido queda marcado `inferido`: viene de v1, donde no había
      forma de distinguir lo relevado de lo inferido, y ante la duda se pide
      validación.
    """
    if not isinstance(data, dict):
        return data
    if int(data.get("schema_version") or 1) >= 2:
        return data

    salida = dict(data)
    salida["schema_version"] = PROCESS_DOCUMENT_SCHEMA_VERSION

    texto_actores = _to_optional_str(salida.pop("actores_resumen", None))
    if texto_actores and not salida.get("actores"):
        salida["actores"] = [
            {"rol": "", "responsabilidad": texto_actores, "confianza": CONFIANZA_INFERIDO}
        ]

    riesgos: list[dict] = list(salida.get("riesgos") or [])
    texto_problemas = _to_optional_str(salida.pop("problemas", None))
    if texto_problemas:
        riesgos.append({"riesgo": texto_problemas, "confianza": CONFIANZA_INFERIDO})
    for paso in salida.get("pasos") or []:
        riesgo_paso = _to_optional_str(paso.pop("risks", None)) if isinstance(paso, dict) else None
        if riesgo_paso:
            riesgos.append(
                {
                    "riesgo": riesgo_paso,
                    "control_actual": "",
                    "evidencia": "",
                    "criticidad": "",
                    "confianza": CONFIANZA_INFERIDO,
                }
            )
    if riesgos:
        salida["riesgos"] = riesgos

    texto_metricas = salida.get("metricas")
    if isinstance(texto_metricas, str):
        valor = _to_optional_str(texto_metricas)
        salida["metricas"] = (
            [{"indicador": valor, "confianza": CONFIANZA_INFERIDO}] if valor else []
        )

    # Campos que salieron del contrato: se descartan (extra="ignore" igual los
    # ignoraría, pero explícito es mejor que implícito).
    salida.pop("material_referencia", None)
    salida.pop("videos", None)
    # `alcance` era texto libre por encima de inicio/fin/incluidos/excluidos, que
    # ya responden la pregunta con precisión. Nunca se renderizó: el renderer
    # imprime los cuatro campos bajo ese título. Un texto libre encima o los
    # repite o los contradice, y si los contradice no hay forma de saber cuál es
    # el oficial — en un artefacto de auditoría, una afirmación por hecho.
    salida.pop("alcance", None)

    return salida
