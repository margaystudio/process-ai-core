"""
Un PDF importado conserva sus imágenes en la representación derivada.

Por qué importa
---------------
El archivo original se guarda y se sirve, así que el expediente estaba completo.
Pero lo que se LEE en la app y lo que INDEXA Tyto es la representación derivada,
y esa quedaba solo con texto: un manual entero cuya única evidencia real —la
captura de la planilla— desaparecía de todo lo que el sistema sabe del documento.

Acá se verifica el camino completo: la imagen se sube como asset de la versión,
el markdown derivado la referencia EN SU POSICIÓN, y el PDF congelado la puede
resolver sin salir a la red (`StorageAssetFetcher`), que es lo que hace que la
verificación de integridad del freeze no aborte.
"""

from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models import Folder, User, Workspace
from process_ai_core.document_import import create_imported_document
from process_ai_core.storage.local import LocalDiskStorage

WS = "ws-import-img"


def _png(color=(30, 90, 160), size=(900, 700)) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def _pdf_con_captura() -> bytes:
    """PDF de dos bloques de texto con una captura en el medio."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Las 6 celdas que tenes que completar:", fontsize=11)
    page.insert_image(fitz.Rect(100, 200, 460, 560), stream=_png())
    page.insert_text((50, 600), "Despues de completar, guardas la planilla.", fontsize=11)
    page.insert_text((50, 700), "Texto de relleno para que la pagina tenga cuerpo real.", fontsize=9)
    salida = doc.tobytes()
    doc.close()
    return salida


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Workspace(id=WS, slug=WS, name="WS", workspace_type="organization"))
    s.add(User(id="user-1", email="user-1@test.com", name="User"))
    s.add(Folder(id="folder-1", workspace_id=WS, name="Carpeta", parent_id=None))
    s.commit()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Storage local + visión apagada (acá no se prueba la descripción)."""
    store = LocalDiskStorage(root=str(tmp_path / "store"))
    import process_ai_core.document_import as di
    import process_ai_core.storage as storage_mod

    monkeypatch.setattr(di, "get_storage", lambda: store)
    monkeypatch.setattr(storage_mod, "get_storage", lambda: store)
    monkeypatch.setenv("PDF_IMAGE_DESCRIBE", "false")

    from process_ai_core.config import get_settings

    get_settings.cache_clear()
    yield store
    get_settings.cache_clear()


def _importar(session, storage, nombre="Manual.pdf"):
    return create_imported_document(
        session=session,
        workspace_id=WS,
        folder_id="folder-1",
        filename=nombre,
        file_bytes=_pdf_con_captura(),
        requires_approval=False,
        user_id="user-1",
    )


def test_la_imagen_del_pdf_llega_a_la_representacion_derivada(session, storage):
    _, version = _importar(session, storage)

    assert "![" in version.content_markdown, "el markdown derivado no tiene la imagen"
    assert "/assets/img01.png" in version.content_markdown
    assert "<img" in (version.content_html or ""), "el HTML congelado no tiene la imagen"


def test_la_imagen_queda_en_su_posicion_original(session, storage):
    _, version = _importar(session, storage)
    md = version.content_markdown

    antes = md.index("Las 6 celdas")
    imagen = md.index("![")
    despues = md.index("Despues de completar")
    assert antes < imagen < despues, "la imagen no quedó donde estaba en el PDF"


def test_la_imagen_se_sube_como_asset_de_la_version(session, storage):
    _, version = _importar(session, storage)

    key = (
        f"workspaces/{WS}/documents/{version.document_id}"
        f"/versions/{version.id}/assets/img01.png"
    )
    assert storage.exists(key)
    assert storage.get(key)[:4] == b"\x89PNG"


def test_las_imagenes_van_tambien_estructuradas_en_el_json(session, storage):
    _, version = _importar(session, storage)
    payload = json.loads(version.content_json)

    (imagen,) = payload["imagenes"]
    assert imagen["asset_id"] == "img01"
    assert imagen["pagina"] == 1
    assert imagen["url"].endswith("/assets/img01.png")
    assert imagen["contexto"], "la imagen perdió su contexto textual"


def test_el_pdf_congelado_resuelve_la_imagen_desde_storage_sin_red(session, storage, tmp_path):
    """
    La reproducibilidad del freeze depende de esto: las imágenes se resuelven por
    el fetcher de storage y entran en la verificación de integridad. Si faltara
    una, `verify_pdf_images` aborta el freeze en vez de congelar un artefacto
    mutilado con su hash ya registrado.
    """
    from process_ai_core.export import (
        ASSET_BASE_URL,
        StorageAssetFetcher,
        export_pdf_from_content,
        verify_pdf_images,
    )

    _, version = _importar(session, storage)

    # Igual que en el freeze: los src del documento apuntan al host centinela.
    from api.routes._freeze import _rewrite_img_src_to_assets

    html = _rewrite_img_src_to_assets(version.content_html)
    assert ASSET_BASE_URL in html

    fetcher = StorageAssetFetcher(
        workspace_id=WS, run_id=None, document_id=version.document_id
    )
    pdf = export_pdf_from_content(
        content=html,
        format="html",
        run_dir=tmp_path,
        pdf_name="congelado.pdf",
        base_url=ASSET_BASE_URL,
        url_fetcher=fetcher,
    )

    assert not fetcher.failures, fetcher.failures
    assert fetcher.expected_raster_count == 1
    verify_pdf_images(pdf.read_bytes(), fetcher)  # no lanza


def test_un_pdf_sin_imagenes_de_contenido_sigue_importandose_igual(session, storage):
    """Sin imágenes, el camino es exactamente el de siempre: solo texto."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 70), "Manual sin imagenes, solo texto corrido y suficiente.", fontsize=11)
    data = doc.tobytes()
    doc.close()

    _, version = create_imported_document(
        session=session,
        workspace_id=WS,
        folder_id="folder-1",
        filename="Solo texto.pdf",
        file_bytes=data,
        requires_approval=False,
        user_id="user-1",
    )

    assert "![" not in version.content_markdown
    assert "Manual sin imagenes" in version.content_markdown
    assert "imagenes" not in json.loads(version.content_json)
