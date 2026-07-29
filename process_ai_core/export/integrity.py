"""
Verificación de que el PDF producido tiene TODAS las imágenes del documento.

WeasyPrint no lanza cuando una imagen no se puede resolver: la omite y termina
el render igual. Para un preview eso es tolerable — el usuario lo ve. Para el
artefacto de auditoría no: el PDF se sube, se le calcula el SHA-256 y queda
registrado como el documento oficial, sin las evidencias y sin ninguna señal.

Un freeze fallido es recuperable (tiene reintento). Un artefacto silenciosamente
incompleto, dado por bueno, no. Por eso acá se aborta.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class IncompletePdfError(RuntimeError):
    """El PDF renderizado no contiene todas las imágenes que el documento referencia."""


def count_embedded_images(pdf_bytes: bytes) -> int:
    """
    Cuenta XObjects de imagen DISTINTOS en el PDF.

    Distintos y no apariciones: WeasyPrint deduplica por URL, así que una imagen
    usada dos veces se embebe una sola vez (verificado). Contar apariciones daría
    un número que no se puede comparar con nada.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return len({img[0] for page in range(len(doc)) for img in doc.get_page_images(page)})
    finally:
        doc.close()


def verify_pdf_images(pdf_bytes: bytes, fetcher, *, contexto: str = "") -> None:
    """
    Aborta si el PDF perdió imágenes por el camino.

    Dos controles, en orden de precisión:

    1. **Fallos de resolución registrados por el fetcher.** Es el control fino:
       sabe exactamente qué URL no se pudo leer. Cubre el modo de falla que
       motivó todo esto (el asset no está en storage, o storage no responde).

    2. **Conteo de XObjects contra los assets ráster resueltos.** Cubre lo que el
       primero no ve: una imagen que se bajó bien pero WeasyPrint no pudo
       decodificar. Se compara con `<` y no con `!=` a propósito — el PDF trae
       además el logo del cliente y el QR de la portada, que no pasan por este
       fetcher y sumarían de más.

    Raises:
        IncompletePdfError: si falta alguna imagen del documento.
    """
    sufijo = f" ({contexto})" if contexto else ""

    if fetcher.failures:
        detalle = "; ".join(f"{url} → {motivo}" for url, motivo in fetcher.failures.items())
        raise IncompletePdfError(
            f"El PDF se generó sin {len(fetcher.failures)} imagen(es) que el documento "
            f"referencia{sufijo}. No se congela un artefacto incompleto. Detalle: {detalle}"
        )

    esperadas = fetcher.expected_raster_count
    if esperadas == 0:
        return

    embebidas = count_embedded_images(pdf_bytes)
    if embebidas < esperadas:
        raise IncompletePdfError(
            f"El PDF tiene {embebidas} imagen(es) embebida(s) pero el documento "
            f"referencia {esperadas} que se resolvieron correctamente{sufijo}: "
            "alguna no se pudo decodificar. No se congela un artefacto incompleto."
        )

    logger.debug("Integridad de imágenes OK%s: %s embebidas ≥ %s esperadas",
                 sufijo, embebidas, esperadas)
