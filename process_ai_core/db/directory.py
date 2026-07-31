"""Directorio de usuarios (user_id → nombre/email) — persistido, escritura al leer.

Implementa el §3 de `margay-dev-agent/knowledge/11-directorio-de-usuarios.md`,
calcado de `margay-crm/commercial_api/services/usuario_service.py` (el piloto del
estándar) y de `margay-dashboards/api/dashboard_api/services/directory_service.py`.

    resolve_usuarios(ids):
        si (tenant, now - synced_at) superó el TTL:
            GET /api/tenants/{tid}/applications/{key}/directory   ← con el JWT del usuario
            UPSERT en process_ai.users_directory
            los que ya no vienen → status='revoked'               ← NUNCA se borra una fila
        resolver los ids contra la tabla local

**El código que lee es el código que escribe.** No hay job, ni cron, ni webhook,
ni trigger: por eso la tabla no puede quedar vacía en silencio. Si está vacía es
porque nadie está resolviendo nombres. Eso es exactamente lo que falló en
`oms.tenant_users_cache` — se creó, el sync nunca se escribió, quedó en 0 filas,
y de ahí salieron las nueve columnas `*_by_name` de OMS.

**Es `/directory`, no el endpoint de admin.** `/directory` está gateado por
`assert_app_member`: lo llama cualquier miembro del módulo. El de admin exige
`assert_tenant_or_app_admin`, así que usarlo para resolver nombres (anti-patrón
#7) deja a los usuarios comunes sin poder resolver ninguno.

**Degradación elegante (invariante).** Resolver nombres JAMÁS rompe una request.
Si Workspace no responde, o si no hay identidad de request (job, script, test),
se sirve lo que haya en la tabla **aunque esté vencido**, y si tampoco hay nada
se cae a la proyección local `process_ai.users`.

**`display_name` lo calcula Workspace** y viaja en el DTO (§1). Acá no se
concatena nombre y apellido: si cada módulo lo arma, cada uno muestra un formato
distinto. Workspace garantiza que nunca viene vacío (cae al email).

Qué NO es este módulo
---------------------
No reemplaza a `sync_workspace_access` (`api/workspace_client.py`), que sigue
manteniendo `users` y `workspace_memberships` desde `session/context`. Ese es el
mismo patrón §3 resuelto a mano antes de que el estándar existiera, y su alcance
—el usuario actual, con su membresía y sus roles— es información que
`/directory` deliberadamente no expone. Los dos conviven, cada uno con su tabla.

El id con el que se resuelve
---------------------------
Desde la migración `0022_id_canonico`, `process_ai.users.id` **es** el id
canónico de la plataforma (`workspace.users.id`, §4), así que el join contra el
directorio es directo:

    users.id  ==  users_directory.user_id

Antes de esa migración el puente era `users.external_id == users_directory.auth_user_id`,
con `auth_user_id` como columna transitoria. La 0022 la borró: ese era su
criterio de salida, escrito desde el día que se creó (migración 0021).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Lo que devolvemos para un id que no se pudo resolver. Nunca falta la key de un
#: id pedido: el llamador no tiene que distinguir "no está" de "no lo sé".
_VACIO = {"nombre": "", "email": ""}

_DEFAULT_TTL_SECONDS = 300.0

# Los mismos nombres y defaults que usa `api/workspace_client.py` para hablar con
# el control plane. Están duplicados y no importados porque `process_ai_core` no
# depende de `api` en ninguna dirección (`api` importa core, nunca al revés) y
# esa regla vale más que ahorrar dos constantes.
_DEFAULT_WORKSPACE_URL = "http://localhost:8001"
_DEFAULT_APP_KEY = "process_ai"


def _workspace_url() -> str:
    return os.getenv("WORKSPACE_URL", _DEFAULT_WORKSPACE_URL).rstrip("/")


def _app_key() -> str:
    return os.getenv("PROCESS_AI_APP_KEY", _DEFAULT_APP_KEY)


def _ttl_seconds() -> float:
    raw = os.getenv("WORKSPACE_DIRECTORY_CACHE_TTL_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_TTL_SECONDS
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


# ── Identidad del request ───────────────────────────────────────────────────
#
# El refresh necesita el JWT del usuario (el gate de /directory es
# `assert_app_member`, no una service key) y el tenant activo. Como el punto de
# lectura es `resolve_signatories`, que se llama desde el core y desde la
# construcción del PDF, la identidad viaja por contextvar en vez de por
# parámetro: es el equivalente del `get_request_context()` de CRM y dashboards.
#
# La puebla `api/request_identity.py` como dependencia async de router. Sin
# identidad —jobs, scripts, tests— no se refresca y se sirve lo que haya.


@dataclass(frozen=True)
class RequestIdentity:
    token: str
    tenant_id: str


_identity: ContextVar[RequestIdentity | None] = ContextVar(
    "process_ai_request_identity", default=None
)


def set_request_identity(token: str | None, tenant_id: str | None) -> None:
    """Registra el JWT y el tenant activo del request en curso."""
    if token and tenant_id:
        _identity.set(RequestIdentity(token=token, tenant_id=tenant_id))
    else:
        _identity.set(None)


def get_request_identity() -> RequestIdentity | None:
    return _identity.get()


def clear_request_identity() -> None:
    """Solo para tests."""
    _identity.set(None)


# ── Traer el directorio de Workspace ────────────────────────────────────────


def _fetch_directorio(tenant_id: str, token: str) -> list[dict[str, Any]] | None:
    """Directorio del módulo para este tenant.

    `None` = no disponible. En ese caso NO se toca la tabla: hay que servir lo
    que ya está aunque esté vencido.
    """
    url = (
        f"{_workspace_url()}"
        f"/api/tenants/{tenant_id}/applications/{_app_key()}/directory"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        logger.warning("No se pudo leer el directorio de workspace: %s", exc)
        return None
    if not resp.is_success:
        logger.warning(
            "Directorio de workspace respondió %d: %s", resp.status_code, resp.text[:200]
        )
        return None
    datos = resp.json()
    if not isinstance(datos, list):
        logger.warning("Directorio de workspace devolvió algo que no es una lista")
        return None
    return datos


# ── Persistencia: UPSERT + revoked, nunca DELETE ────────────────────────────


def _guardar_directorio(tenant_id: str, entradas: list[dict[str, Any]]) -> None:
    """UPSERT del directorio completo del tenant + revocación de los ausentes.

    Todo en una transacción: o queda el directorio entero consistente o no queda
    nada. Si se aplicara a medias, un usuario podría quedar revocado sin que se
    haya escrito su reemplazo.

    Abre su **propia** sesión a propósito. El refresh lo dispara quien está
    leyendo nombres, y esa lectura puede estar adentro de una transacción de
    negocio (aprobar una versión, congelar un PDF). Si el directorio compartiera
    esa transacción, un rollback de negocio se llevaría puesto el refresh — y al
    revés, un error acá abortaría la operación real. Son independientes.

    Se usa SELECT + UPDATE/INSERT con el ORM y no un `INSERT … ON CONFLICT`
    nativo como CRM: el `ON CONFLICT` es específico del dialecto y la suite corre
    buena parte de los tests contra SQLite en memoria. Con directorios de
    decenas de personas la diferencia no se mide.
    """
    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.models import UserDirectory

    ahora = datetime.utcnow()
    vistos: list[str] = []
    normalizadas: list[dict[str, Any]] = []

    for e in entradas:
        uid = (e.get("user_id") or "").strip()
        if not uid:
            # Sin id canónico no hay PK posible; Workspace siempre lo manda.
            logger.warning("Entrada de directorio sin user_id, se ignora")
            continue
        vistos.append(uid)
        normalizadas.append(
            {
                "user_id": uid,
                # `auth_user_id` NO se guarda: la 0022 borró la columna. El DTO de
                # /directory lo sigue trayendo (otros módulos indexan por ahí),
                # pero acá ya no hace falta — users.id es el id canónico.
                "email": e.get("email"),
                "first_name": e.get("first_name"),
                "last_name": e.get("last_name"),
                # display_name lo calcula Workspace; acá NO se arma (§1).
                "display_name": e.get("display_name"),
            }
        )

    with get_db_session() as session:
        existentes = {
            fila.user_id: fila
            for fila in session.query(UserDirectory)
            .filter(UserDirectory.tenant_id == tenant_id)
            .all()
        }

        for datos in normalizadas:
            fila = existentes.get(datos["user_id"])
            if fila is None:
                session.add(
                    UserDirectory(
                        tenant_id=tenant_id,
                        status="active",
                        synced_at=ahora,
                        **datos,
                    )
                )
                continue
            for campo, valor in datos.items():
                setattr(fila, campo, valor)
            fila.status = "active"
            fila.synced_at = ahora

        # Los que dejaron de venir en la respuesta ya no son miembros del módulo.
        # NO se borran (§3): la fila queda para que el histórico siga resolviendo
        # el nombre por join. `synced_at` también se toca — significa "última vez
        # que verificamos esta fila", no "última vez que estuvo activa".
        for uid, fila in existentes.items():
            if uid not in set(vistos) and fila.status != "revoked":
                fila.status = "revoked"
                fila.synced_at = ahora


# ── Escritura al leer ───────────────────────────────────────────────────────


def _esta_vencido(tenant_id: str) -> bool:
    """¿El directorio de este tenant superó el TTL? Sin filas → vencido."""
    from sqlalchemy import func

    from process_ai_core.db.database import get_db_session
    from process_ai_core.db.models import UserDirectory

    with get_db_session() as session:
        ultimo = (
            session.query(func.max(UserDirectory.synced_at))
            .filter(UserDirectory.tenant_id == tenant_id)
            .scalar()
        )
    if ultimo is None:
        return True
    return (datetime.utcnow() - ultimo).total_seconds() > _ttl_seconds()


def _refrescar_si_hace_falta(tenant_id: str) -> None:
    """El corazón del patrón: leer dispara la escritura.

    Nunca propaga una excepción — resolver nombres no rompe requests.
    """
    identidad = get_request_identity()
    if identidad is None:
        # Job, script de tooling o test: no hay JWT que usar. Se sirve lo que haya.
        return
    if identidad.tenant_id != tenant_id:
        # Se están resolviendo nombres de un tenant que no es el activo del
        # request. El token no autoriza ese directorio, así que no se llama.
        return
    try:
        if not _esta_vencido(tenant_id):
            return
        entradas = _fetch_directorio(tenant_id, identidad.token)
        if entradas is None:
            # Workspace caído: servimos lo vencido. Es el punto del §3.
            return
        _guardar_directorio(tenant_id, entradas)
    except Exception:
        logger.warning("No se pudo refrescar el directorio de usuarios", exc_info=True)


# ── Lectura ─────────────────────────────────────────────────────────────────


def tenant_id_de_workspace(session: Session, workspace_id: str | None) -> str | None:
    """`process_ai.workspaces.tenant_id` — la llave del directorio.

    El módulo indexa casi todo por su `workspace_id` local; el directorio, por el
    `tenant_id` del control plane. Este es el único punto de traducción.
    """
    if not workspace_id:
        return None
    from process_ai_core.db.models import Workspace

    fila = session.query(Workspace.tenant_id).filter_by(id=workspace_id).first()
    return fila[0] if fila and fila[0] else None


def resolve_usuarios(
    session: Session,
    tenant_id: str | None,
    user_ids: Iterable[str | None],
) -> dict[str, dict[str, str]]:
    """Mapa `process_ai.users.id` → `{"nombre", "email"}`.

    Desde la migración `0022_id_canonico` los ids que entran (los que guardan
    `approved_by`, `validator_user_id`, etc.) **son** los canónicos, así que el
    join contra el directorio es `users_directory.user_id = users.id`, directo.

    Sigue entrando por `users` y no directo por `users_directory` porque el
    fallback local importa: si el directorio nunca se pudo poblar, `users.name`
    es lo único que hay, y una firma con el nombre viejo es mejor que una vacía.

    Orden de preferencia para el nombre:

      1. `users_directory.display_name` — calculado por Workspace y refrescado
         por TTL. Es el valor correcto.
      2. `users.name` — la proyección local, congelada en el primer login. Es lo
         que hay si el directorio nunca se pudo poblar (primer arranque con
         Workspace caído, o un job sin JWT).
      3. el email, por cualquiera de las dos vías.

    Un id que no resuelve devuelve info vacía; nunca falta la key de un id
    pedido. Los `revoked` se resuelven igual que los activos: el histórico tiene
    que seguir mostrando el nombre de quien ya no está en el módulo.
    """
    from process_ai_core.db.models import User, UserDirectory

    pedidos = {uid for uid in user_ids if uid}
    if not pedidos:
        return {}

    if tenant_id:
        _refrescar_si_hace_falta(tenant_id)

    filas = (
        session.query(
            User.id,
            User.name,
            User.email,
            UserDirectory.display_name,
            UserDirectory.email,
        )
        .outerjoin(
            UserDirectory,
            (UserDirectory.user_id == User.id)
            & (UserDirectory.tenant_id == (tenant_id or "")),
        )
        .filter(User.id.in_(pedidos))
        .all()
    )

    resuelto: dict[str, dict[str, str]] = {}
    for uid, nombre_local, email_local, display_name, email_dir in filas:
        email = (email_dir or email_local or "").strip()
        nombre = (display_name or nombre_local or email or "").strip()
        resuelto[uid] = {"nombre": nombre, "email": email}

    return {uid: resuelto.get(uid, dict(_VACIO)) for uid in pedidos}


def attach_nombres(
    session: Session,
    tenant_id: str | None,
    rows: list[dict[str, Any]],
    campos: list[tuple[str, str]],
    default: str = "",
) -> list[dict[str, Any]]:
    """Setea in place `campo_nombre` = nombre | email | default para cada par
    `(campo_id, campo_nombre)`. Devuelve la misma lista para encadenar.

    Es el punto de entrada para las rutas: resuelve TODOS los ids de TODAS las
    filas en una sola pasada. Es lo que evita el N+1 (y el `getUser()` por id que
    hacía la UI, que además chocaba contra un endpoint self-only).
    """
    ids = {row.get(campo_id) for row in rows for campo_id, _ in campos}
    directorio = resolve_usuarios(session, tenant_id, ids)
    for row in rows:
        for campo_id, campo_nombre in campos:
            info = directorio.get(str(row.get(campo_id) or ""))
            nombre = (info["nombre"] or info["email"]) if info else ""
            row[campo_nombre] = nombre or default
    return rows
