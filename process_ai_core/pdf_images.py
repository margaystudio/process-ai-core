"""
Extracción de imágenes de un PDF **conservando su posición en el flujo de lectura**.

El problema
-----------
Hasta acá, un PDF con imágenes embebidas perdía todas sus imágenes por los dos
caminos: al importarlo (la representación derivada quedaba solo con texto) y al
usarlo como insumo de una generación (se convertía a texto y nada más). El
archivo original se conserva, pero lo que se lee en la app y lo que indexa Tyto
es la derivada.

Y en un manual, la captura ES el contenido: "completá estas seis celdas grises"
sin la captura de la planilla no dice nada.

Por qué posicional y no una bolsa de imágenes
---------------------------------------------
Extraer las imágenes a una lista y ponerlas todas al final es exactamente el
error que se sacó del schema con `material_referencia`: imágenes sin contexto,
que el lector no sabe a qué paso corresponden. `page.get_text("dict")` devuelve
los bloques —de texto y de imagen— en orden de lectura, así que se puede
intercalar el flujo y saber qué texto rodea a cada imagen. Ese texto vecino es
después el contexto con el que el modelo decide qué paso ilustra la imagen, y el
insumo del que se genera su descripción.

Un solo punto de extracción, dos consumidores
----------------------------------------------
- `process_ai_core.document_import` → la representación derivada del PDF
  importado conserva sus imágenes en el lugar donde estaban.
- `process_ai_core.media` → un PDF usado como insumo promueve sus imágenes a
  assets de imagen del run, con su contexto textual.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from .config import get_settings
from .core.inference import CHIP_A_VALIDAR

logger = logging.getLogger(__name__)

#: Formatos que sabemos servir y embeber en un PDF. Cualquier otro se descarta:
#: no vale la pena arrastrar un JPX que después WeasyPrint no decodifica.
_EXTENSIONES_SOPORTADAS = {"png", "jpeg", "jpg", "webp", "gif", "bmp"}

#: Cuánto texto vecino se guarda como contexto de cada imagen, por lado.
_CONTEXTO_MAX_CHARS = 400


@dataclass(frozen=True)
class PdfImage:
    """
    Una imagen embebida en un PDF, con todo lo que hace falta para ubicarla.

    Las dimensiones vienen por duplicado a propósito: en píxeles (el bitmap) y en
    **puntos sobre la página** (el tamaño con el que se imprime). Para decidir si
    una imagen es contenido o decoración manda el punto, no el píxel — ver
    `descartar_mobiliario`.
    """

    #: Bytes del bitmap, tal como están embebidos en el PDF.
    data: bytes
    #: Extensión sin punto ("png", "jpeg", ...).
    ext: str
    #: Página donde aparece, 1-based.
    page: int
    #: Orden dentro del documento (1-based, sobre TODAS las imágenes candidatas).
    order: int
    width_px: int
    height_px: int
    #: Ancho/alto con los que se dibuja sobre la página, en puntos (1 pt = 1/72").
    width_pt: float
    height_pt: float
    #: Texto inmediatamente anterior y posterior en el flujo de lectura.
    text_before: str
    text_after: str
    #: xref del objeto en el PDF (0 si no se pudo determinar).
    xref: int
    #: SHA-256 de `data`. Identidad de la imagen: es lo que permite detectar la
    #: misma imagen repetida en varias páginas aunque el PDF la haya re-embebido
    #: con otro xref.
    sha256: str

    @property
    def context(self) -> str:
        """Contexto textual completo (lo de antes + lo de después)."""
        partes = [p for p in (self.text_before.strip(), self.text_after.strip()) if p]
        return "\n".join(partes)

    def filename(self, stem: str) -> str:
        """Nombre de archivo estable para esta imagen dentro de un contenedor."""
        return f"{stem}_img{self.order:02d}.{'jpg' if self.ext == 'jpeg' else self.ext}"


@dataclass
class FlowItem:
    """Un ítem del flujo de lectura del PDF: o texto, o una imagen que sobrevivió."""

    kind: Literal["text", "image"]
    text: str = ""
    image: PdfImage | None = None


@dataclass
class PdfContent:
    """Resultado de la extracción: el flujo de lectura + las imágenes que quedaron."""

    flow: list[FlowItem] = field(default_factory=list)
    images: list[PdfImage] = field(default_factory=list)
    #: motivo → cuántas se descartaron por él. Para ajustar umbrales con
    #: documentos reales sin tener que instrumentar nada.
    discarded: Counter = field(default_factory=Counter)
    pages: int = 0

    @property
    def text(self) -> str:
        """Solo el texto del flujo, en orden."""
        return "\n\n".join(i.text for i in self.flow if i.kind == "text" and i.text.strip())

    @property
    def looks_scanned(self) -> bool:
        """
        True si el PDF parece escaneado (páginas que son una foto, sin texto).

        Mismo umbral que usa el fallback a OCR de `media._extract_text_from_document`.
        Importa acá porque en un PDF escaneado las "imágenes embebidas" son las
        páginas enteras: promoverlas duplicaría el documento adentro de sí mismo.
        El original se conserva igual, así que no se pierde nada.
        """
        if self.pages <= 0:
            return False
        return len(self.text.strip()) / self.pages < get_settings().ocr_pdf_min_chars_per_page


# ============================================================
# Extracción
# ============================================================


def _texto_del_bloque(bloque: dict) -> str:
    """Texto plano de un bloque de tipo 0, respetando los saltos de línea."""
    lineas = []
    for linea in bloque.get("lines") or []:
        spans = "".join(s.get("text", "") for s in linea.get("spans") or [])
        if spans.strip():
            lineas.append(spans)
    return "\n".join(lineas).strip()


def _recortar_final(texto: str, limite: int = _CONTEXTO_MAX_CHARS) -> str:
    """Se queda con los últimos `limite` caracteres (el contexto más cercano)."""
    texto = texto.strip()
    return texto if len(texto) <= limite else "…" + texto[-limite:]


def _recortar_inicio(texto: str, limite: int = _CONTEXTO_MAX_CHARS) -> str:
    """Se queda con los primeros `limite` caracteres."""
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[:limite] + "…"


def _xrefs_por_bloque(pagina) -> dict[int, int]:
    """
    Mapa `number` del bloque → xref del objeto imagen.

    `get_text("dict")` da los bytes pero no el xref; `get_image_info(xrefs=True)`
    da el xref y el mismo `number` de bloque. Se cruzan por ahí.
    """
    try:
        return {
            info["number"]: int(info.get("xref") or 0)
            for info in pagina.get_image_info(xrefs=True)
            if "number" in info
        }
    except Exception as exc:  # noqa: BLE001 — el xref es informativo, no crítico
        logger.debug("No se pudieron leer los xrefs de la página: %s", exc)
        return {}


def _flujo_bruto(doc) -> tuple[list[FlowItem], list[PdfImage]]:
    """
    Una sola pasada: devuelve el flujo de lectura completo (texto + TODAS las
    imágenes candidatas) y la lista de candidatas.

    El filtro de mobiliario se aplica después, sobre el conjunto completo, porque
    uno de sus criterios —la repetición— solo se puede evaluar mirando el
    documento entero.
    """
    flujo: list[FlowItem] = []
    candidatas: list[PdfImage] = []

    for indice_pagina, pagina in enumerate(doc, start=1):
        # `sort=True` ordena los bloques por posición vertical en vez de por el
        # orden del content stream. No es lo mismo: el stream refleja en qué
        # orden el generador dibujó las cosas, y hay PDFs que dibujan todo el
        # texto y después las imágenes — con lo que TODA imagen quedaría al final
        # de su página, que es justamente el resultado que este módulo existe
        # para evitar. Verificado: con el orden del stream, un PDF armado así
        # ponía la captura después del pie de página.
        bloques = pagina.get_text("dict", sort=True).get("blocks") or []
        xrefs = _xrefs_por_bloque(pagina)
        textos = [_texto_del_bloque(b) if b.get("type") == 0 else "" for b in bloques]

        for i, bloque in enumerate(bloques):
            if bloque.get("type") != 1:
                if textos[i]:
                    flujo.append(FlowItem(kind="text", text=textos[i]))
                continue

            data = bloque.get("image")
            if not data:
                continue
            data = bytes(data)
            x0, y0, x1, y1 = bloque.get("bbox") or (0.0, 0.0, 0.0, 0.0)
            imagen = PdfImage(
                data=data,
                ext=(bloque.get("ext") or "png").lower(),
                page=indice_pagina,
                order=len(candidatas) + 1,
                width_px=int(bloque.get("width") or 0),
                height_px=int(bloque.get("height") or 0),
                width_pt=round(abs(x1 - x0), 2),
                height_pt=round(abs(y1 - y0), 2),
                # El contexto es el bloque de texto más cercano a cada lado: es lo
                # que dice de qué se trata la captura.
                text_before=_recortar_final(next((t for t in reversed(textos[:i]) if t), "")),
                text_after=_recortar_inicio(next((t for t in textos[i + 1:] if t), "")),
                xref=xrefs.get(bloque.get("number"), 0),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            candidatas.append(imagen)
            flujo.append(FlowItem(kind="image", image=imagen))

    return flujo, candidatas


# ============================================================
# Filtro del mobiliario
# ============================================================


def descartar_mobiliario(
    candidatas: list[PdfImage],
    *,
    min_lado_pt: float | None = None,
    min_lado_px: int | None = None,
    max_relacion_aspecto: float | None = None,
    paginas_repetida: int | None = None,
) -> tuple[list[PdfImage], Counter]:
    """
    Separa el contenido del mobiliario: logos, membretes, filetes, firmas.

    No toda imagen de un PDF es contenido. Si se promueven todas, un documento
    generado termina con el logo del organismo repetido siete veces. Los tres
    criterios, y por qué funcionan:

    1. **Tamaño EN PUNTOS SOBRE LA PÁGINA, no en píxeles.** Una imagen de 2000 px
       escalada a 2 cm es decorativa; una de 400 px que ocupa media página es
       contenido. El píxel miente sobre la intención, el punto no. Se descarta
       además por píxel mínimo, pero solo para atajar iconos diminutos estirados.
    2. **Repetición en varias páginas.** Una imagen que aparece en todas las
       páginas es mobiliario, no información. Se identifica por hash de bytes y
       no por xref: un PDF puede re-embeber el mismo logo con xrefs distintos.
    3. **Relaciones de aspecto extremas.** Filetes y separadores.

    Los umbrales son configurables (ver `config.Settings`) porque el punto justo
    depende del corpus; por eso también se loguea cuántas se descartaron y por
    qué, para poder ajustarlos con documentos reales.

    Returns:
        (sobrevivientes, motivos_descartados)
    """
    settings = get_settings()
    min_lado_pt = settings.pdf_image_min_side_pt if min_lado_pt is None else min_lado_pt
    min_lado_px = settings.pdf_image_min_side_px if min_lado_px is None else min_lado_px
    max_relacion_aspecto = (
        settings.pdf_image_max_aspect_ratio
        if max_relacion_aspecto is None
        else max_relacion_aspecto
    )
    paginas_repetida = (
        settings.pdf_image_repeat_pages if paginas_repetida is None else paginas_repetida
    )

    paginas_por_hash: dict[str, set[int]] = {}
    for img in candidatas:
        paginas_por_hash.setdefault(img.sha256, set()).add(img.page)

    sobrevivientes: list[PdfImage] = []
    motivos: Counter = Counter()

    for img in candidatas:
        if img.ext not in _EXTENSIONES_SOPORTADAS:
            motivos[f"formato_no_soportado:{img.ext}"] += 1
            continue
        if len(paginas_por_hash[img.sha256]) >= paginas_repetida:
            motivos["repetida_en_varias_paginas"] += 1
            continue
        if img.width_pt < min_lado_pt or img.height_pt < min_lado_pt:
            motivos["chica_en_puntos"] += 1
            continue
        if img.width_px < min_lado_px or img.height_px < min_lado_px:
            motivos["chica_en_pixeles"] += 1
            continue
        lado_menor = min(img.width_pt, img.height_pt)
        if lado_menor > 0 and max(img.width_pt, img.height_pt) / lado_menor > max_relacion_aspecto:
            motivos["relacion_de_aspecto_extrema"] += 1
            continue
        sobrevivientes.append(img)

    return sobrevivientes, motivos


# ============================================================
# API pública
# ============================================================


def extract_pdf_content(data: bytes, *, nombre: str = "documento.pdf") -> PdfContent:
    """
    Extrae el flujo de lectura de un PDF: texto + imágenes que son contenido.

    El flujo intercala los bloques de texto y las imágenes que sobrevivieron al
    filtro de mobiliario, en el orden en que se leen. Las descartadas no aparecen
    en ningún lado (pero se cuentan por motivo, y eso se loguea).

    Degradación: cualquier fallo devuelve un `PdfContent` vacío. Ni la
    importación ni la generación se rompen porque un PDF venga raro.
    """
    contenido = PdfContent()
    try:
        import fitz  # PyMuPDF
    except ImportError:  # pragma: no cover — es dependencia dura
        logger.warning("PyMuPDF no disponible: '%s' se procesa sin imágenes.", nombre)
        return contenido

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo abrir '%s' para extraer imágenes: %s", nombre, exc)
        return contenido

    try:
        contenido.pages = len(doc)
        flujo, candidatas = _flujo_bruto(doc)
        conservadas, motivos = descartar_mobiliario(candidatas)
        contenido.images = conservadas
        contenido.discarded = motivos

        if candidatas:
            logger.info(
                "PDF '%s': %d imagen(es) embebida(s), %d conservada(s), %d descartada(s)%s",
                nombre,
                len(candidatas),
                len(conservadas),
                len(candidatas) - len(conservadas),
                f" ({dict(motivos)})" if motivos else "",
            )

        ordenes_conservados = {img.order for img in conservadas}
        contenido.flow = [
            item
            for item in flujo
            if item.kind == "text" or (item.image and item.image.order in ordenes_conservados)
        ]

        # PDF escaneado: sus "imágenes" son las páginas. Se descartan las dos
        # cosas (la lista y el flujo) para que los dos consumidores caigan a su
        # camino de texto normal —que para un escaneado es el OCR— sin tener que
        # repetir esta regla cada uno por su lado.
        if contenido.images and contenido.looks_scanned:
            logger.info(
                "PDF '%s' parece escaneado (%.0f caracteres por página): sus %d "
                "imagen(es) son páginas, no contenido; no se promueven.",
                nombre,
                len(contenido.text.strip()) / max(contenido.pages, 1),
                len(contenido.images),
            )
            contenido.discarded["pdf_escaneado"] += len(contenido.images)
            contenido.images = []
            contenido.flow = [i for i in contenido.flow if i.kind == "text"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo extrayendo el contenido de '%s': %s", nombre, exc)
        return PdfContent()
    finally:
        doc.close()

    return contenido


def extract_pdf_images(data: bytes, *, nombre: str = "documento.pdf") -> list[PdfImage]:
    """Solo las imágenes que son contenido, en orden de lectura."""
    return extract_pdf_content(data, nombre=nombre).images


# ============================================================
# Descripción para el índice semántico
# ============================================================


@dataclass(frozen=True)
class ImageDescription:
    """Descripción generada con visión. **Inferencia pura**: nadie la validó."""

    titulo: str
    descripcion: str


_MIME_POR_EXT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
}


def describe_image(image: PdfImage, *, nombre: str = "") -> ImageDescription | None:
    """
    Describe la imagen con un modelo de visión, usando su contexto textual.

    Por qué en la ingesta y no en cada consulta
    -------------------------------------------
    Meter la imagen en el HTML no ayuda a Tyto: Tyto indexa texto. Si el paso
    clave de un procedimiento es una captura de qué celdas completar, sin esto esa
    información no existe en la capa semántica. Se paga **una** llamada de visión
    por imagen, en el momento de la ingesta, y queda guardada junto al asset e
    indexada con el resto del documento. Describir en cada consulta costaría lo
    mismo por cada pregunta que alguien haga, para siempre.

    Se puede apagar con `PDF_IMAGE_DESCRIBE=false`: las imágenes se conservan
    igual, lo que se pierde es su descripción (y con ella, su indexabilidad).

    Best-effort: cualquier fallo devuelve None. Una imagen sin descripción es
    peor que una con descripción, pero una importación rota es mucho peor.
    """
    if not get_settings().pdf_image_describe:
        return None
    try:
        from .ai.factory import get_vision_provider

        salida = get_vision_provider().describe_image(
            data=image.data,
            mime_type=_MIME_POR_EXT.get(image.ext, "image/png"),
            context=image.context,
        )
        descripcion = (salida.get("descripcion") or "").strip()
        titulo = (salida.get("titulo") or "").strip()
        if not descripcion and not titulo:
            return None
        return ImageDescription(titulo=titulo, descripcion=descripcion)
    except Exception as exc:  # noqa: BLE001 — la visión jamás rompe la ingesta
        logger.warning(
            "No se pudo describir la imagen %d de '%s' (%s): queda sin descripción "
            "y por lo tanto fuera del índice semántico.",
            image.order, nombre or "PDF", exc,
        )
        return None


def figure_title(image: PdfImage, description: ImageDescription | None) -> str:
    """Título de la figura: el que infirió la visión, o uno derivado de la posición."""
    if description and description.titulo:
        return description.titulo
    return f"Figura {image.order} (pág. {image.page})"


def figure_markdown(
    image: PdfImage,
    url: str,
    description: ImageDescription | None,
) -> str:
    """
    Markdown de una figura: la imagen y, debajo, su descripción marcada.

    La descripción va al pie y no como `alt` a propósito: el `alt` no se imprime
    ni se indexa como texto del documento, y el punto de describir la imagen es
    justamente que su contenido exista en la capa semántica. Y lleva el chip
    porque es inferencia sin validar, igual que cualquier otro contenido inferido.
    """
    titulo = figure_title(image, description)
    partes = [f"![{titulo}]({url})", ""]
    if description and description.descripcion:
        partes.append(f"*{titulo}.* {description.descripcion} {CHIP_A_VALIDAR}")
        partes.append("")
    return "\n".join(partes)
