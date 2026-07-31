"""
Extracción posicional de imágenes de un PDF + filtro del mobiliario.

Lo que se protege acá:

1. Que la imagen conserve su POSICIÓN en el flujo de lectura y su contexto
   textual. Una bolsa de imágenes al final del documento es el error que ya se
   sacó del schema con `material_referencia`: el lector no sabe a qué paso
   corresponde cada una.
2. Que el mobiliario (logos, membretes, filetes) NO se promueva, y que el
   contenido SÍ sobreviva a todos los filtros.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from process_ai_core.pdf_images import (
    descartar_mobiliario,
    extract_pdf_content,
    extract_pdf_images,
)

#: PDF de referencia del caso real: 2 páginas, UNA sola imagen embebida en la
#: página 1, de 1819×2573 px, que es claramente contenido (la captura de la
#: planilla que el manual explica). Vive fuera del repo; si no está, se saltea.
PDF_REFERENCIA = Path.home() / "Downloads" / "Manual IRPF - Anticipo Bimestral 2026.pdf"


def _png(color=(30, 90, 160), size=(400, 300)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


#: Texto de relleno al pie de cada página. Sin él, un PDF de prueba con dos
#: frases sueltas dispara la heurística de "PDF escaneado" (pocos caracteres por
#: página) y el módulo no promueve ninguna imagen — que es lo correcto, pero
#: convierte cada test en un falso negativo.
_RELLENO = [
    "Texto de relleno del cuerpo del documento para que la pagina tenga contenido real.",
    "Segunda linea de relleno con suficiente cantidad de caracteres por pagina.",
]


def _pdf(paginas: list[dict], relleno: bool = True) -> bytes:
    """
    Arma un PDF de prueba.

    Cada página es `{"texto": [(punto_y, texto), ...], "imagenes": [(rect, png)]}`
    con el rect en PUNTOS sobre la página, que es lo que mira el filtro.
    """
    import fitz

    doc = fitz.open()
    for spec in paginas:
        page = doc.new_page()
        for y, texto in spec.get("texto", []):
            page.insert_text((50, y), texto, fontsize=11)
        if relleno:
            for i, linea in enumerate(_RELLENO):
                page.insert_text((50, 790 + i * 14), linea, fontsize=8)
        for rect, png in spec.get("imagenes", []):
            page.insert_image(fitz.Rect(*rect), stream=png)
    salida = doc.tobytes()
    doc.close()
    return salida


@pytest.fixture(autouse=True)
def sin_visión(monkeypatch):
    """La descripción con visión sale de la ecuación: acá se prueba extracción."""
    monkeypatch.setenv("PDF_IMAGE_DESCRIBE", "false")
    from process_ai_core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Extracción posicional ────────────────────────────────────────────────────


def test_la_imagen_queda_en_su_lugar_del_flujo_y_no_al_final():
    pdf = _pdf(
        [
            {
                "texto": [(70, "Las 6 celdas que tenes que completar:")],
                "imagenes": [((100, 200, 450, 600), _png())],
                # El texto de después se inserta más abajo que la imagen.
            }
        ]
    )
    contenido = extract_pdf_content(pdf, nombre="manual.pdf")

    tipos = [item.kind for item in contenido.flow]
    assert "image" in tipos, "la imagen no llegó al flujo"
    # No está al final: hay texto antes de la imagen.
    assert tipos.index("image") > 0
    assert len(contenido.images) == 1


def test_la_imagen_viaja_con_el_texto_que_la_rodea():
    pdf = _pdf(
        [
            {
                "texto": [(70, "Antes de la captura"), (700, "Despues de la captura")],
                "imagenes": [((100, 200, 450, 600), _png())],
            }
        ]
    )
    (imagen,) = extract_pdf_images(pdf)

    assert "Antes de la captura" in imagen.text_before
    assert "Despues de la captura" in imagen.text_after
    assert "Antes de la captura" in imagen.context


def test_devuelve_pagina_orden_y_dimensiones_en_puntos_ademas_de_pixeles():
    pdf = _pdf(
        [
            {"texto": [(70, "Pagina uno")]},
            {
                "texto": [(70, "Pagina dos")],
                "imagenes": [((100, 200, 460, 560), _png(size=(800, 800)))],
            },
        ]
    )
    (imagen,) = extract_pdf_images(pdf)

    assert imagen.page == 2
    assert imagen.order == 1
    assert imagen.width_px == 800 and imagen.height_px == 800
    # El tamaño sobre la página es el del rect donde se dibujó, no el del bitmap.
    assert 350 < imagen.width_pt < 370
    assert 350 < imagen.height_pt < 370
    assert imagen.sha256


# ── Filtro del mobiliario ────────────────────────────────────────────────────


def test_descarta_el_logo_que_se_repite_en_todas_las_paginas():
    logo = _png((10, 10, 10), size=(300, 300))
    contenido_grande = _png((200, 30, 30), size=(900, 700))
    pdf = _pdf(
        [
            {
                "texto": [(70, "Encabezado")],
                "imagenes": [((40, 30, 120, 110), logo), ((80, 200, 500, 600), contenido_grande)],
            },
            {"texto": [(70, "Segunda")], "imagenes": [((40, 30, 120, 110), logo)]},
        ]
    )
    contenido = extract_pdf_content(pdf, nombre="con_logo.pdf")

    assert len(contenido.images) == 1, "sobrevivió el logo o se perdió el contenido"
    assert contenido.images[0].width_pt > 300
    assert contenido.discarded["repetida_en_varias_paginas"] == 2


def test_descarta_por_tamano_en_puntos_aunque_tenga_muchos_pixeles():
    """
    El píxel miente sobre la intención: una imagen de 2000 px escalada a 2 cm es
    decorativa. El punto sobre la página no miente.
    """
    sello = _png(size=(2000, 2000))
    pdf = _pdf([{"texto": [(70, "Firma")], "imagenes": [((40, 100, 90, 150), sello)]}])

    contenido = extract_pdf_content(pdf, nombre="sello.pdf")

    assert contenido.images == []
    assert contenido.discarded["chica_en_puntos"] == 1


def test_descarta_los_filetes_por_relacion_de_aspecto():
    # Suficientemente grande en los dos lados como para pasar el filtro de
    # tamaño: lo que la descarta es la proporción (500 × 60 pt ⇒ 8,3:1).
    filete = _png(size=(1200, 144))
    pdf = _pdf([{"texto": [(70, "Titulo")], "imagenes": [((40, 100, 540, 160), filete)]}])

    contenido = extract_pdf_content(pdf, nombre="filete.pdf")

    assert contenido.images == []
    assert contenido.discarded["relacion_de_aspecto_extrema"] == 1


def test_los_umbrales_son_configurables():
    filete = _png(size=(1200, 144))
    pdf = _pdf([{"texto": [(70, "Titulo")], "imagenes": [((40, 100, 540, 160), filete)]}])
    candidatas = []

    import fitz

    from process_ai_core.pdf_images import _flujo_bruto

    doc = fitz.open(stream=pdf, filetype="pdf")
    try:
        _, candidatas = _flujo_bruto(doc)
    finally:
        doc.close()

    estrictos, _ = descartar_mobiliario(candidatas)
    permisivos, _ = descartar_mobiliario(
        candidatas, min_lado_pt=1, max_relacion_aspecto=100, paginas_repetida=99, min_lado_px=1
    )
    assert estrictos == []
    assert len(permisivos) == 1


def test_un_pdf_escaneado_no_promueve_sus_paginas_como_imagenes():
    """
    En un escaneado la "imagen embebida" es la página entera. Promoverla
    duplicaría el documento adentro de sí mismo — y el original se conserva igual.
    """
    pagina_escaneada = _png(size=(1700, 2200))
    pdf = _pdf([{"imagenes": [((0, 0, 595, 842), pagina_escaneada)]}], relleno=False)

    contenido = extract_pdf_content(pdf, nombre="escaneado.pdf")

    assert contenido.images == []
    assert contenido.discarded["pdf_escaneado"] == 1


# ── Un solo motor de texto ───────────────────────────────────────────────────


def test_el_texto_derivado_no_depende_de_si_la_imagen_pasa_el_filtro():
    """
    El mismo PDF con una captura de 55 pt y con una de 57 pt tiene que producir
    EL MISMO texto. Cuando convivían dos extractores, el de abajo del umbral iba
    por pypdf y el de arriba por PyMuPDF, y los dos no coinciden en espaciados,
    ligaduras ni columnas: un umbral de tamaño de imagen decidía el texto del
    documento. `content_html` es entrada congelada del artefacto de auditoría,
    así que esa costura es de la misma clase que la versión del motor de render.
    """
    from process_ai_core.media import _extract_text_from_document

    cuerpo = [(70, "Procedimiento de cierre de caja."), (120, "Paso 1: contar el efectivo.")]
    imagen = _png(size=(600, 600))

    textos = []
    for lado in (50, 400):  # una descartada por chica, la otra conservada
        pdf = _pdf([{"texto": cuerpo, "imagenes": [((100, 200, 100 + lado, 200 + lado), imagen)]}])
        contenido = extract_pdf_content(pdf, nombre=f"lado{lado}.pdf")
        textos.append(contenido.text)

    # El filtro efectivamente decide distinto en cada caso...
    chico = extract_pdf_content(
        _pdf([{"texto": cuerpo, "imagenes": [((100, 200, 150, 250), imagen)]}])
    )
    grande = extract_pdf_content(
        _pdf([{"texto": cuerpo, "imagenes": [((100, 200, 500, 600), imagen)]}])
    )
    assert len(chico.images) == 0 and len(grande.images) == 1
    # ...y aun así el texto es idéntico.
    assert textos[0] == textos[1]
    assert chico.text == grande.text

    # Y es el mismo texto que ve el resto del pipeline por la vía normal.
    import tempfile
    from pathlib import Path as _Path

    with tempfile.TemporaryDirectory() as tmp:
        archivo = _Path(tmp) / "doc.pdf"
        archivo.write_bytes(
            _pdf([{"texto": cuerpo, "imagenes": [((100, 200, 500, 600), imagen)]}])
        )
        assert _extract_text_from_document(archivo) == grande.text


# ── Caso de referencia ───────────────────────────────────────────────────────


@pytest.mark.skipif(not PDF_REFERENCIA.exists(), reason="PDF de referencia no disponible")
def test_el_pdf_de_referencia_conserva_su_unica_imagen():
    contenido = extract_pdf_content(PDF_REFERENCIA.read_bytes(), nombre=PDF_REFERENCIA.name)

    assert len(contenido.images) == 1
    imagen = contenido.images[0]
    assert imagen.page == 1
    assert (imagen.width_px, imagen.height_px) == (1819, 2573)
    # Sobrevive a TODOS los filtros: ocupa media página, no se repite, no es un filete.
    assert imagen.width_pt > 400 and imagen.height_pt > 500
    assert "celdas" in imagen.text_before

    # Y está en su lugar: hay texto antes y texto después.
    tipos = [i.kind for i in contenido.flow]
    posicion = tipos.index("image")
    assert posicion > 0 and posicion < len(tipos) - 1
