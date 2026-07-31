"""
Congelado del PDF de una versión APROBADA como artefacto de auditoría (Fase B).

Al aprobar una versión:
  1. Se renderiza el PDF desde su contenido (fuente de verdad: content_html, si no, markdown).
  2. Se sube a object storage bajo la clave canónica de la versión.
  3. Se calcula SHA-256 y se persiste key + hash + timestamp + motor de render.

Best-effort: si el render o la subida fallan, NO se rompe la aprobación; se loggea
un warning y la versión queda aprobada sin PDF congelado (se puede reintentar luego).
"""

from __future__ import annotations

import hashlib
import logging
import re
import tempfile
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy.orm import Session

from process_ai_core.config import get_settings
from process_ai_core.db.models import Document, DocumentVersion
from process_ai_core.export import (
    ASSET_BASE_URL,
    StorageAssetFetcher,
    export_pdf_from_content,
    get_export_content,
    verify_pdf_images,
)
from process_ai_core.storage import get_storage, version_pdf_key
from ._branding import get_workspace_pdf_branding
from ._document_context import build_document_context

logger = logging.getLogger(__name__)


def _rewrite_img_src_to_assets(html: str) -> str:
    """
    Apunta las imágenes del documento al host centinela de assets.

    Antes esto generaba URLs FIRMADAS de la propia API, y WeasyPrint las bajaba
    por HTTP durante el render. Tres problemas, todos silenciosos: la API se
    llamaba a sí misma mientras atendía la aprobación que disparó el freeze; el
    render dependía de la red y de que la firma no hubiera vencido; y si la
    descarga fallaba WeasyPrint omitía la imagen sin lanzar, congelando el
    artefacto sin las evidencias.

    Ahora las URLs quedan bajo `ASSET_BASE_URL`, que no existe en la red: las
    resuelve `StorageAssetFetcher` leyendo directo de object storage.

    Se reescriben también las rutas absolutas `/api/v1/...` (imágenes del editor
    manual): el fetcher las mapea a su clave de storage.
    """
    if not html:
        return html

    def repl(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("data:") or src.startswith(ASSET_BASE_URL):
            return m.group(0)
        if src.startswith("assets/") or src.startswith("./assets/"):
            return f'src="{ASSET_BASE_URL}{src.lstrip("./")}"'
        if src.startswith("/api/v1/"):
            return f'src="{ASSET_BASE_URL}{src.lstrip("/")}"'
        if _API_IMAGE_RE.search(src):
            # URL absoluta a nuestra propia API: se normaliza al host centinela
            # para que tampoco salga por HTTP.
            return f'src="{ASSET_BASE_URL}{_API_IMAGE_RE.sub("", src).lstrip("/")}"'
        return m.group(0)

    return re.sub(r'src="([^"]+)"', repl, html)


# Prefijo de una URL absoluta a nuestra propia API (cualquier host).
_API_IMAGE_RE = re.compile(r"^https?://[^/]+(?=/api/v1/)")


def _render_engine_label() -> str:
    """
    Motor + versión con los que se produjo el artefacto.

    Ya no depende del formato: WeasyPrint es el único motor de salida. La versión
    es parte del contrato del artefacto (ver el pin en pyproject.toml), así que
    queda registrada en la fila junto al hash.
    """
    try:
        import weasyprint  # type: ignore

        return f"weasyprint-{getattr(weasyprint, '__version__', '?')}"
    except Exception:
        return "weasyprint"


def freeze_approved_pdf(session: Session, version: DocumentVersion, api_base: str | None = None) -> bool:
    """
    Renderiza, sube y registra el PDF de una versión APROBADA. Devuelve True si tuvo éxito.

    Idempotente: si la versión ya tiene `pdf_storage_key`, no re-renderiza.
    """
    if version.version_status != "APPROVED":
        return False
    if version.pdf_storage_key:
        return True  # ya congelado

    try:
        document = session.query(Document).filter_by(id=version.document_id).first()
        if not document:
            logger.warning("freeze_approved_pdf: documento %s no encontrado", version.document_id)
            return False
        workspace_id = document.workspace_id

        # Siempre HTML: get_export_content normaliza (ver content_source.py).
        content = get_export_content(version)

        # Si la versión llegó sin content_html, el HTML se acaba de derivar del
        # markdown y sería una entrada del artefacto que NO quedó congelada: el
        # PDF dependería de la versión de la librería `markdown` del día. Se
        # persiste ahora, en la misma transacción que la clave y el hash, para
        # que el registro del artefacto quede completo de una sola vez.
        #
        # Se guarda ANTES de reescribir los src a propósito: en la fila va la
        # forma portable, con rutas relativas, no las del host centinela.
        if not (version.content_html or "").strip():
            version.content_html = content
            logger.info(
                "Versión %s no tenía content_html; se congela junto con el PDF", version.id
            )

        settings = get_settings()
        api_base = (api_base or settings.api_base_url).rstrip("/")
        branding = get_workspace_pdf_branding(session, workspace_id)
        # El artefacto de auditoría es el único render donde el contexto es
        # definitivo: acá la versión ya está APPROVED y las firmas no cambian más.
        document_context = build_document_context(session, document, version)

        content = _rewrite_img_src_to_assets(content)

        # Las imágenes se leen de object storage, no por HTTP: ver asset_fetcher.py.
        fetcher = StorageAssetFetcher(
            workspace_id=workspace_id,
            run_id=version.run_id,
            document_id=version.document_id,
        )

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = export_pdf_from_content(
                content=content,
                format="html",
                run_dir=Path(tmp),
                pdf_name="document.pdf",
                base_url=ASSET_BASE_URL,
                branding=branding,
                document_context=document_context,
                url_fetcher=fetcher,
            )
            pdf_bytes = Path(pdf_path).read_bytes()

        # Si falta una evidencia, se ABORTA. Lanza IncompletePdfError, que cae en
        # el except de abajo: el freeze devuelve False, la aprobación sigue
        # válida y el reintento del endpoint del PDF congelado lo vuelve a
        # intentar. Un artefacto incompleto con hash registrado no se detecta más.
        verify_pdf_images(pdf_bytes, fetcher, contexto=f"versión {version.id}")

        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        key = version_pdf_key(workspace_id, version.document_id, version.id)
        get_storage().put(key, pdf_bytes, content_type="application/pdf")

        version.pdf_storage_key = key
        version.pdf_sha256 = sha256
        version.pdf_generated_at = datetime.now(UTC)
        version.pdf_render_engine = _render_engine_label()

        # Recalcular el uso de storage del tenant (best-effort).
        from process_ai_core.db.helpers import update_workspace_storage_usage
        update_workspace_storage_usage(session, workspace_id)

        logger.info(
            "PDF aprobado congelado: version=%s key=%s sha256=%s",
            version.id, key, sha256[:12],
        )
        return True
    except Exception as exc:
        logger.warning(
            "freeze_approved_pdf falló para versión %s (la aprobación sigue válida): %s",
            getattr(version, "id", "?"), exc,
        )
        return False


# ── Barrido de pendientes ────────────────────────────────────────────────────
#
# El freeze puede quedar pendiente por dos caminos legítimos: una aprobación con
# `defer_freeze=True` (lote), o un freeze que falló al aprobar. El GET del PDF
# congela bajo demanda, pero eso deja un agujero: si nadie abre nunca el PDF de
# un documento aprobado, el artefacto de auditoría NO EXISTE. Para un sistema de
# gobernanza eso no es aceptable — el artefacto tiene que existir aunque nadie lo
# mire, porque su razón de ser es estar disponible el día que alguien pregunte.


def count_versions_pending_freeze(session: Session, workspace_id: str | None = None) -> int:
    """
    Cuántas versiones APPROVED no tienen todavía su PDF congelado.

    Es la métrica que avisa si el freeze está fallando sistemáticamente. Un valor
    que sube y no baja después de correr el barrido no es backlog: es que el
    render viene fallando. Ojo con leerla como ruido — desde que la verificación
    de integridad ABORTA el freeze cuando falta una evidencia, un pico acá puede
    ser justamente que se está evitando publicar un PDF con imágenes faltantes.
    """
    query = session.query(DocumentVersion).filter(
        DocumentVersion.version_status == "APPROVED",
        DocumentVersion.pdf_storage_key.is_(None),
    )
    if workspace_id is not None:
        query = query.join(Document, Document.id == DocumentVersion.document_id).filter(
            Document.workspace_id == workspace_id
        )
    return query.count()


def freeze_pending_versions(
    session: Session,
    *,
    limit: int = 50,
    workspace_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Congela hasta `limit` versiones APPROVED que no tengan PDF.

    Idempotente y seguro de correr en paralelo con el freeze bajo demanda:

    - `SKIP LOCKED` esquiva las filas que otro proceso ya tiene tomadas por el
      `with_for_update()` del GET del PDF, en vez de bloquearse detrás de ellas.
      Dos barridos simultáneos se reparten el trabajo en vez de pelearlo.
    - Se re-chequea `pdf_storage_key` DESPUÉS de tomar el lock: si el ganador de
      la carrera ya congeló, esta pasada no re-renderiza.
    - `freeze_approved_pdf` ya es idempotente por su cuenta.

    Cada versión va en su propia transacción: un documento con una evidencia
    faltante aborta SU freeze y el barrido sigue con el resto, en vez de tirar
    abajo el lote entero.
    """
    candidatas = (
        session.query(DocumentVersion.id)
        .filter(
            DocumentVersion.version_status == "APPROVED",
            DocumentVersion.pdf_storage_key.is_(None),
        )
    )
    if workspace_id is not None:
        candidatas = candidatas.join(
            Document, Document.id == DocumentVersion.document_id
        ).filter(Document.workspace_id == workspace_id)

    ids = [fila[0] for fila in candidatas.order_by(DocumentVersion.created_at).limit(limit).all()]

    resultado = {"candidatas": len(ids), "congeladas": 0, "salteadas": 0, "fallidas": 0}
    if dry_run:
        resultado["ids"] = ids
        return resultado

    for version_id in ids:
        try:
            version = (
                session.query(DocumentVersion)
                .filter_by(id=version_id)
                .populate_existing()
                .with_for_update(skip_locked=True)
                .one_or_none()
            )
            if version is None:
                # La tiene tomada el freeze bajo demanda: es suya, no nuestra.
                resultado["salteadas"] += 1
                session.rollback()
                continue
            if version.pdf_storage_key:
                resultado["salteadas"] += 1
                session.rollback()
                continue

            if freeze_approved_pdf(session, version):
                session.commit()
                resultado["congeladas"] += 1
            else:
                session.rollback()
                resultado["fallidas"] += 1
                logger.warning("Barrido: no se pudo congelar la versión %s", version_id)
        except Exception as exc:
            session.rollback()
            resultado["fallidas"] += 1
            logger.warning("Barrido: error congelando la versión %s: %s", version_id, exc)

    return resultado
