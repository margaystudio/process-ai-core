"""
Identidad de gobernanza del documento que se está imprimiendo.

Hasta ahora el exportador solo recibía contenido y un logo: no sabía QUÉ estaba
imprimiendo, y por eso el PDF no podía llevar portada, pie con versión ni acta de
aprobación. `DocumentContext` es el dato que cruza esa frontera.

Qué entra acá
-------------
SOLO lo que queda congelado en el acto de aprobación. El PDF de una versión
aprobada es un artefacto inmutable: si embebe un dato que después cambia en el
sistema, el papel y la pantalla se contradicen y el artefacto pierde valor
probatorio.

Por eso NO entran (viven en el sistema, no en el papel):

- la carpeta del documento — se mueve;
- el estado actual del documento — cambia cuando se crea una versión nueva;
- ninguna referencia al run — es un detalle de implementación de la generación,
  y "elaborado por" es una PERSONA (`version.created_by`), no un run.

Nada acá es obligatorio: los call-sites completan lo que pueden resolver y el
resto queda en None. Un campo ausente se omite del PDF, no se inventa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class VersionHistoryEntry:
    """
    Una fila del historial de versiones impreso en el documento.

    SIN estado a propósito. El estado es mutable y el PDF congelado no se puede
    reescribir: si dijera "vigente", mentiría en cuanto se apruebe la versión
    siguiente. Las versiones anteriores figuran por el hecho de haber sido
    aprobadas y superadas, que es permanente.
    """

    version_number: int
    approved_at: datetime | None = None
    approved_by: str | None = None
    #: Qué cambió, según lo escribió el autor al enviar la versión a revisión
    #: (`Validation.submit_comment`). Puede faltar: la fila se imprime igual.
    change_summary: str | None = None


@dataclass(frozen=True)
class DocumentContext:
    """
    Datos inmutables del documento y de la versión que se está imprimiendo.

    `code` sale de `documents.code` (ADR-019, migración 0015) y `validity_until`
    de `document_versions.validity_until` (migración 0016): los dos se fijan una
    vez y no cambian. Pueden llegar en None —un documento previo a la migración,
    o una aprobación sin vencimiento comprometido— y la portada los omite.
    """

    # ── Identidad del documento ──────────────────────────────────────────────
    #: Codificación documental estable (ej. "PR-0042"). No cambia nunca.
    code: str | None = None
    #: Nombre del documento (`Document.name`).
    title: str | None = None
    #: Label del tipo documental del catálogo del tenant (`DocumentType.label`),
    #: no el slug: es lo que el cliente configuró para mostrar.
    document_type_label: str | None = None
    #: Nombre del workspace/organización dueña del documento.
    client_name: str | None = None

    # ── Identidad de la versión ──────────────────────────────────────────────
    version_number: int | None = None
    version_id: str | None = None
    #: True solo si la versión está APPROVED. Un preview de borrador NO debe
    #: poder imprimirse con aspecto de documento aprobado.
    is_approved: bool = False

    # ── Firmas (nombres ya resueltos, no IDs) ────────────────────────────────
    #: Autor de la versión (`DocumentVersion.created_by`).
    elaborated_by: str | None = None
    #: Quien validó (`Validation.validator_user_id` de la validación asociada).
    reviewed_by: str | None = None
    #: Quien aprobó (`DocumentVersion.approved_by`).
    approved_by: str | None = None
    approved_at: datetime | None = None

    # ── Trazabilidad de reemplazo ────────────────────────────────────────────
    #: Versión a la que reemplaza esta (`supersedes_version_id` → su número).
    supersedes_version_number: int | None = None
    supersedes_approved_at: datetime | None = None

    #: Hasta cuándo se comprometió la vigencia, fijada al aprobar.
    validity_until: date | None = None

    #: Rol operativo de cada firmante en el momento de aprobar. Para gobernanza
    #: importa la autoridad bajo la que se aprobó, no solo la identidad: "aprobado
    #: por Juan Pérez" es más débil que "Juan Pérez, Gerente de Planta". Si el
    #: workspace no configuró roles operativos quedan en None y se omiten.
    elaborated_by_role: str | None = None
    reviewed_by_role: str | None = None
    approved_by_role: str | None = None

    #: Historial de versiones aprobadas, de la más nueva a la más vieja,
    #: reconstruido desde la cadena `supersedes_version_id`.
    version_history: tuple[VersionHistoryEntry, ...] = ()

    #: Índice de contenidos (lo decide el perfil de render; ver profiles.py).
    show_toc: bool = False

    #: URL de verificación en línea de ESTA versión (lleva el version_id). Va en
    #: el QR de la portada. Es inmutable como el version_id del que deriva: una
    #: copia impresa no puede afirmar que sigue vigente, así que remite a la
    #: consulta en línea en vez de mentir.
    verification_url: str | None = None
