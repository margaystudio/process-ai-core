# tools/run_demo.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from process_ai_core.config import get_settings
from process_ai_core.domain_models import RawAsset
from process_ai_core.engine import run_process_pipeline
from process_ai_core.domains.processes.profiles import get_profile
from process_ai_core.export import export_pdf

"""
tools.run_demo
==============

CLI "demo" para ejecutar el pipeline end-to-end sin base de datos.

Objetivo
--------
Permite validar rápidamente el flujo principal del proyecto:

1) Descubrir insumos (audio / video / evidence / text) desde input/
2) Enriquecerlos (transcripción, extracción de frames, etc.)
3) Construir un prompt "grande" con todo el material
4) Pedir al LLM el documento en JSON (schema definido por prompts)
5) Parsear ese JSON a modelos de dominio (ProcessDocument)
6) Renderizar Markdown usando un DocumentProfile (operativo/gestion)
7) (Opcional) Exportar a PDF con Pandoc

Estructura esperada de carpetas
-------------------------------
Dentro de input_dir (por defecto: ./input):

- input/audio/       -> audios (.m4a, .mp3, .wav)
- input/video/       -> videos (.mp4, .mov, .mkv)
- input/evidence/    -> imágenes sueltas aportadas por usuario (capturas, fotos, etc.)
- input/text/        -> textos (.txt, .md)

Salida
------
En output_dir (por defecto: ./output) se generan:

- proceso_<modo>.json
- proceso_<modo>.md
- proceso_<modo>.pdf (si no se usa --no-pdf)

Notas importantes
-----------------
- Este script NO exige DB; es ideal para iterar rápido.
- `media.enrich_assets()` devuelve:
    enriched: List[EnrichedAsset]
    images_by_step: Dict[int, List[{path,title}]]  (capturas inferidas desde video)
    evidence_images: List[{path,title}]            (imágenes sueltas del usuario)
- `doc_engine.render_markdown()` es quien decide cómo se acomodan esas imágenes.
"""


# Extensiones soportadas por tipo de asset.
AUDIO_EXTS = {".m4a", ".mp3", ".wav"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
TEXT_EXTS = {".txt", ".md"}


def discover_assets(input_dir: Path) -> List[RawAsset]:
    """
    Descubre assets dentro de subcarpetas de `input_dir` y construye RawAsset.

    Esta función es un "ingestor" liviano para el demo.
    En el proyecto ya existe `process_ai_core.ingest.discover_raw_assets` que es
    más general (rglob + sidecars JSON), pero acá se dejó deliberadamente simple
    para el ejemplo.

    Parameters
    ----------
    input_dir:
        Carpeta base de entrada. Se esperan subcarpetas: audio/, video/, evidence/, text/

    Returns
    -------
    List[RawAsset]
        Lista ordenada por carpeta/tipo. Los IDs se generan secuencialmente por tipo:
        - aud1, aud2, ...
        - vid1, vid2, ...
        - img1, img2, ... (evidence)
        - txt1, txt2, ...
    """
    assets: List[RawAsset] = []

    def add_folder(kind: str, sub: str, exts: set[str], prefix: str) -> None:
        """
        Agrega a `assets` todos los archivos en input_dir/sub con extensión soportada.

        Parameters
        ----------
        kind:
            Tipo lógico de asset: "audio" | "video" | "image" | "text"
        sub:
            Nombre de subcarpeta debajo de input_dir
        exts:
            Conjunto de extensiones admitidas
        prefix:
            Prefijo para generar IDs (aud/vid/img/txt)
        """
        folder = input_dir / sub
        if not folder.exists():
            return

        files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts])
        for i, p in enumerate(files, start=1):
            assets.append(
                RawAsset(
                    id=f"{prefix}{i}",
                    kind=kind,  # type: ignore[assignment]
                    path_or_url=str(p),
                    # Metadata mínima para demo. Si querés mayor control,
                    # se recomienda usar ingest.py con sidecars JSON.
                    metadata={"titulo": p.stem},
                )
            )

    add_folder("audio", "audio", AUDIO_EXTS, "aud")
    add_folder("video", "video", VIDEO_EXTS, "vid")

    # ✅ Renombrado: antes "images/", ahora "evidence/"
    # Estas son "imágenes sueltas" aportadas por usuario.
    # No intentamos asignarlas a un paso en input: eso se infiere luego.
    add_folder("image", "evidence", IMAGE_EXTS, "img")

    add_folder("text", "text", TEXT_EXTS, "txt")

    return assets


def build_context_block(
    mode: str,
    audience: str | None,
    detail_level: str | None,
    formality: str | None,
) -> str:
    """
    Construye un bloque de contexto (texto) para anteponer al prompt principal.

    La idea es inyectar "preferencias" de estilo y destinatario sin depender de DB,
    para orientar al modelo (operativo vs gestión, nivel de detalle, formalidad, etc).

    Parameters
    ----------
    mode:
        "operativo" o "gestion". Alineado con DocumentProfile y flags del CLI.
    audience:
        Texto libre indicando la audiencia (ej. "direccion", "administracion", etc.)
    detail_level:
        Texto libre indicando el nivel de detalle (ej. "breve", "estandar", "detallado")
    formality:
        Texto libre indicando formalidad (ej. "baja", "media", "alta")

    Returns
    -------
    str
        Bloque de texto terminado en doble salto de línea, listo para concatenar
        con el prompt "body" construido desde assets enriquecidos.
    """
    lines: list[str] = []
    lines.append("=== CONTEXTO Y PREFERENCIAS ===")

    if mode == "operativo":
        lines.append("- Modo: operativo. Documento corto, directo, entendible por personal de pista/depósito.")
        lines.append("- Priorizá pasos accionables, seguridad, y evidencias simples.")
    else:
        lines.append("- Modo: gestión. Documento útil para encargados/dirección: controles, riesgos y métricas.")
        lines.append("- Incluí resumen ejecutivo breve y puntos críticos de control.")

    if audience:
        lines.append(f"- Audiencia: {audience}")
    if detail_level:
        lines.append(f"- Nivel de detalle: {detail_level}")
    if formality:
        lines.append(f"- Formalidad: {formality}")

    return "\n".join(lines).strip() + "\n\n"


def main() -> None:
    """
    Entry-point del demo.

    Parseo de argumentos
    --------------------
    - --process-name: nombre del proceso (sale en el documento final)
    - --mode: operativo|gestion (afecta prompt + profile de render)
    - --audience: override de audiencia (inyección al prompt)
    - --detail-level: override de detalle (inyección al prompt)
    - --formality: override formalidad (inyección al prompt)
    - --no-pdf: si está presente, no corre export a PDF

    Flujo
    -----
    1) Carga settings desde .env
    2) Descubre assets en input/
    3) Enrich assets (transcribe, frames, evidencia, etc.)
    4) Construye prompt (context_block + build_prompt_from_enriched)
    5) LLM -> JSON
    6) Parse JSON -> ProcessDocument
    7) Render Markdown con profile y evidencias
    8) Persistir json/md y opcionalmente generar PDF
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--process-name", default="Proceso demo", help="Nombre visible del proceso en el documento")
    parser.add_argument("--mode", choices=["operativo", "gestion"], default="operativo")
    parser.add_argument("--audience", default="", help="Override opcional: operativo|rrhh|administracion|direccion")
    parser.add_argument("--detail-level", default="", help="Override opcional: breve|estandar|detallado|mixto")
    parser.add_argument("--formality", default="", help="Override opcional: baja|media|alta")
    parser.add_argument("--no-pdf", action="store_true", help="No generar PDF")
    args = parser.parse_args()

    settings = get_settings()
    input_dir = Path(settings.input_dir)
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_assets = discover_assets(input_dir)
    if not raw_assets:
        raise SystemExit(f"No encontré archivos en {input_dir}/(audio|video|evidence|text)")

    # Instrucciones adicionales de estilo/audiencia (bloque de contexto para el prompt).
    context_block = build_context_block(
        mode=args.mode,
        audience=args.audience.strip() or None,
        detail_level=args.detail_level.strip() or None,
        formality=args.formality.strip() or None,
    )

    profile = get_profile(args.mode)

    # Ejecutar el pipeline completo (ingesta ya se hizo; acá enriquecemos, generamos JSON y renderizamos MD).
    result = run_process_pipeline(
        process_name=args.process_name,
        raw_assets=raw_assets,
        profile=profile,
        context_block=context_block,
    )

    json_str = result["json_str"]

    json_path = output_dir / f"proceso_{args.mode}.json"
    json_path.write_text(json_str, encoding="utf-8")

    md = result["markdown"]
    md_path = output_dir / f"proceso_{args.mode}.md"
    md_path.write_text(md, encoding="utf-8")

    print(f"✅ JSON generado en: {json_path.resolve()}")
    print(f"✅ Documento generado en: {md_path.resolve()}")

    # Export a PDF (Pandoc) opcional.
    if not args.no_pdf:
        try:
            pdf_path = export_pdf(output_dir, md_path, f"proceso_{args.mode}.pdf")
            print(f"📄 PDF generado en: {pdf_path.resolve()}")
        except Exception as e:
            print(f"⚠️ No se pudo generar el PDF. Motivo: {e}")


if __name__ == "__main__":
    main()