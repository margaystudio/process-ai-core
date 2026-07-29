"""
QR de verificación para la portada.

Lo que el QR resuelve es un problema de papel: una copia impresa no puede
afirmar que sigue vigente — el documento pudo haberse reemplazado por una
versión nueva un minuto después de imprimirlo. El QR apunta a la versión
concreta (por `version_id`) para que quien lo tenga en la mano pueda comprobar
en línea si es la vigente.

Se embebe como data URI y no como archivo: no pasa por el `url_fetcher`, no
depende de storage y no puede faltar en el artefacto.
"""

from __future__ import annotations

import base64
import io
import logging

logger = logging.getLogger(__name__)


def qr_data_uri(url: str, *, box_size: int = 4, border: int = 0) -> str | None:
    """
    PNG del QR como data URI, o None si no se pudo generar.

    Determinístico: mismo texto ⇒ mismos bytes. El QR entra en el PDF congelado,
    así que si variara arruinaría el SHA-256 del artefacto.

    Nivel de corrección de errores M (~15%): un QR impreso y fotocopiado tolera
    algo de degradación sin dejar de leerse.
    """
    if not url:
        return None
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)
        imagen = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        buffer = io.BytesIO()
        # optimize=False: el optimizador de Pillow puede variar entre versiones y
        # esto tiene que dar siempre los mismos bytes.
        imagen.save(buffer, format="PNG", optimize=False)
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception as exc:
        # Un QR ausente degrada la portada, no la invalida: el version_id sigue
        # impreso en texto al lado.
        logger.warning("No se pudo generar el QR de verificación: %s", exc)
        return None
