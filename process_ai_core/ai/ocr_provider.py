"""OCR local vía Tesseract (Fase 1.2 — estrategia barata).

Estrategia:
- Imágenes: PIL + pytesseract.
- PDF escaneado (sin capa de texto): renderizar páginas con PyMuPDF → Tesseract por página.

Requiere el binario de Tesseract instalado en el sistema. En Windows, configurar
TESSERACT_CMD apuntando al ejecutable (p. ej. C:\\Program Files\\Tesseract-OCR\\tesseract.exe).
"""

from __future__ import annotations

import io

from ..config import get_settings


class TesseractNotAvailableError(RuntimeError):
    """El binario de Tesseract no está instalado o no es accesible."""


class TesseractOCRProvider:
    """Implementación local de `OCRProvider` usando pytesseract + PyMuPDF."""

    def __init__(self, *, tesseract_cmd: str | None = None, languages: str | None = None) -> None:
        settings = get_settings()
        self._tesseract_cmd = tesseract_cmd or settings.tesseract_cmd or None
        self._languages = languages or settings.ocr_languages

    def _configure_tesseract(self) -> None:
        import pytesseract

        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd

    def _ensure_tesseract(self) -> None:
        """Verifica que el binario de Tesseract esté disponible."""
        import pytesseract

        self._configure_tesseract()
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError as exc:
            raise TesseractNotAvailableError(
                "Tesseract OCR no está instalado o no está en PATH. "
                "Instalá Tesseract (Windows: UB-Mannheim installer; Linux: apt install tesseract-ocr tesseract-ocr-spa) "
                "y configurá TESSERACT_CMD en .env si hace falta."
            ) from exc

    def extract_text(self, data: bytes, *, content_type: str | None = None) -> str:
        """Extrae texto de bytes de imagen o PDF escaneado."""
        self._ensure_tesseract()

        ct = (content_type or "").lower()
        if ct == "application/pdf" or _looks_like_pdf(data):
            return self._ocr_pdf_bytes(data)
        return self._ocr_image_bytes(data)

    def _ocr_image_bytes(self, data: bytes) -> str:
        import pytesseract
        from PIL import Image

        self._configure_tesseract()
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang=self._languages)
        return (text or "").strip()

    def _ocr_pdf_bytes(self, data: bytes) -> str:
        import fitz
        import pytesseract
        from PIL import Image

        self._configure_tesseract()
        doc = fitz.open(stream=data, filetype="pdf")
        parts: list[str] = []
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                page_text = pytesseract.image_to_string(img, lang=self._languages)
                if page_text and page_text.strip():
                    parts.append(page_text.strip())
        finally:
            doc.close()
        return "\n\n".join(parts).strip()


def _looks_like_pdf(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == b"%PDF"
