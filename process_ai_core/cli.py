"""
process_ai_core.cli
===================

Punto de entrada mínimo (CLI "simple") para ejecutar el flujo end-to-end del core:

1) Descubrir insumos crudos en `input/` (audio, video, imágenes, texto).
2) Enriquecerlos (transcribir audio, extraer frames de video, copiar imágenes a `output/assets/`, etc.).
3) Construir un prompt consolidado para el LLM.
4) Pedir al LLM un JSON estructurado (ProcessDocument).
5) Parsear ese JSON a modelos de dominio.
6) Renderizar un Markdown final (y opcionalmente PDF via Pandoc).

Este archivo está pensado para:
- demo local rápida,
- smoke tests manuales,
- validar que el pipeline “no se rompió” al tocar media/doc_engine/export.

Notas importantes
-----------------
- La estructura del documento final (qué secciones se muestran / formato de pasos)
  idealmente la controla `DocumentProfile` y el renderer (`render_markdown`).
  Este `cli.py` es una versión mínima; si tu renderer requiere `profile`, ajustá
  la llamada aquí (o usá el `tools/run_demo.py` que ya tiene perfiles).

- En el pipeline actual, los assets “visuales” se copian (o generan) bajo
  `output/assets/` y el Markdown debe referenciarlos con rutas relativas del tipo:
  `assets/<archivo>` para que Pandoc los resuelva con `cwd=output/`.
"""

from __future__ import annotations

from pathlib import Path

from .config import get_settings
from .doc_engine import build_prompt_from_enriched, parse_process_document, render_markdown
from .export import export_pdf  # Import dentro del paquete
from .ingest import discover_raw_assets
from .llm_client import generate_process_document_json
from .media import enrich_assets


def main() -> None:
    """
    Ejecuta una corrida completa del motor:

    - Lee configuración (settings).
    - Descubre insumos en `./input/`.
    - Enriquece insumos para el prompt (transcripción/copia de imágenes/etc.).
    - Genera JSON con el LLM.
    - Renderiza Markdown (y opcionalmente PDF con Pandoc).
    - Persiste outputs en `settings.output_dir`.

    Raises
    ------
    RuntimeError
        Si no se encuentran insumos en la carpeta `input/`.
    """
    settings = get_settings()
    base = Path(".")

    # 0) Ingesta: detectar insumos crudos dentro de input/
    raw_assets = discover_raw_assets(base / "input")
    if not raw_assets:
        raise RuntimeError("No se encontraron insumos en la carpeta input/.")

    # 1) Enriquecer assets (transcribir / copiar imágenes a output/assets / etc.)
    #
    # Contrato esperado:
    # - Devuelve una lista de EnrichedAsset con extracted_text listo para prompt.
    # - Para imágenes generadas desde video, suele incluir metadata.paso_sugerido.
    enriched = enrich_assets(raw_assets)

    # 2) Construir prompt
    process_name = "Proceso demo generado por process_ai_core"
    prompt = build_prompt_from_enriched(process_name, enriched)

    # 3) LLM: generar JSON (documento estructurado)
    json_str = generate_process_document_json(prompt)

    # 4) Parse + render Markdown
    doc = parse_process_document(json_str)

    # ------------------------------------------------------------
    # Construcción de images_by_step (compatibilidad / demo)
    # ------------------------------------------------------------
    # Este bloque intenta mapear imágenes a pasos cuando:
    # - el EnrichedAsset es kind="image"
    # - y viene metadata.paso_sugerido (normalmente inferido desde video)
    #
    # Para demos: extraemos la ruta 'assets/...' desde extracted_text.
    # En una versión más prolija, esa ruta debería venir en metadata directamente.
    images_by_step: dict[int, list[dict[str, str]]] = {}

    for a in enriched:
        if a.kind != "image":
            continue

        paso = a.metadata.get("paso_sugerido")
        if not paso:
            continue

        try:
            paso_i = int(paso)
        except ValueError:
            # Si alguien puso "paso_3" o algo no numérico, lo ignoramos
            continue

        # Extraer assets/<archivo> desde extracted_text (porque tu pipeline lo genera así):
        # "[IMAGEN:...] ... archivo='assets/loquesea.png'"
        import re

        m = re.search(r"archivo='([^']+)'", a.extracted_text or "")
        if not m:
            continue

        images_by_step.setdefault(paso_i, []).append(
            {
                "title": a.metadata.get("titulo", f"Imagen paso {paso_i}"),
                "path": m.group(1),
            }
        )

    # Render Markdown.
    #
    # NOTA:
    # Si tu `render_markdown` actual requiere `profile` o soporta además
    # `evidence_images`, este CLI puede quedar desactualizado. En ese caso,
    # usá el runner más nuevo (tools/run_demo.py) o ajustá esta llamada.
    md = render_markdown(doc, images_by_step=images_by_step)

    # 5) Persistir outputs
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "proceso_demo.md"
    json_path = output_dir / "proceso_demo.json"
    pdf_name = "proceso_demo.pdf"
    pdf_path = output_dir / pdf_name

    # Guardar JSON (crudo)
    json_path.write_text(json_str, encoding="utf-8")

    # Guardar Markdown
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