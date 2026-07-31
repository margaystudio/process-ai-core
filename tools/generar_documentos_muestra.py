#!/usr/bin/env python
"""
Generación de documentos de punta a punta, desde fixtures, hasta el PDF.

POR QUÉ EXISTE
--------------
Durante el Paso 5 apareció un bug —"Contexto" impreso dos veces en el perfil de
gestión— que ningún test unitario detectó y que se vio recién al mirar un
documento completo. No era un bug de una función: era del documento como un todo,
y esa clase de defecto no la agarra un assert sobre un string.

Este script convierte esa mirada en algo repetible. Recorre el pipeline REAL
—JSON -> ProcessDocument -> Markdown -> HTML -> PDF, con el renderer y el
exportador de producción, no con dobles— y deja los PDFs para revisar a ojo.

No llama al LLM: el JSON de entrada es un fixture versionado en el repo. Eso lo
hace determinístico y gratis, que es lo que permite correrlo siempre.

CÓMO SE USA
-----------
    python tools/generar_documentos_muestra.py
    python tools/generar_documentos_muestra.py --salida /tmp/muestras
    python tools/generar_documentos_muestra.py --solo inferido

Es el ÚLTIMO PASO antes de mergear cualquier cambio sobre el renderer, el
exportador o el CSS: se corre, se abren los PDFs, se mergea. Un diff verde en la
suite dice que ninguna afirmación conocida se rompió; no dice que el documento
se siga leyendo bien.

QUÉ COMPARAR AL MIRARLOS
------------------------
- Ninguna sección con el encabezado solo, sin contenido debajo.
- Ninguna sección repetida.
- Los chips `A VALIDAR` acompañan SOLO lo inferido.
- Las tablas de actores, riesgos e indicadores entran en el ancho de la página.
- En el borrador: marca de agua, bloque de invalidación en la primera página y
  la nota al pie. En el aprobado: NADA de eso.
- En el superado: la banda del sello, legible, sin tapar texto.
- La portada del aprobado: código, versión, fechas, vigencia y firmas.

FIXTURES
--------
Están en tools/fixtures_documentos/, uno por escenario que interesa mirar:

    completo_relevado  todos los campos poblados, todo marcado `relevado`
    campos_en_none     lo que no se relevó llega vacío y no se inventa
    inferido           chips `A VALIDAR` en campos de texto y en estructuras
    con_imagenes       evidencias embebidas por el pipeline de assets

Agregar un escenario es agregar un JSON en ese directorio.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta, UTC
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from process_ai_core.domains.processes.builder import ProcessBuilder  # noqa: E402
from process_ai_core.domains.processes.profiles import get_profile  # noqa: E402
from process_ai_core.domains.processes.renderer import render_markdown  # noqa: E402
from process_ai_core.export import export_pdf_from_content  # noqa: E402
from process_ai_core.export.document_context import DocumentContext  # noqa: E402
from process_ai_core.export.superseded_stamp import stamp_superseded  # noqa: E402

FIXTURES = RAIZ / "tools" / "fixtures_documentos"
SALIDA_DEFAULT = RAIZ / "muestras_pdf"
PERFILES = ("operativo", "gestion")

#: Fecha fija: el objetivo es que dos corridas del script den el mismo PDF, así
#: que un `date.today()` acá rompería la única propiedad que lo hace útil para
#: comparar antes y después de un cambio.
HOY = date(2026, 7, 29)
APROBADO_EL = datetime(2026, 7, 29, 14, 30, tzinfo=UTC)


def _contexto(nombre: str, *, estado: str, con_historial: bool = True) -> DocumentContext:
    """
    Contexto de portada/pie según el estado del documento.

    Es lo que decide si el PDF sale con marca de invalidación o sin ella, así que
    las tres variantes salen de acá y no de tres plantillas distintas.
    """
    base = dict(
        code="PRO-CAJ-001",
        title=nombre,
        document_type_label="Procedimiento",
        client_name="Estación de Servicio del Este",
        version_number=3,
        version_id="ver-muestra-0003",
        elaborated_by="Ana Bentancur",
        elaborated_by_role="Consultora de procesos",
        reviewed_by="Martín Sosa",
        reviewed_by_role="Jefe de estación",
        verification_url="https://app.margaystudio.io/verificar/ver-muestra-0003",
    )
    if con_historial:
        base.update(
            supersedes_version_number=2,
            supersedes_approved_at=datetime(2025, 11, 3, 10, 0, tzinfo=UTC),
        )

    if estado == "borrador":
        # Sin aprobación: el PDF tiene que salir con la marca de invalidación.
        return DocumentContext(**base, is_approved=False)

    return DocumentContext(
        **base,
        is_approved=True,
        approved_by="Laura Píriz",
        approved_at=APROBADO_EL,
        validity_until=HOY + timedelta(days=365),
    )


def _generar(fixture: Path, perfil: str, estado: str, salida: Path) -> Path:
    """Un documento: JSON -> ProcessDocument -> Markdown -> HTML -> PDF."""
    payload = json.loads(fixture.read_text())
    documento = ProcessBuilder().parse_document(json.dumps(payload))

    imagenes = None
    if fixture.stem == "con_imagenes":
        # Mismo camino que en producción: el pipeline de assets inserta las
        # imágenes por paso; el modelo nunca escribe Markdown de imágenes.
        imagenes = {
            1: [{"path": "assets/captura_pos.png", "caption": "Ticket Z del POS"}],
            3: [{"path": "assets/captura_pos.png", "caption": "Acta firmada por el testigo"}],
        }

    markdown = render_markdown(documento, get_profile(perfil), images_by_step=imagenes)

    nombre = f"{fixture.stem}__{perfil}__{estado}"
    run_dir = salida / nombre
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "documento.md").write_text(markdown)
    if imagenes:
        destino = run_dir / "assets"
        destino.mkdir(exist_ok=True)
        for archivo in (FIXTURES / "assets").iterdir():
            shutil.copy2(archivo, destino / archivo.name)

    pdf = export_pdf_from_content(
        content=markdown,
        format="markdown",
        run_dir=run_dir,
        pdf_name=f"{nombre}.pdf",
        document_context=_contexto(documento.process_name, estado=estado),
    )

    if estado == "superado":
        # El sello NO se hornea en el render: se estampa al servir, para que el
        # artefacto guardado siga siendo el que se aprobó y su hash siga valiendo.
        # Acá se reproduce ese paso para poder mirar el resultado.
        pdf.write_bytes(_normalizar_para_comparar(stamp_superseded(pdf.read_bytes(), vigente_version=4)))

    return pdf


def _normalizar_para_comparar(pdf_bytes: bytes) -> bytes:
    """
    Congela lo que PyMuPDF genera al azar cada vez que guarda el PDF sellado.

    Son dos cosas: las fechas de creación/modificación y el `/ID` del trailer
    (el identificador de archivo, aleatorio por guardado). Con eso, dos corridas
    del script dan PDFs byte a byte iguales.

    Solo para las muestras. En producción esto no hace falta: el sello se estampa
    al servir y esos bytes no se hashean —el hash registrado es el del artefacto
    original, que no se toca— así que dos descargas distintas puedan diferir es
    irrelevante. Acá sí importa: si el PDF sellado cambia en cada corrida, deja
    de servir para comparar antes y después de un cambio, que es todo el punto.
    """
    try:
        import fitz

        documento = fitz.open(stream=pdf_bytes, filetype="pdf")
        metadatos = documento.metadata or {}
        metadatos.update({"creationDate": "D:20260729143000Z", "modDate": "D:20260729143000Z"})
        documento.set_metadata(metadatos)
        salida = documento.tobytes(garbage=0, deflate=True)
        documento.close()
        # El /ID no se puede fijar desde la API de PyMuPDF, así que se reemplaza
        # sobre los bytes. Es el identificador de archivo del trailer: ningún
        # lector lo usa para nada que importe acá.
        return re.sub(
            rb"/ID\s*\[<[0-9A-Fa-f]*><[0-9A-Fa-f]*>\]",
            b"/ID[<00000000000000000000000000000000><00000000000000000000000000000000>]",
            salida,
            count=1,
        )
    except Exception:
        # Si falla, se devuelve el sellado tal cual: perder determinismo en una
        # muestra es molesto, no perder la muestra.
        return pdf_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("CÓMO SE USA")[0].strip())
    parser.add_argument("--salida", type=Path, default=SALIDA_DEFAULT)
    parser.add_argument("--solo", default=None, help="generar un solo fixture (por nombre)")
    parser.add_argument("--limpiar", action="store_true", help="borrar la salida antes de generar")
    args = parser.parse_args()

    fixtures = sorted(p for p in FIXTURES.glob("*.json"))
    if args.solo:
        fixtures = [p for p in fixtures if p.stem == args.solo]
        if not fixtures:
            print(f"No hay fixture '{args.solo}'. Hay: {[p.stem for p in FIXTURES.glob('*.json')]}")
            return 1

    if args.limpiar and args.salida.exists():
        shutil.rmtree(args.salida)
    args.salida.mkdir(parents=True, exist_ok=True)

    generados: list[Path] = []

    # Cobertura de CONTENIDO: cada fixture en los dos perfiles, aprobado.
    for fixture in fixtures:
        for perfil in PERFILES:
            generados.append(_generar(fixture, perfil, "aprobado", args.salida))

    # Cobertura de ESTADO: un fixture en las tres variantes. Alcanza con uno —
    # lo que cambia entre borrador, aprobado y superado es la portada, la marca
    # de invalidación y el sello, no el contenido.
    referencia = next((f for f in fixtures if f.stem == "completo_relevado"), fixtures[0])
    for estado in ("borrador", "superado"):
        generados.append(_generar(referencia, "gestion", estado, args.salida))

    print(f"\n{len(generados)} PDF(s) en {args.salida}:\n")
    for pdf in generados:
        print(f"  {pdf.stat().st_size / 1024:7.1f} KB  {pdf.relative_to(args.salida)}")

    print(
        "\nAbrilos y compará contra la lista de 'QUÉ COMPARAR AL MIRARLOS' del\n"
        "docstring de este script. Es el último paso antes de mergear un cambio\n"
        "sobre el renderer, el exportador o el CSS."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
