"""Tests para importación de documentos (sin BD)."""

from __future__ import annotations

from process_ai_core.document_import import (
    ALLOWED_IMPORT_EXTENSIONS,
    _build_imported_content,
    _extract_text_from_bytes,
)


def test_allowed_extensions():
    assert ".txt" in ALLOWED_IMPORT_EXTENSIONS
    assert ".md" in ALLOWED_IMPORT_EXTENSIONS
    assert ".pdf" in ALLOWED_IMPORT_EXTENSIONS
    assert ".docx" in ALLOWED_IMPORT_EXTENSIONS


def test_build_imported_content():
    content_json, content_markdown = _build_imported_content(
        "manual.md",
        "Texto del manual",
        "workspaces/w1/documents/d1/versions/v1/source/manual.md",
    )
    assert "Texto del manual" in content_json
    assert "# manual" in content_markdown or "# Manual" in content_markdown.lower()
    assert "imported" in content_json


def test_extract_text_from_md_bytes():
    text = _extract_text_from_bytes("nota.md", b"# Titulo\n\nCuerpo")
    assert "Cuerpo" in text
