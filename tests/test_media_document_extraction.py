from pathlib import Path
import logging
import sys
import types

import pytest

import process_ai_core.ai.factory as ai_factory
from process_ai_core.ai.ocr_provider import TesseractNotAvailableError
from process_ai_core.media import _extract_text_from_document


def test_extract_text_from_txt_and_md(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    md = tmp_path / "notes.md"
    txt.write_text("hola mundo", encoding="utf-8")
    md.write_text("# titulo\ncontenido", encoding="utf-8")

    assert _extract_text_from_document(txt) == "hola mundo"
    assert _extract_text_from_document(md) == "# titulo\ncontenido"


def test_extract_text_from_pdf_with_mocked_pypdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 mock")

    class _Page:
        def __init__(self, text: str):
            self._text = text

        def extract_text(self):
            return self._text

    class _Reader:
        def __init__(self, _path):
            self.pages = [_Page("pagina 1"), _Page("pagina 2")]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=_Reader))

    extracted = _extract_text_from_document(pdf)
    assert extracted == "pagina 1\n\npagina 2"


def test_extract_text_from_docx_with_mocked_python_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    docx = tmp_path / "doc.docx"
    docx.write_bytes(b"PK\x03\x04")

    class _Paragraph:
        def __init__(self, text: str):
            self.text = text

    class _Doc:
        def __init__(self):
            self.paragraphs = [_Paragraph("linea 1"), _Paragraph("   "), _Paragraph("linea 2")]

    def _document_factory(_path):
        return _Doc()

    monkeypatch.setitem(sys.modules, "docx", types.SimpleNamespace(Document=_document_factory))

    extracted = _extract_text_from_document(docx)
    assert extracted == "linea 1\n\nlinea 2"


def test_extract_text_from_doc_raises_clear_error(tmp_path: Path):
    legacy_doc = tmp_path / "legacy.doc"
    legacy_doc.write_bytes(b"mock")

    with pytest.raises(ValueError, match=".doc"):
        _extract_text_from_document(legacy_doc)


def test_extract_text_from_real_text_pdf_uses_pypdf_not_ocr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """PDF con capa de texto real: pypdf alcanza, el OCR NO debe invocarse."""
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "con_texto.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Procedimiento de apertura de estacion.\n"
        "Paso 1: encender el sistema.\n"
        "Paso 2: verificar surtidores.",
    )
    doc.save(str(pdf_path))
    doc.close()

    # Si por algún motivo se cae al OCR, que el test falle en vez de degradar.
    def _fail_ocr():
        raise AssertionError("no debería instanciarse el OCR para un PDF con texto")

    monkeypatch.setattr(ai_factory, "get_ocr_provider", _fail_ocr)

    extracted = _extract_text_from_document(pdf_path)
    assert "Paso 1" in extracted
    assert "surtidores" in extracted


def test_scanned_pdf_falls_back_to_ocr_with_mocked_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """PDF escaneado (pypdf devuelve vacío) → se usa el OCR provider mockeado."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(b"%PDF-1.4 scanned-image-only")

    class _EmptyPage:
        def extract_text(self):
            return ""

    class _Reader:
        def __init__(self, _path):
            self.pages = [_EmptyPage(), _EmptyPage()]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=_Reader))

    class _FakeOCR:
        def extract_text(self, data, *, content_type=None):
            assert data == b"%PDF-1.4 scanned-image-only"
            assert content_type == "application/pdf"
            return "TEXTO RECUPERADO POR OCR"

    monkeypatch.setattr(ai_factory, "get_ocr_provider", lambda: _FakeOCR())

    extracted = _extract_text_from_document(pdf)
    assert extracted == "TEXTO RECUPERADO POR OCR"


def test_scanned_pdf_without_ocr_degrades_to_pypdf_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Sin OCR disponible: devuelve el texto de pypdf (vacío) y loguea warning, no rompe."""
    pdf = tmp_path / "escaneado.pdf"
    pdf.write_bytes(b"%PDF-1.4 scanned-image-only")

    class _EmptyPage:
        def extract_text(self):
            return ""

    class _Reader:
        def __init__(self, _path):
            self.pages = [_EmptyPage()]

    monkeypatch.setitem(sys.modules, "pypdf", types.SimpleNamespace(PdfReader=_Reader))

    class _UnavailableOCR:
        def extract_text(self, data, *, content_type=None):
            raise TesseractNotAvailableError("Tesseract no instalado")

    monkeypatch.setattr(ai_factory, "get_ocr_provider", lambda: _UnavailableOCR())

    with caplog.at_level(logging.WARNING):
        extracted = _extract_text_from_document(pdf)

    assert extracted == ""  # texto de pypdf (vacío), sin romper el import
    assert any("OCR" in rec.message for rec in caplog.records)
