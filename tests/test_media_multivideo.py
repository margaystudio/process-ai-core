"""Regresión: enrich_assets no debe descartar assets después de un video.

Antes, la rama de video hacía `return` apenas terminaba el primer video, tirando
en silencio todo lo que viniera después (más videos, imágenes, texto, audio).
Ahora usa `continue` y procesa todos los assets.
"""

from __future__ import annotations

import process_ai_core.media as media
from process_ai_core.domain_models import RawAsset


def _stub_video_internals(monkeypatch):
    """Neutraliza ffmpeg/OpenAI del branch de video (sin binarios ni red)."""
    monkeypatch.setattr(media, "_ffmpeg_extract_audio", lambda *a, **k: None)
    monkeypatch.setattr(
        media, "transcribe_audio_with_timestamps",
        lambda *a, **k: {"text": "transcripción del video", "segments": []},
    )
    # Sin pasos => no hay extracción de frames ni selección con IA.
    monkeypatch.setattr(media, "plan_steps_from_transcript_segments", lambda *a, **k: [])


def test_assets_despues_del_video_no_se_descartan(monkeypatch, tmp_path):
    _stub_video_internals(monkeypatch)

    fake_video = tmp_path / "demo.mp4"
    fake_video.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # contenido irrelevante (mockeado)

    raw_assets = [
        RawAsset(id="vid1", kind="video", path_or_url=str(fake_video), metadata={"titulo": "Demo"}),
        # El audio va DESPUÉS del video; con override no necesita transcripción real.
        RawAsset(
            id="aud1", kind="audio", path_or_url="n/a",
            metadata={"extracted_text_override": "texto del audio posterior"},
        ),
    ]

    enriched, _images_by_step, _evidence = media.enrich_assets(raw_assets, output_base=tmp_path)

    ids = {e.id for e in enriched}
    assert "vid1" in ids, "el video debe procesarse"
    assert "aud1" in ids, "el asset posterior al video ya NO debe descartarse (bug fijado)"
