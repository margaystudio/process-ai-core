from __future__ import annotations

from pathlib import Path

from .models import RawAsset
from .media import enrich_assets
from .engine import build_prompt_from_enriched, parse_process_document, render_markdown
from .llm_client import generate_process_document_json
from .config import get_settings
from .ingest import discover_raw_assets

# Import dentro del paquete (export/ debe estar dentro de process_ai_core/)
from .export import export_pdf


def main() -> None:
    settings = get_settings()
    base = Path(".")

    raw_assets = discover_raw_assets(base / "input")

    if not raw_assets:
        raise RuntimeError("No se encontraron insumos en la carpeta input/.")

    # 1) Enriquecer assets (transcribir / copiar imágenes a output/assets / etc.)
    enriched = enrich_assets(raw_assets)

    # 2) Construir prompt
    process_name = "Proceso demo generado por process_ai_core"
    prompt = build_prompt_from_enriched(process_name, enriched)

    # 3) LLM: generar JSON
    json_str = generate_process_document_json(prompt)

    # 4) Parse + render Markdown
    doc = parse_process_document(json_str)
    md = render_markdown(doc)

    # 5) Persistir outputs
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "proceso_demo.md"
    json_path = output_dir / "proceso_demo.json"
    pdf_name = "proceso_demo.pdf"
    pdf_path = output_dir / pdf_name

    # ✅ Guardar JSON (crudo)
    json_path.write_text(json_str, encoding="utf-8")

    # ✅ Guardar Markdown
    md_path.write_text(md, encoding="utf-8")

    print(f"✅ JSON generado en: {json_path.resolve()}")
    print(f"✅ Documento generado en: {md_path.resolve()}")

    # 6) Export PDF (Pandoc) - en el mismo flujo pero encapsulado
    try:
        export_pdf(run_dir=output_dir, md_path=md_path, pdf_name=pdf_name)
        print(f"📄 PDF generado en: {pdf_path.resolve()}")
    except Exception as e:
        print(f"⚠️ No se pudo generar el PDF con Pandoc. Motivo: {e}")
        print("   Tip: instalá pandoc (brew install pandoc) y reintentá.")


if __name__ == "__main__":
    main()