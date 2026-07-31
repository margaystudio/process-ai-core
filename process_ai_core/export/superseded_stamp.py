"""
Sello "VERSIÓN SUPERADA", estampado AL SERVIR el PDF.

El problema
-----------
ISO 9001 exige que los documentos obsoletos estén claramente identificados. Pero
el PDF congelado de la v4 dice "aprobada el 22 de julio de 2026" y eso es verdad
para siempre: no se puede reescribir sin romper el SHA-256 registrado, que es lo
único que prueba que ese archivo es el que se aprobó.

La solución
-----------
El blob en storage NO se toca. El sello se superpone en el momento de la entrega,
sobre una copia en memoria. El artefacto sigue verificando contra su hash; lo que
el usuario descarga lleva la advertencia.

Consecuencia que hay que tener presente
---------------------------------------
El PDF servido con sello NO tiene el mismo SHA-256 que el registrado. Es
inevitable —son bytes distintos— y por eso el endpoint expone el hash original en
una cabecera y permite pedir el blob sin sellar para auditoría. Ver
api/routes/documents/versions.py.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

_COLOR = (0.706, 0.137, 0.094)  # #b42318, el mismo rojo de la marca de invalidación
_FONDO = (0.996, 0.953, 0.949)  # #fef3f2, el tinte de la marca de invalidación


def stamp_superseded(pdf_bytes: bytes, *, vigente_version: int | None) -> bytes:
    """
    Devuelve una copia del PDF con el sello en todas las páginas.

    Best-effort: si el sellado falla se devuelve el PDF original. Un documento
    superado sin sello es un problema; un documento que no se puede abrir es
    peor, y el estado real siempre se puede consultar por el QR.
    """
    # Separador "·" y no "—": las fuentes base-14 del PDF (Helvetica) codifican
    # en Latin-1 y el guion largo (U+2014) queda fuera — se imprimía como "?".
    # El punto medio (U+00B7) sí está. Verificado renderizando.
    texto = "VERSIÓN SUPERADA"
    if vigente_version is not None:
        texto += f" · vigente: v{vigente_version}"

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for pagina in doc:
                _sellar_pagina(fitz, pagina, texto)
            salida = io.BytesIO()
            doc.save(salida)
            return salida.getvalue()
        finally:
            doc.close()
    except Exception as exc:
        logger.warning(
            "No se pudo estampar el sello de versión superada; se sirve el PDF "
            "original sin sello: %s", exc,
        )
        return pdf_bytes


def _sellar_pagina(fitz, pagina, texto: str) -> None:
    """
    Banda superior con el texto, de ancho completo.

    Arriba y no en diagonal a propósito: la marca de agua diagonal ya está
    reservada para "BORRADOR" (invalidación), y usar el mismo tratamiento para
    dos cosas distintas —"no vale todavía" y "ya no vale"— las vuelve
    indistinguibles de un vistazo. Además, arriba se ve incluso si alguien
    imprime y engrapa el documento.
    """
    ancho = pagina.rect.width
    alto_banda = 26

    banda = fitz.Rect(0, 0, ancho, alto_banda)
    # Fondo OPACO, no translúcido. Con un rojo al 10% el sello quedaba ilegible
    # justo donde más importa: sobre el filete de marca de la portada, que es
    # oscuro. El sello tiene que leerse encima de cualquier cosa, así que se
    # pinta un fondo claro sólido y se acepta tapar unos milímetros del borde.
    pagina.draw_rect(banda, color=None, fill=_FONDO, overlay=True)
    pagina.draw_line(
        fitz.Point(0, alto_banda), fitz.Point(ancho, alto_banda),
        color=_COLOR, width=1.4, overlay=True,
    )
    pagina.insert_textbox(
        fitz.Rect(0, 7, ancho, alto_banda),
        texto,
        fontname="hebo",  # Helvetica Bold: de las base-14, no embebe fuente
        fontsize=9.5,
        color=_COLOR,
        align=fitz.TEXT_ALIGN_CENTER,
        overlay=True,
    )
