"""
Tests del manifiesto de fuentes (Fase D).

Verifica que se registra metadata + SHA-256 de cada fuente (sin guardar los bytes)
y la transcripción/texto extraído, para defensa de auditoría.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Dict

from process_ai_core.input_manifest import build_input_manifest, build_input_manifest_json


@dataclass
class _Raw:
    id: str
    kind: str
    path_or_url: str
    metadata: Dict[str, str]


@dataclass
class _Enriched:
    id: str
    extracted_text: str


def test_manifest_records_hash_and_size(tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"fake-video-bytes")
    raw = [_Raw(id="vid1", kind="video", path_or_url=str(f), metadata={"titulo": "Recepción"})]

    manifest = build_input_manifest(raw, uploaded_by="user-7")

    src = manifest["sources"][0]
    assert src["id"] == "vid1"
    assert src["kind"] == "video"
    assert src["filename"] == "video.mp4"
    assert src["size"] == len(b"fake-video-bytes")
    assert src["sha256"] == hashlib.sha256(b"fake-video-bytes").hexdigest()
    assert src["title"] == "Recepción"
    assert manifest["uploaded_by"] == "user-7"
    assert "captured_at" in manifest


def test_manifest_attaches_transcription(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"x")
    raw = [_Raw(id="aud1", kind="audio", path_or_url=str(f), metadata={})]
    enriched = [_Enriched(id="aud1", extracted_text="hola esto es la transcripción")]

    manifest = build_input_manifest(raw, enriched_assets=enriched)
    assert manifest["sources"][0]["extracted_text"] == "hola esto es la transcripción"


def test_manifest_does_not_store_bytes(tmp_path):
    """El manifiesto guarda hash/size pero NO el contenido binario."""
    f = tmp_path / "img.png"
    f.write_bytes(b"PNGDATA")
    raw = [_Raw(id="img1", kind="image", path_or_url=str(f), metadata={})]

    manifest = build_input_manifest(raw)
    src = manifest["sources"][0]
    assert "PNGDATA" not in json.dumps(manifest)
    assert src["sha256"] is not None


def test_manifest_url_source_no_hash():
    raw = [_Raw(id="lnk1", kind="text", path_or_url="https://example.com/doc", metadata={})]
    manifest = build_input_manifest(raw)
    src = manifest["sources"][0]
    assert src["source_url"] == "https://example.com/doc"
    assert "sha256" not in src


def test_build_input_manifest_json_is_valid_json(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("nota")
    raw = [_Raw(id="txt1", kind="text", path_or_url=str(f), metadata={})]
    s = build_input_manifest_json(raw)
    assert json.loads(s)["sources"][0]["id"] == "txt1"
