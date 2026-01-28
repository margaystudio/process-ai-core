from process_ai_core.domain_models import Step, ProcessDocument
from process_ai_core.doc_engine import render_markdown
from process_ai_core.domains.processes.profiles import get_profile


def test_render_markdown_basic():
    doc = ProcessDocument(
        process_name="Proceso Test",
        objetivo="Objetivo de prueba",
        contexto="Contexto de prueba",
        alcance="Alcance de prueba",
        inicio="Inicio",
        fin="Fin",
        incluidos="Incluidos",
        excluidos="Excluidos",
        frecuencia="Diaria",
        disparadores="Fin de día",
        actores_resumen="Actor 1, Actor 2",
        sistemas="Sistema X",
        inputs="Input X",
        outputs="Output X",
        pasos=[
            Step(
                order=1,
                actor="Actor 1",
                action="Hace algo",
                input="Input",
                output="Output",
                risks="Riesgo",
            )
        ],
        variantes="Variantes",
        excepciones="Excepciones",
        metricas="Métricas",
        almacenamiento_datos="Base X",
        usos_datos="Uso X",
        problemas="Problemas",
        oportunidades="Oportunidades",
        preguntas_abiertas="¿Quién hace X?",
        material_referencia="Material de referencia",
        videos=[],
    )

    profile = get_profile("operativo")
    md = render_markdown(doc, profile)
    assert "# Proceso Test" in md
    assert "Hace algo" in md