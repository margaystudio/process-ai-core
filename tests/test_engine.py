from process_ai_core.domain_models import Step, ProcessDocument
from process_ai_core.doc_engine import render_markdown
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.domains.processes.models import Step as DomainStep, ProcessDocument as DomainProcessDocument
from process_ai_core.domains.processes.renderer import ProcessRenderer


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


def test_render_markdown_no_incluye_preguntas_abiertas():
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
        preguntas_abiertas="Texto de preguntas abiertas que no debe renderizarse",
        material_referencia="Material de referencia",
        videos=[],
    )

    profile = get_profile("operativo")
    md = render_markdown(doc, profile)
    assert "Texto de preguntas abiertas que no debe renderizarse" not in md
    assert "Dudas para confirmar" not in md


def test_process_renderer_no_incluye_preguntas_abiertas():
    doc = DomainProcessDocument(
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
            DomainStep(
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
        preguntas_abiertas="Texto de preguntas abiertas que no debe renderizarse",
        material_referencia="Material de referencia",
        videos=[],
    )

    profile = get_profile("operativo")
    md = ProcessRenderer().render_markdown(doc, profile)
    assert "Texto de preguntas abiertas que no debe renderizarse" not in md
    assert "Dudas para confirmar" not in md


def test_process_renderer_delega_en_doc_engine():
    doc_engine_document = ProcessDocument(
        process_name="Proceso Delegado",
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
        preguntas_abiertas="No renderizar",
        material_referencia="Material de referencia",
        videos=[],
    )

    process_renderer_document = DomainProcessDocument(
        process_name="Proceso Delegado",
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
            DomainStep(
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
        preguntas_abiertas="No renderizar",
        material_referencia="Material de referencia",
        videos=[],
    )

    profile = get_profile("operativo")
    markdown_from_doc_engine = render_markdown(doc_engine_document, profile)
    markdown_from_process_renderer = ProcessRenderer().render_markdown(process_renderer_document, profile)

    assert markdown_from_process_renderer == markdown_from_doc_engine