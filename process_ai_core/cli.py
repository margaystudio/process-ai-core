from pathlib import Path

from .models import RawAsset
from .media import enrich_assets
from .engine import (
    build_prompt_from_enriched,
    parse_process_document,
    render_markdown,
)
from .llm_client import generate_process_document_json
from .config import get_settings


def main():
    settings = get_settings()
    base = Path(".")

    # Hardcode inicial de insumos crudos para probar
    raw_assets = [
        RawAsset(
            id="audio1",
            kind="audio",
            path_or_url=str(base / "input" / "audio" / "reunion_demo.m4a"),
            metadata={"titulo": "Reunión demo sobre un proceso"},
        ),
        RawAsset(
            id="txt1",
            kind="text",
            path_or_url=str(base / "input" / "text" / "notas_proceso.txt"),
            metadata={"autor": "Santi"},
        ),
        # a futuro: video, imágenes...
    ]

    enriched = enrich_assets(raw_assets)

    process_name = "Proceso demo generado por process_ai_core"
    prompt = build_prompt_from_enriched(process_name, enriched)

    json_str = generate_process_document_json(prompt)
    doc = parse_process_document(json_str)
    md = render_markdown(doc)

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "proceso_demo.md"
    output_path.write_text(md, encoding="utf-8")

    print(f"✅ Documento generado en: {output_path.resolve()}")


if __name__ == "__main__":
    main()