"""
Construcción de claves canónicas de almacenamiento.

Esquema — TODO bajo `workspaces/{workspace_id}/...` (organizado por tenant):

    workspaces/{ws}/runs/{run_id}/process.json|md|pdf
    workspaces/{ws}/runs/{run_id}/assets/...
    workspaces/{ws}/documents/{document_id}/versions/{version_id}/document.pdf
    workspaces/{ws}/documents/{document_id}/versions/{version_id}/assets/{asset_id}.{ext}

Las claves incluyen `workspace_id` para aislamiento multi-tenant verificable y para
contabilidad/borrado por tenant triviales (sumar/borrar por prefijo).
"""

from __future__ import annotations

import re
import unicodedata

#: Largo máximo del nombre dentro de la clave. No es un límite del backend: es
#: para que una clave siga siendo legible en un log o en el panel de storage.
_MAX_NOMBRE = 80

_PERMITIDOS = re.compile(r"[^A-Za-z0-9._-]+")


def nombre_seguro_para_clave(filename: str, *, fallback: str = "archivo") -> str:
    """
    Nombre de archivo apto para una clave de object storage.

    POR QUÉ HACE FALTA
    ------------------
    Supabase Storage **rechaza las claves con caracteres no ASCII**: subir el
    original de un documento llamado `Procedimiento Gestión de Deuda.docx`
    falla con `InvalidKey`, mientras que el mismo archivo sin tildes entra sin
    problema. Es un error del backend de storage, no de validación nuestra, así
    que aparece recién al subir y con un mensaje que no dice "sacale la tilde".

    Se transliteran los acentos (á→a) en vez de descartarlos, para que el
    nombre siga siendo reconocible en la clave. Es solo la CLAVE: el nombre
    original se guarda aparte (`source_file_name`) y es el que se usa al
    descargar, así que el usuario sigue recibiendo su archivo con el nombre que
    le puso.
    """
    base = (filename or "").replace("\\", "/").split("/")[-1]
    stem, punto, ext = base.rpartition(".")
    if not punto:  # sin extensión
        stem, ext = base, ""

    stem_sano = _solo_ascii_seguro(stem)[:_MAX_NOMBRE].strip("-.")
    ext_sano = _solo_ascii_seguro(ext).strip("-.")

    # Un nombre entero en otro alfabeto (陰陽.docx) se queda sin stem: se usa el
    # fallback, pero conservando la extensión, que es la parte que importa para
    # abrir el archivo después.
    if not stem_sano:
        stem_sano = fallback.rpartition(".")[0] or fallback
        if not ext_sano:
            ext_sano = fallback.rpartition(".")[2] if "." in fallback else ""

    return f"{stem_sano}.{ext_sano}" if ext_sano else stem_sano


def _solo_ascii_seguro(texto: str) -> str:
    """NFKD separa la letra de su tilde; nos quedamos con la letra."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return _PERMITIDOS.sub("-", plano).strip("-.")


def workspace_prefix(workspace_id: str) -> str:
    return f"workspaces/{workspace_id}"


def workspace_branding_key(workspace_id: str, filename: str) -> str:
    """
    Clave del icono de marca del workspace.

    Vive en object storage y no en disco local porque lo lee el freeze del PDF:
    en Cloud Run el filesystem es efímero y hay varias instancias, así que el
    archivo subido por una instancia no existe en la que congela el documento.
    """
    safe = nombre_seguro_para_clave(filename, fallback="icon.png")
    return f"{workspace_prefix(workspace_id)}/branding/{safe}"


def run_prefix(workspace_id: str, run_id: str) -> str:
    return f"workspaces/{workspace_id}/runs/{run_id}"


def run_artifact_key(workspace_id: str, run_id: str, rel: str) -> str:
    """Clave de un artefacto de run (rel = ruta relativa dentro del run, estilo POSIX)."""
    rel = rel.lstrip("/")
    return f"{run_prefix(workspace_id, run_id)}/{rel}"


def version_prefix(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}"


def version_pdf_key(workspace_id: str, document_id: str, version_id: str) -> str:
    return f"{version_prefix(workspace_id, document_id, version_id)}/document.pdf"


def version_asset_key(
    workspace_id: str, document_id: str, version_id: str, asset_id: str, ext: str
) -> str:
    ext = ext.lstrip(".")
    return f"{version_prefix(workspace_id, document_id, version_id)}/assets/{asset_id}.{ext}"


def version_source_file_key(
    workspace_id: str, document_id: str, version_id: str, filename: str
) -> str:
    """Clave del archivo original importado (conserva la extensión del nombre).

    El nombre va saneado —sin tildes ni caracteres raros— porque Supabase
    Storage rechaza claves no ASCII. El nombre ORIGINAL se conserva en
    `document_versions.source_file_name`, que es el que se usa al descargar.
    """
    safe = nombre_seguro_para_clave(filename, fallback="source.bin")
    return f"{version_prefix(workspace_id, document_id, version_id)}/source/{safe}"
