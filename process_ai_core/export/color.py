"""
Sistema de color del PDF: marca del cliente + contraste calculado.

El workspace configura `primary_color` y `secondary_color` y los ve aplicados en
la UI, pero hasta ahora ningún exportador los usaba — del branding solo se leía
el logo. Acá se resuelven a un juego completo de variables CSS.

El contraste NO se fija a mano. Un cliente con marca amarilla y texto blanco en
el header de tabla produce una tabla ilegible, y es el tipo de cosa que solo se
descubre en producción. Se calcula la luminancia relativa (WCAG 2.1) y se elige
blanco o tinta oscura según cuál contraste mejor.
"""

from __future__ import annotations

import re

#: Par neutro para workspaces que no configuraron marca. Azul pizarra: legible en
#: impresión monocroma y sin connotación de estado (nada de verde "aprobado").
DEFAULT_PRIMARY = "#1f3a5f"
DEFAULT_SECONDARY = "#c8a04a"

#: Tinta del cuerpo. No es negro puro: en impresión el #000 satura y "vibra".
INK = "#14181f"
INK_SOFT = "#4a5361"
INK_FAINT = "#6b7480"

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_hex(color: str | None) -> str | None:
    """Devuelve `#rrggbb` en minúsculas, o None si no es un hex válido."""
    if not color or not isinstance(color, str):
        return None
    match = _HEX_RE.match(color.strip())
    if not match:
        return None
    valor = match.group(1).lower()
    if len(valor) == 3:
        valor = "".join(c * 2 for c in valor)
    return f"#{valor}"


def _channels(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(hex_color: str) -> float:
    """Luminancia relativa según WCAG 2.1 (0 = negro, 1 = blanco)."""

    def lineal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lineal(c) for c in _channels(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """Ratio de contraste WCAG entre dos colores (1:1 a 21:1)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


def on_color(background: str) -> str:
    """
    Color de texto legible sobre `background`: blanco o tinta oscura.

    Se elige por contraste medido, no por una regla fija. Un primary claro
    (amarillo, cian, lima) con texto blanco da una cabecera de tabla ilegible.
    """
    return "#ffffff" if contrast_ratio(background, "#ffffff") >= contrast_ratio(background, INK) else INK


def mix_with_white(hex_color: str, ratio: float) -> str:
    """Aclara un color mezclándolo con blanco. `ratio` 0 = igual, 1 = blanco."""
    r, g, b = _channels(hex_color)
    mezcla = tuple(round((c + (1 - c) * ratio) * 255) for c in (r, g, b))
    return "#%02x%02x%02x" % mezcla


def _darken(hex_color: str, ratio: float) -> str:
    """Oscurece hacia negro. `ratio` 0 = igual, 1 = negro."""
    r, g, b = _channels(hex_color)
    mezcla = tuple(round(c * (1 - ratio) * 255) for c in (r, g, b))
    return "#%02x%02x%02x" % mezcla


def readable_on_white(hex_color: str, *, min_ratio: float = 4.5) -> str:
    """
    Versión del color con contraste suficiente para TEXTO sobre blanco.

    Un color de marca sirve para rellenar (cabecera de tabla, filete) pero no
    siempre para escribir: un amarillo o un lima como color de los h1/h2 da
    títulos que en pantalla se leen a medias y en papel desaparecen. Se oscurece
    lo mínimo necesario hasta alcanzar el ratio AA (4.5:1), conservando el matiz
    — sigue siendo el color del cliente, no un gris genérico.
    """
    if contrast_ratio(hex_color, "#ffffff") >= min_ratio:
        return hex_color
    candidato = hex_color
    for _ in range(20):
        candidato = _darken(candidato, 0.12)
        if contrast_ratio(candidato, "#ffffff") >= min_ratio:
            return candidato
    return INK


def resolve_palette(primary: str | None, secondary: str | None) -> dict[str, str]:
    """
    Juego completo de variables de color a partir de lo que configuró el cliente.

    Cae al par neutro cuando el workspace no definió marca, así que el resultado
    siempre es un documento con identidad — nunca uno a medio pintar.
    """
    p = normalize_hex(primary) or DEFAULT_PRIMARY
    s = normalize_hex(secondary) or DEFAULT_SECONDARY
    return {
        "pdf-primary": p,
        "pdf-secondary": s,
        # Para TEXTO sobre blanco (h1, h2, versión del header). Puede diferir del
        # primary: un color de marca claro no sirve para escribir.
        "pdf-primary-text": readable_on_white(p),
        "pdf-secondary-text": readable_on_white(s),
        # Texto sobre fondo de marca (cabecera de tabla, filetes rellenos).
        "pdf-on-primary": on_color(p),
        # Tinte muy suave del primary para superficies (zebra, fondo del acta).
        "pdf-primary-tint": mix_with_white(p, 0.94),
        "pdf-ink": INK,
        "pdf-ink-soft": INK_SOFT,
        "pdf-ink-faint": INK_FAINT,
        "pdf-border-color": "#dbe2ea",
        "pdf-border-strong": "#c3ccd8",
        "pdf-surface-color": "#f8fafc",
    }
