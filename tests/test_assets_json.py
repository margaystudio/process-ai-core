"""
Tests para la inyección de imágenes estructuradas en el JSON (Fase C).

Verifica que el bloque `assets` (imagen↔paso + evidencia) se agrega al content_json
para consumo del RAG, con asset_id estable, sin romper el JSON original.
"""

import json

from process_ai_core.assets_json import build_assets_block, inject_assets_into_json


def test_build_assets_block_image_step_link():
    images_by_step = {
        1: [{"path": "assets/frames_vid1/step01_1.png", "title": "Apertura"}],
        5: [{"path": "assets/frames_vid1/step05_2.png", "title": ""}],
    }
    evidence = [{"path": "assets/evidence/img1_planilla.png", "title": "Planilla"}]

    block = build_assets_block(images_by_step, evidence)

    # Claves de paso como string, ligadas a sus imágenes
    assert set(block["images_by_step"].keys()) == {"1", "5"}
    assert block["images_by_step"]["1"][0]["asset_id"] == "step01_1"
    assert block["images_by_step"]["1"][0]["path"] == "assets/frames_vid1/step01_1.png"
    assert block["images_by_step"]["1"][0]["title"] == "Apertura"
    # Evidencia con asset_id estable derivado del filename
    assert block["evidence_images"][0]["asset_id"] == "img1_planilla"


def test_inject_adds_assets_key_preserving_original():
    original = json.dumps({"process_name": "Recepción", "pasos": [{"order": 1}]})
    out = inject_assets_into_json(
        original,
        images_by_step={1: [{"path": "assets/evidence/a.png", "title": "A"}]},
        evidence_images=[],
    )
    data = json.loads(out)
    # No se pierde el contenido original
    assert data["process_name"] == "Recepción"
    assert data["pasos"] == [{"order": 1}]
    # Se agrega el bloque assets
    assert data["assets"]["images_by_step"]["1"][0]["asset_id"] == "a"


def test_inject_empty_assets():
    out = inject_assets_into_json('{"x": 1}', images_by_step={}, evidence_images=[])
    data = json.loads(out)
    assert data["assets"] == {"images_by_step": {}, "evidence_images": []}


def test_inject_invalid_json_returns_original():
    bad = "no soy json"
    assert inject_assets_into_json(bad, {1: [{"path": "a.png"}]}, []) == bad


def test_inject_skips_images_without_path():
    block = build_assets_block({1: [{"title": "sin path"}]}, [{"path": "", "title": "vacío"}])
    assert block["images_by_step"] == {}
    assert block["evidence_images"] == []
