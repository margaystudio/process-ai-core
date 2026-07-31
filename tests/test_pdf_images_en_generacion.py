"""
Un PDF usado como INSUMO de una generación promueve sus imágenes al documento.

El caso de uso: un PDF puede ser UNA PARTE del insumo, no el procedimiento
entero. Se documenta un cierre de caja a partir de una entrevista, notas, y el
manual en PDF del sistema POS — y las capturas de ese manual son la evidencia de
pasos concretos. Antes ese PDF se convertía a texto y nada más: sus imágenes
nunca llegaban a ser assets del run, así que el pipeline de imágenes que ya
existía (inject_assets_into_json → images_by_step → el renderer) nunca las veía.

El modelo no inserta imágenes: solo dice, por NÚMERO, qué paso ilustra cada una.
La inserción sigue siendo 100 % del pipeline de assets.
"""

from __future__ import annotations

import io
import json

import pytest

from process_ai_core.assets_json import (
    assign_referenced_images_to_steps,
    inject_assets_into_json,
    number_image_assets,
)
from process_ai_core.domain_models import EnrichedAsset, RawAsset
from process_ai_core.domains.processes.builder import ProcessBuilder
from process_ai_core.domains.processes.models import ProcessDocument, Step
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.domains.processes.renderer import render_markdown
from process_ai_core.media import enrich_assets


def _png(color=(30, 90, 160), size=(900, 700)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def _manual_pos(path) -> str:
    """Manual del POS: texto con una captura en el medio."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Para cerrar la caja, entra al menu Cierre.", fontsize=11)
    page.insert_image(fitz.Rect(100, 200, 460, 560), stream=_png())
    page.insert_text((50, 600), "Confirma el arqueo y emite el comprobante.", fontsize=11)
    page.insert_text((50, 700), "Texto de relleno para que la pagina tenga cuerpo real.", fontsize=9)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture(autouse=True)
def sin_visión(monkeypatch):
    monkeypatch.setenv("PDF_IMAGE_DESCRIBE", "false")
    from process_ai_core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def enriquecidos(tmp_path):
    """Assets enriquecidos de un run con notas + el manual en PDF."""
    notas = tmp_path / "notas.md"
    notas.write_text("El cajero cuenta el efectivo y firma la planilla.", encoding="utf-8")
    manual = _manual_pos(tmp_path / "manual_pos.pdf")

    raw = [
        RawAsset(id="notas", kind="text", path_or_url=str(notas), metadata={}),
        RawAsset(id="manual", kind="text", path_or_url=manual, metadata={}),
    ]
    enriched, images_by_step, evidence = enrich_assets(raw, output_base=tmp_path)
    return enriched, images_by_step, evidence, tmp_path


# ── Promoción ────────────────────────────────────────────────────────────────


def test_el_pdf_de_entrada_promueve_sus_imagenes_a_assets_del_run(enriquecidos):
    enriched, images_by_step, _evidence, base = enriquecidos

    imagenes = [a for a in enriched if a.kind == "image"]
    assert len(imagenes) == 1, "la imagen del PDF no se promovió"

    asset = imagenes[0]
    assert asset.metadata["origen"] == "pdf"
    assert asset.metadata["source_document"] == "manual"
    assert asset.metadata["pagina"] == "1"
    # El archivo existe donde el renderer y el sync a storage lo van a buscar.
    assert (base / asset.metadata["path"]).exists()
    # Y viaja con el texto que la rodeaba en el PDF.
    assert "Cierre" in asset.metadata["contexto"] or "arqueo" in asset.metadata["contexto"]

    # Todavía NO tiene paso: eso lo decide el modelo.
    assert images_by_step == {}


def test_el_prompt_le_ofrece_la_imagen_al_modelo_numerada(enriquecidos):
    enriched, *_ = enriquecidos
    prompt = ProcessBuilder().build_prompt("Cierre de caja", enriched)

    assert "IMAGENES DISPONIBLES" in prompt
    assert "Imagen 1:" in prompt
    assert '"imagenes": [2]' in prompt or "imagenes" in prompt
    # El contexto del PDF viaja en el prompt: es con lo que el modelo decide.
    assert "Contexto en el documento" in prompt


def test_la_numeracion_es_la_misma_para_el_prompt_y_para_la_resolucion(enriquecidos):
    """
    Si la numeración se calculara en dos lados, el modelo diría "paso 5 ↔ imagen
    3" y el pipeline pegaría otra imagen. El bug sería invisible.
    """
    enriched, *_ = enriquecidos
    numeros = number_image_assets(enriched)

    assert list(numeros) == [1]
    prompt = ProcessBuilder().build_prompt("Cierre de caja", enriched)
    assert f"Imagen 1: id={numeros[1].id}" in prompt


# ── Asignación a pasos ───────────────────────────────────────────────────────


def _doc(imagenes_del_paso_2):
    return ProcessDocument(
        process_name="Cierre de caja",
        objetivo="Cerrar la caja al fin del turno",
        pasos=[
            Step(order=1, actor="Cajero", action="Cuenta el efectivo", input="", output=""),
            Step(
                order=2,
                actor="Cajero",
                action="Entra al menu Cierre (ver captura)",
                input="",
                output="",
                imagenes=imagenes_del_paso_2,
            ),
        ],
    )


def test_la_imagen_llega_al_paso_que_el_modelo_indico(enriquecidos):
    enriched, images_by_step, _evidence, _base = enriquecidos

    resultado = assign_referenced_images_to_steps(_doc([1]), enriched, images_by_step)

    assert list(resultado) == [2], "la imagen no quedó en el paso que dijo el modelo"
    assert resultado[2][0]["path"].endswith(".png")


def test_una_imagen_que_el_modelo_no_ubico_no_se_pierde(enriquecidos):
    """Va al paso 0 ("capturas adicionales"), no a la basura."""
    enriched, images_by_step, _evidence, _base = enriquecidos

    resultado = assign_referenced_images_to_steps(_doc([]), enriched, images_by_step)

    assert list(resultado) == [0]
    assert len(resultado[0]) == 1


def test_una_referencia_inventada_no_pega_una_imagen_equivocada(enriquecidos):
    enriched, images_by_step, _evidence, _base = enriquecidos

    resultado = assign_referenced_images_to_steps(_doc([7]), enriched, images_by_step)

    # La 7 no existe: no se asigna nada al paso 2 y la 1 queda como adicional.
    assert 2 not in resultado
    assert len(resultado[0]) == 1


def test_la_evidencia_suelta_del_usuario_no_se_mueve_de_su_seccion(tmp_path):
    """
    La evidencia que aporta el usuario ya tiene su propia sección; moverla a los
    pasos cambiaría lo que el usuario pidió. Solo son asignables las de PDF.
    """
    evidencia = EnrichedAsset(
        id="ev1",
        kind="image",
        raw_path="x.png",
        metadata={"titulo": "Recibo", "path": "assets/evidence/ev1.png"},
        extracted_text="",
    )
    resultado = assign_referenced_images_to_steps(_doc([1]), [evidencia], {})

    assert resultado == {}


# ── Del paso al documento renderizado ────────────────────────────────────────


def test_el_documento_final_muestra_la_imagen_anclada_al_paso(enriquecidos):
    enriched, images_by_step, evidence, base = enriquecidos
    resultado = assign_referenced_images_to_steps(_doc([1]), enriched, images_by_step)

    markdown = render_markdown(
        _doc([1]), get_profile("operativo"), resultado, evidence, output_base=base
    )

    assert "### Paso 2 {#cap-paso-2}" in markdown
    assert "![" in markdown
    assert "(ver captura)" in markdown or "cap-paso-2" in markdown


def test_el_json_del_documento_lleva_la_imagen_asociada_al_paso(enriquecidos):
    enriched, images_by_step, evidence, _base = enriquecidos
    resultado = assign_referenced_images_to_steps(_doc([1]), enriched, images_by_step)

    payload = json.loads(
        inject_assets_into_json('{"process_name": "Cierre"}', resultado, evidence)
    )

    assert "2" in payload["assets"]["images_by_step"]


# ── Descripción para el índice semántico ─────────────────────────────────────


def test_la_descripcion_de_la_imagen_se_indexa_y_va_marcada_como_inferida(monkeypatch):
    """
    Tyto indexa TEXTO: si la descripción no está en el markdown, el contenido de
    la captura no existe en la capa semántica. Y como es inferencia pura —nadie
    la escribió ni la validó— tiene que llevar el chip "A VALIDAR" (ADR-015).
    """
    from process_ai_core.semantic.chunking import split_markdown_into_chunks

    imagenes = {
        2: [
            {
                "path": "assets/pdf_manual/manual_img01.png",
                "title": "Menu de cierre del POS",
                "description": "Pantalla del POS con el menu Cierre y el total del turno.",
            }
        ]
    }
    markdown = render_markdown(_doc([1]), get_profile("operativo"), imagenes, [])

    assert "Pantalla del POS con el menu Cierre" in markdown
    assert "A VALIDAR" in markdown

    indexado = " ".join(c.content for c in split_markdown_into_chunks(markdown))
    assert "menu Cierre y el total del turno" in indexado


def test_la_descripcion_tambien_va_estructurada_en_el_json():
    payload = json.loads(
        inject_assets_into_json(
            "{}",
            {2: [{"path": "assets/x.png", "title": "T", "description": "Qué muestra"}]},
            [],
        )
    )
    entrada = payload["assets"]["images_by_step"]["2"][0]

    assert entrada["description"] == "Qué muestra"
    assert entrada["description_confianza"] == "inferido"
