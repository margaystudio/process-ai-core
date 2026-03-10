from pathlib import Path
import sys
import types

import pytest

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
