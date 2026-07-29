"""
Contrato del schema del documento de proceso (v2).

Fija tres cosas que antes no estaban garantizadas:

1. **Lo que no se relevó llega vacío.** En v1 las 23 claves eran obligatorias y
   string; el modelo llenaba veinte campos con una entrevista que cubría ocho, y
   nada permitía distinguir lo relevado de lo inferido.
2. **Un documento v1 sigue leyéndose.** Las versiones ya aprobadas tienen su
   `content_json` en v1 y no se migran en la base: se convierten al leerlos.
3. **El esquema es una sola fuente de verdad.** Sale del modelo Pydantic y viaja
   en `response_format`, no descrito en prosa dentro del prompt.
"""

import json

import pytest
from pydantic import ValidationError

from process_ai_core.ai.json_schema import build_strict_schema
from process_ai_core.domains.processes.builder import ProcessBuilder
from process_ai_core.domains.processes.models import (
    CONFIANZA_INFERIDO,
    CONFIANZA_RELEVADO,
    PROCESS_DOCUMENT_SCHEMA_VERSION,
    ProcessDocumentSchema,
    upgrade_v1_payload,
)

BUILDER = ProcessBuilder()


# ── 1. Campos opcionales ─────────────────────────────────────────────────────


def test_lo_no_relevado_llega_en_none_y_no_en_cadena_vacia():
    """
    None y "" no significan lo mismo. None dice "no se cubrió"; "" es un campo
    lleno de nada. El renderer omite el primero, y eso es información honesta.
    """
    doc = ProcessDocumentSchema.model_validate(
        {"process_name": "P", "objetivo": "O", "contexto": "", "frecuencia": "   "}
    )
    assert doc.contexto is None
    assert doc.frecuencia is None
    assert doc.inputs is None  # ni siquiera vino


def test_solo_hacen_falta_nombre_objetivo_y_pasos():
    doc = ProcessDocumentSchema.model_validate({"process_name": "P", "objetivo": "O"})
    assert doc.process_name == "P"
    assert doc.pasos == []
    assert doc.is_usable() is True

    vacio = ProcessDocumentSchema.model_validate({})
    assert vacio.is_usable() is False


def test_una_estructura_rota_sigue_fallando():
    """La tolerancia es con la AUSENCIA, no con la forma."""
    with pytest.raises(ValidationError):
        ProcessDocumentSchema.model_validate({"process_name": "P", "pasos": "no soy una lista"})


# ── 2. Marca de inferencia ───────────────────────────────────────────────────


def test_la_confianza_por_defecto_es_inferido():
    """
    El default seguro es pedir validación. Si el modelo no dice de dónde sacó un
    dato, no se asume que lo relevó.
    """
    doc = ProcessDocumentSchema.model_validate(
        {"process_name": "P", "objetivo": "O", "actores": [{"rol": "X", "responsabilidad": "Y"}]}
    )
    assert doc.actores[0].confianza == CONFIANZA_INFERIDO


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("relevado", CONFIANZA_RELEVADO),
        ("RELEVADO", CONFIANZA_RELEVADO),
        ("inferido", CONFIANZA_INFERIDO),
        ("cualquier cosa", CONFIANZA_INFERIDO),
        (None, CONFIANZA_INFERIDO),
        ("", CONFIANZA_INFERIDO),
    ],
)
def test_la_confianza_se_normaliza_hacia_el_lado_seguro(valor, esperado):
    doc = ProcessDocumentSchema.model_validate(
        {"process_name": "P", "riesgos": [{"riesgo": "R", "confianza": valor}]}
    )
    assert doc.riesgos[0].confianza == esperado


def test_la_escala_usa_el_vocabulario_de_tyto():
    """Si Tyto ya distingue confianza, el documento usa la misma escala (ADR-015)."""
    from process_ai_core.semantic.tyto_answer import TIER_INFERIDO

    assert CONFIANZA_INFERIDO == TIER_INFERIDO


# ── 3. Retrocompatibilidad v1 → v2 ───────────────────────────────────────────


V1 = {
    "process_name": "Cierre de caja",
    "objetivo": "Asegurar el arqueo",
    "actores_resumen": "Cajero: cuenta el efectivo. Encargado: valida.",
    "problemas": "No hay control cruzado del POS.",
    "metricas": "Tiempo de cierre por turno.",
    "material_referencia": "Imagen 1: ![x](assets/x.png)",
    "videos": [{"title": "Demo", "url": "http://x"}],
    "pasos": [
        {"order": 1, "actor": "Cajero", "action": "Cuenta", "input": "i", "output": "o",
         "risks": "Faltante no detectado"},
    ],
}


def test_un_documento_v1_se_sigue_leyendo():
    doc = BUILDER.parse_document(json.dumps(V1))
    assert doc.process_name == "Cierre de caja"
    assert len(doc.pasos) == 1


def test_los_parrafos_v1_pasan_a_un_solo_item_estructurado():
    """
    No se intenta trocear la prosa: partir un párrafo por comas produciría filas
    falsas, y una matriz de riesgos con datos inventados es peor que una con una
    sola fila honesta.
    """
    doc = BUILDER.parse_document(json.dumps(V1))
    assert len(doc.actores) == 1
    assert "Cajero: cuenta el efectivo" in doc.actores[0].responsabilidad
    assert len(doc.metricas) == 1
    assert doc.metricas[0].indicador == "Tiempo de cierre por turno."


def test_el_riesgo_del_paso_v1_se_muda_a_la_matriz():
    doc = BUILDER.parse_document(json.dumps(V1))
    riesgos = [r.riesgo for r in doc.riesgos]
    assert "No hay control cruzado del POS." in riesgos
    assert "Faltante no detectado" in riesgos
    # Y el paso ya no lo lleva.
    assert not hasattr(doc.pasos[0], "risks")


def test_todo_lo_convertido_desde_v1_queda_marcado_inferido():
    """
    En v1 no había forma de distinguir lo relevado de lo inferido. Ante la duda,
    se pide validación en vez de darla por hecha.
    """
    doc = BUILDER.parse_document(json.dumps(V1))
    assert all(a.confianza == CONFIANZA_INFERIDO for a in doc.actores)
    assert all(r.confianza == CONFIANZA_INFERIDO for r in doc.riesgos)
    assert all(m.confianza == CONFIANZA_INFERIDO for m in doc.metricas)


def test_los_campos_eliminados_se_descartan():
    convertido = upgrade_v1_payload(dict(V1))
    assert "material_referencia" not in convertido
    assert "videos" not in convertido
    assert convertido["schema_version"] == PROCESS_DOCUMENT_SCHEMA_VERSION


def test_un_documento_v2_no_se_toca():
    v2 = {"schema_version": 2, "process_name": "P", "riesgos": [{"riesgo": "R"}]}
    assert upgrade_v1_payload(dict(v2)) == v2


# ── 4. Structured outputs ────────────────────────────────────────────────────


def test_el_response_format_cumple_el_modo_estricto_de_openai():
    """
    Modo estricto: TODAS las propiedades en `required` (lo opcional se expresa
    como nullable, no omitiendo), `additionalProperties: false` en cada objeto y
    sin `default`.
    """
    rf = BUILDER.get_response_format()
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True

    esquema = rf["json_schema"]["schema"]

    def revisar(nodo, ruta="raíz"):
        if isinstance(nodo, dict):
            if nodo.get("type") == "object" or "properties" in nodo:
                props = set((nodo.get("properties") or {}).keys())
                assert set(nodo.get("required", [])) == props, f"required incompleto en {ruta}"
                assert nodo.get("additionalProperties") is False, f"falta el cierre en {ruta}"
            assert "default" not in nodo, f"quedó un default en {ruta}"
            for k, v in nodo.items():
                revisar(v, f"{ruta}.{k}")
        elif isinstance(nodo, list):
            for i, v in enumerate(nodo):
                revisar(v, f"{ruta}[{i}]")

    revisar(esquema)


def test_lo_opcional_viaja_como_nullable_y_no_como_ausente():
    esquema = BUILDER.get_response_format()["json_schema"]["schema"]
    contexto = esquema["properties"]["contexto"]
    tipos = {t.get("type") for t in contexto["anyOf"]}
    assert tipos == {"string", "null"}
    assert "contexto" in esquema["required"]


def test_el_esquema_ya_no_esta_escrito_en_el_prompt():
    """
    Era una segunda fuente de verdad que se desincronizaba sola. Ahora sale del
    modelo Pydantic.
    """
    prompt = BUILDER.get_system_prompt()
    assert '"process_name": string' not in prompt
    assert '"pasos": [' not in prompt
    # Y el prompt tampoco pide Markdown de imágenes: eso lo hace el pipeline.
    assert "![" not in prompt
    assert "assets/" not in prompt


def test_el_prompt_no_esta_anclado_en_un_rubro():
    """Los ejemplos concretos viven en el catálogo business_type, por workspace."""
    prompt = BUILDER.get_system_prompt()
    for termino in ("depósito", "mercadería", "remito", "orden de compra", "factura"):
        assert termino not in prompt.lower(), f"el prompt sigue anclado en logística: {termino}"


def test_los_ejemplos_estan_en_el_catalogo():
    from tools.seed_catalogs import SEED

    rubros = [s for s in SEED if s["domain"] == "business_type"]
    assert len(rubros) >= 3, "debería haber varios rubros, no uno solo"
    texto = " ".join(s["prompt_text"] for s in rubros).lower()
    assert "remito" in texto and "arqueo" in texto


# ── 5. Sin campos huérfanos ──────────────────────────────────────────────────


def test_alcance_ya_no_existe_como_campo():
    """
    Era el quinto huérfano: se generaba, se validaba, se guardaba, y el renderer
    nunca lo usaba — imprime inicio/fin/incluidos/excluidos bajo ese título.

    Se sacó, no se conectó. Los cuatro campos estructurados responden la pregunta
    con precisión; un texto libre encima o los repite o los contradice, y si los
    contradice no hay forma de saber cuál es el oficial.
    """
    assert "alcance" not in ProcessDocumentSchema.model_fields
    esquema = BUILDER.get_response_format()["json_schema"]["schema"]
    assert "alcance" not in esquema["properties"]
    assert "alcance" not in esquema["required"]


def test_un_v1_con_alcance_se_lee_y_lo_descarta():
    payload = dict(V1, alcance="Desde que llega el cliente hasta que se va")
    doc = BUILDER.parse_document(json.dumps(payload))
    assert not hasattr(doc, "alcance")
    assert "alcance" not in upgrade_v1_payload(dict(payload))


def test_la_seccion_alcance_sobrevive_al_campo():
    """
    Lo que se sacó es el CAMPO, no la sección: "alcance" sigue siendo la clave
    con la que el perfil pide imprimir inicio/fin/incluidos/excluidos.
    """
    from process_ai_core.domains.processes.models import ProcessDocument
    from process_ai_core.domains.processes.profiles import get_profile
    from process_ai_core.domains.processes.renderer import render_markdown

    doc = ProcessDocument(
        process_name="P", objetivo="O", pasos=[],
        inicio="Llega el pedido", fin="Se archiva el remito",
    )
    md = render_markdown(doc, get_profile("gestion"))
    assert "## Alcance" in md
    assert "Llega el pedido" in md


def test_no_quedan_campos_huerfanos_en_el_schema():
    """
    Todo campo del schema tiene que terminar impreso por algún perfil. Un campo
    que se genera, se valida y se guarda pero nunca sale es trabajo del modelo
    que nadie ve y una promesa que el documento no cumple.
    """
    from process_ai_core.domains.processes.profiles import GESTION_V1, OPERATIVO_V1
    from process_ai_core.domains.processes.renderer import render_markdown
    from process_ai_core.domains.processes.profiles import get_profile
    from process_ai_core.domains.processes.models import ProcessDocument

    #: Campos que a propósito NO se imprimen, con el motivo.
    NO_SE_IMPRIMEN = {
        # Insumo del ciclo de revisión: un documento aprobado con una sección
        # "dudas para confirmar" se contradice a sí mismo (ver test_engine.py).
        "preguntas_abiertas",
        # Metadatos, no contenido.
        "schema_version",
        "campos_inferidos",
        "process_name",  # va como título, no como sección
    }

    campos = set(ProcessDocumentSchema.model_fields) - NO_SE_IMPRIMEN

    # Un documento con TODOS los campos poblados con un marcador único.
    valores = {}
    for campo in campos:
        info = ProcessDocumentSchema.model_fields[campo]
        anotacion = str(info.annotation)
        if "str" in anotacion and "List" not in anotacion and "list" not in anotacion:
            valores[campo] = f"MARCA-{campo}"
    doc = ProcessDocument(
        process_name="P", objetivo=valores.pop("objetivo", "O"), pasos=[], **valores
    )

    impreso = render_markdown(doc, get_profile("operativo")) + render_markdown(
        doc, get_profile("gestion")
    )
    huerfanos = [c for c in valores if f"MARCA-{c}" not in impreso]
    assert not huerfanos, (
        f"campos que se generan y se guardan pero ningún perfil imprime: {huerfanos}"
    )
