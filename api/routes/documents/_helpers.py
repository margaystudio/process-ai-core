"""
Helpers compartidos entre los sub-routers de documentos.

Se extrajeron del módulo monolítico original (documents.py) para que crud,
runs, content y versions puedan reutilizarlos sin duplicar lógica.
"""

import re
from typing import Optional

from fastapi import HTTPException

from api.artifact_signing import sign_artifact_url


def _assert_doc_in_active_workspace(doc_workspace_id: str, active_workspace_id: str, document_id: str) -> None:
    """Lanza 404 si el documento no pertenece al workspace activo del contexto."""
    if doc_workspace_id != active_workspace_id:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")


_LATEX_ARTIFACT_RE = re.compile(
    r"\\(?:FloatBarrier|clearpage|newpage|pagebreak|vspace\{[^}]*\}|hspace\{[^}]*\}|noindent|medskip|bigskip|smallskip)",
    re.IGNORECASE,
)


def _strip_latex_artifacts(text: str) -> str:
    """Elimina comandos LaTeX que no tienen equivalente HTML y quedarían como texto basura."""
    return _LATEX_ARTIFACT_RE.sub("", text)


def _markdown_to_html(md: str) -> str:
    """Convierte Markdown a HTML para precarga del editor manual."""
    # Limpiar artefactos LaTeX antes de convertir (no tienen sentido en HTML)
    md = _strip_latex_artifacts(md or "")
    try:
        import markdown
        return markdown.markdown(md, extensions=["extra", "nl2br", "tables", "sane_lists"])
    except Exception:
        import html as html_mod
        return "".join(f"<p>{html_mod.escape(line)}</p>" for line in md.splitlines())


def _rewrite_img_src_to_absolute(
    html_content: str,
    run_id: Optional[str],
    api_base: str,
    workspace_id: Optional[str] = None,
) -> str:
    """
    Reescribe rutas de imágenes relativas en HTML a URLs absolutas con token firmado.
    - src="assets/..." → {api_base}/api/v1/artifacts/{run_id}/assets/...?token=...
    - src="/api/v1/..." o src="http..." → sin cambios

    Args:
        workspace_id: Cuando se provee, genera URLs firmadas (HMAC). Si es None,
                      genera URLs sin token (solo para compatibilidad legacy).
    """
    if not html_content:
        return html_content

    def replace_src(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("http") or src.startswith("/api/v1/"):
            return m.group(0)
        if run_id and (src.startswith("assets/") or src.startswith("./assets/")):
            clean = src.lstrip("./")
            if workspace_id:
                signed = sign_artifact_url(run_id, clean, workspace_id)
                return f'src="{api_base}{signed}"'
            return f'src="{api_base}/api/v1/artifacts/{run_id}/{clean}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', replace_src, html_content)


_HTML_BLOCK_RE = re.compile(
    r"<(?:h[1-6]|p|ul|ol|li|strong|em|b|i|table|img|div|span|a|br|hr|blockquote|pre|code)\b",
    re.IGNORECASE,
)


def _is_valid_html(text: str) -> bool:
    """
    Devuelve True si el texto contiene etiquetas HTML de bloque o inline.
    HTML generado por python-markdown o Tiptap siempre las tiene.
    Markdown crudo nunca las tiene.
    """
    return bool(_HTML_BLOCK_RE.search(text or ""))


def _looks_like_markdown(text: str) -> bool:
    """
    Devuelve True si el texto NO contiene etiquetas HTML válidas
    (es decir, probablemente es markdown crudo o texto plano).
    Se mantiene por compatibilidad; internamente usa _is_valid_html.
    """
    return not _is_valid_html(text)
