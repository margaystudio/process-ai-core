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
from .document_profiles import get_profile
from .engine import run_process_pipeline
from .export import export_pdf  # Import dentro del paquete
from .ingest import discover_raw_assets


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

    # 1) Seleccionar un perfil de documento simple (por defecto usamos gestión)
    profile = get_profile("gestion")

    # 2) Ejecutar el pipeline completo en memoria (sin I/O de archivos)
    result = run_process_pipeline(
        process_name="Proceso demo generado por process_ai_core",
        raw_assets=raw_assets,
        profile=profile,
        context_block=None,
    )

    json_str = result["json_str"]
    md = result["markdown"]

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