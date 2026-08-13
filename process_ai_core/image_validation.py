"""
Validación de imágenes subidas por su CONTENIDO, no por su nombre.

Las subidas validaban solo la extensión (y a veces el `content_type`, que lo
manda el cliente): dos cosas que el que sube elige libremente. Un archivo
llamado `logo.png` que en realidad es otra cosa entraba igual, y después se
sirve de vuelta a los navegadores (icono de marca, imágenes del editor) y lo
parsean Pillow/PyMuPDF al generar el PDF.

Chequear los primeros bytes no es una defensa completa —un PNG válido puede
traer un payload en un chunk— pero corta el caso simple: subir HTML/SVG/script
con extensión de imagen. Es la contraparte de servir con `nosniff`: el archivo
declara lo que es, y el servidor no deja que el navegador adivine otra cosa.

Se hace a mano y sin dependencia nueva porque comparar firmas de formato es
determinístico y corto; lo que NO se escribe a mano —por ser exactamente lo
contrario— es un sanitizador de HTML (ver `html_sanitize.py`).
"""

from __future__ import annotations

#: Firma → extensiones canónicas. Solo formatos ráster: un SVG es XML y puede
#: traer <script>, por eso no está (ver la allow-list de branding).
_FIRMAS: tuple[tuple[bytes, frozenset[str]], ...] = (
    (b"\x89PNG\r\n\x1a\n", frozenset({".png"})),
    (b"\xff\xd8\xff", frozenset({".jpg", ".jpeg"})),
    (b"GIF87a", frozenset({".gif"})),
    (b"GIF89a", frozenset({".gif"})),
    (b"BM", frozenset({".bmp"})),
)

#: WEBP y AVIF son contenedores: la firma no está al principio del archivo.
_CONTENEDORES: tuple[tuple[bytes, bytes, frozenset[str]], ...] = (
    (b"RIFF", b"WEBP", frozenset({".webp"})),
    (b"", b"ftyp", frozenset({".avif", ".heic"})),
)


def extension_real_de_imagen(contenido: bytes) -> str | None:
    """Extensión que corresponde al CONTENIDO, o None si no es una imagen conocida."""
    if not contenido:
        return None
    for firma, extensiones in _FIRMAS:
        if contenido.startswith(firma):
            return sorted(extensiones)[0]
    cabecera = contenido[:32]
    for prefijo, marca, extensiones in _CONTENEDORES:
        if (not prefijo or cabecera.startswith(prefijo)) and marca in cabecera:
            return sorted(extensiones)[0]
    return None


def es_imagen_valida(contenido: bytes, extension_declarada: str) -> bool:
    """
    True si el contenido es una imagen ráster y coincide con lo declarado.

    La coincidencia se evalúa por familia: un `.jpg` y un `.jpeg` son lo mismo,
    y un archivo cuya firma dice PNG no puede llamarse `.webp`.
    """
    real = extension_real_de_imagen(contenido)
    if real is None:
        return False
    declarada = extension_declarada.lower()
    for _, extensiones in _FIRMAS:
        if real in extensiones and declarada in extensiones:
            return True
    for _, _, extensiones in _CONTENEDORES:
        if real in extensiones and declarada in extensiones:
            return True
    return False
