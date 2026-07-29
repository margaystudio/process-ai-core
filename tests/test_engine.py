"""
Render del documento de proceso (schema v2).

Los tests fijan el contrato: qué se imprime, qué NO se imprime, y cómo se marca
lo que el modelo infirió en vez de relevar.
"""

from process_ai_core.domains.processes.models import (
    CONFIANZA_INFERIDO,
    CONFIANZA_RELEVADO,
    Actor,
    Metrica,
    ProcessDocument,
    Riesgo,
    Step,
)
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.domains.processes.renderer import ProcessRenderer, render_markdown


def _doc(**overrides) -> ProcessDocument:
    """Documento completo v2; los tests pisan solo lo que les interesa."""
    base = dict(
        process_name="Proceso Test",
        objetivo="Objetivo de prueba",
        pasos=[
            Step(order=1, actor="Actor 1", action="Hace algo", input="Input", output="Output")
        ],
        contexto="Contexto de prueba",
        inicio="Inicio",
        fin="Fin",
        incluidos="Incluidos",
        excluidos="Excluidos",
        frecuencia="Diaria",
        disparadores="Fin de día",
        sistemas="Sistema X",
        inputs="Input X",
        outputs="Output X",
        variantes="Variantes",
        excepciones="Excepciones",
        almacenamiento_datos="Base X",
        usos_datos="Uso X",
        oportunidades="Oportunidades",
        preguntas_abiertas="¿Quién hace X?",
        actores=[Actor(rol="Actor 1", responsabilidad="Hace algo")],
        riesgos=[Riesgo(riesgo="Riesgo A", control_actual="Control A", evidencia="Planilla",
                        criticidad="alta")],
        metricas=[Metrica(indicador="Tiempo de ciclo", definicion="min", frecuencia="mensual",
                          meta="< 10")],
    )
    base.update(overrides)
    return ProcessDocument(**base)


def test_render_markdown_basico():
    md = render_markdown(_doc(), get_profile("operativo"))
    assert "# Proceso Test" in md
    assert "Hace algo" in md


def test_preguntas_abiertas_nunca_se_imprime():
    """
    Es insumo del ciclo de revisión, no contenido del documento: uno APROBADO con
    una sección "dudas para confirmar" se contradice a sí mismo. Queda accesible
    en el JSON de la versión para que la capa de revisión lo levante.
    """
    doc = _doc(preguntas_abiertas="Texto que no debe renderizarse")
    for perfil in ("operativo", "gestion"):
        md = render_markdown(doc, get_profile(perfil))
        assert "Texto que no debe renderizarse" not in md
        assert "preguntas_abiertas" not in md
        assert "Dudas para confirmar" not in md

    # Y tampoco figura en el `show` de ningún perfil.
    from process_ai_core.domains.processes.profiles import GESTION_V1, OPERATIVO_V1

    assert "preguntas_abiertas" not in OPERATIVO_V1.show + GESTION_V1.show


def test_process_renderer_delega_en_el_render():
    doc = _doc()
    directo = render_markdown(doc, get_profile("gestion"))
    via_clase = ProcessRenderer().render_markdown(document=doc, profile=get_profile("gestion"))
    assert directo == via_clase


# ── Encabezados huérfanos ────────────────────────────────────────────────────


def test_una_seccion_sin_contenido_no_deja_el_encabezado_solo():
    """
    Antes, Alcance / Frecuencia / Sistemas / Excepciones emitían el "##" ANTES de
    mirar si había contenido: con los subcampos vacíos quedaba un encabezado
    suelto, que se lee como un documento incompleto en vez de uno que no releva
    esa dimensión.
    """
    doc = _doc(
        inicio=None, fin=None, incluidos=None, excluidos=None,
        frecuencia=None, disparadores=None,
        sistemas=None, inputs=None, outputs=None,
        almacenamiento_datos=None, usos_datos=None,
        excepciones=None, variantes=None,
    )
    md = render_markdown(doc, get_profile("gestion"))
    for encabezado in ("## Alcance", "## Frecuencia", "## Sistemas", "## Excepciones"):
        assert encabezado not in md, f"quedó un encabezado sin contenido: {encabezado}"
    # Con contenido sí aparecen.
    md_completo = render_markdown(_doc(), get_profile("gestion"))
    assert "## Alcance" in md_completo


# ── Campos que antes no se renderizaban ──────────────────────────────────────


def test_almacenamiento_y_usos_de_datos_ahora_se_imprimen():
    """Estaban en el schema desde siempre y nunca salían impresos."""
    md = render_markdown(_doc(), get_profile("gestion"))
    assert "Base X" in md
    assert "Uso X" in md


# ── Estructuras: actores, riesgos, indicadores ───────────────────────────────


def test_actores_riesgos_e_indicadores_salen_como_tabla():
    md = render_markdown(_doc(), get_profile("gestion"))

    assert "| Rol | Responsabilidad |" in md
    assert "| Riesgo | Control actual | Evidencia | Criticidad |" in md
    assert "| Indicador | Definición | Frecuencia | Meta |" in md
    assert "Control A" in md and "Planilla" in md and "alta" in md
    assert "Tiempo de ciclo" in md and "< 10" in md


def test_la_tabla_de_pasos_no_tiene_columna_de_riesgos():
    """
    El riesgo del paso se mudó a la matriz de riesgos, que es donde lo busca un
    auditor. Seis columnas en A4 quedaban ilegibles.
    """
    md = render_markdown(_doc(), get_profile("gestion"))
    encabezado = [l for l in md.splitlines() if l.startswith("| # |")]
    assert encabezado, "no se encontró la tabla de pasos"
    assert "Riesgos" not in encabezado[0]
    assert encabezado[0].count("|") == 6  # 5 columnas


def test_una_seccion_estructurada_vacia_no_deja_encabezado():
    doc = _doc(actores=[], riesgos=[], metricas=[])
    md = render_markdown(doc, get_profile("gestion"))
    for encabezado in ("## Actores", "## Riesgos", "## Indicadores"):
        assert encabezado not in md


# ── Marca de inferencia (ADR-006 / ADR-015) ──────────────────────────────────


def test_lo_inferido_se_marca_a_validar_y_lo_relevado_no():
    """
    La IA propone, el humano valida (ADR-006). El documento tiene que permitir
    distinguir una cosa de la otra, y con la misma escala que usa Tyto (ADR-015).
    """
    doc = _doc(
        actores=[
            Actor(rol="Cajero", responsabilidad="Arquea", confianza=CONFIANZA_RELEVADO),
            Actor(rol="Auditor", responsabilidad="Revisa", confianza=CONFIANZA_INFERIDO),
        ],
        riesgos=[Riesgo(riesgo="Faltante de caja", confianza=CONFIANZA_INFERIDO)],
        pasos=[
            Step(order=1, actor="C", action="Cuenta", input="i", output="o",
                 confianza=CONFIANZA_RELEVADO),
            Step(order=2, actor="A", action="Concilia", input="i", output="o",
                 confianza=CONFIANZA_INFERIDO),
        ],
    )
    md = render_markdown(doc, get_profile("gestion"))

    # El chip acompaña SOLO a lo inferido.
    assert "Revisa `A VALIDAR`" in md
    assert "Arquea `A VALIDAR`" not in md
    assert "Concilia `A VALIDAR`" in md
    assert "Cuenta `A VALIDAR`" not in md
    assert "Faltante de caja `A VALIDAR`" in md


def test_un_campo_de_texto_inferido_tambien_se_marca():
    doc = _doc(campos_inferidos=["frecuencia"])
    md = render_markdown(doc, get_profile("gestion"))
    assert "Diaria `A VALIDAR`" in md
    # Y lo que no se declaró inferido, no.
    assert "Objetivo de prueba `A VALIDAR`" not in md
