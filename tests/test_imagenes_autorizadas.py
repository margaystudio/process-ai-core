"""
Las imágenes de un documento se sirven con request autenticado y permiso de carpeta.

El agujero que esto cierra
--------------------------
Las imágenes embebidas se servían con un token firmado en la URL. Un token en la
dirección es un PORTADOR: el servidor valida la firma pero no sabe QUIÉN la
presenta, así que el permiso por carpeta —una capacidad que el producto vende
explícitamente— no se aplicaba. Cualquier miembro del workspace con el enlace
veía material de una carpeta que tenía denegada.

Lo que se verifica acá es el ARREGLO, no la plomería: que el permiso de carpeta
se evalúe en cada pedido. El proxy del front (ui/app/api/doc-assets/) es solo lo
que hace que el servidor sepa quién pide; un proxy que reenviara sin este chequeo
del otro lado dejaría el agujero abierto.
"""

from __future__ import annotations

import io
import re
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from types import SimpleNamespace

from api.routes import artifacts as artifacts_mod
from api.routes.documents import content as content_mod
from api.routes.documents import versions as versions_mod
from api.routes.documents._helpers import (
    PROXY_PREFIX,
    rewrite_img_src_to_proxy,
    strip_image_url_tokens,
)
from process_ai_core.db.database import Base
from process_ai_core.db.models import (
    Document,
    DocumentVersion,
    Folder,
    FolderPermission,
    OperationalRole,
    Process,
    Run,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.storage.local import LocalDiskStorage


def _uid() -> str:
    return str(uuid.uuid4())


def _png() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (10, 120, 90)).save(buffer, "PNG")
    return buffer.getvalue()


def _request(headers: dict | None = None):
    """Sustituto de fastapi.Request: los handlers solo leen `request.headers`."""
    return SimpleNamespace(headers=headers or {})


class Escenario:
    """
    Workspace con una carpeta RESTRINGIDA a un rol operativo, un documento
    adentro con una imagen de versión, una imagen del editor y un artefacto de run.
    """

    def __init__(self, session, storage):
        self.session = session
        self.storage = storage
        self.workspace = Workspace(
            id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization"
        )
        session.add(self.workspace)

        # Carpeta con permisos EXPLÍCITOS: solo quien tenga el rol operativo entra.
        self.carpeta = Folder(
            id=_uid(),
            workspace_id=self.workspace.id,
            name="Confidencial",
            path="Confidencial",
            parent_id=None,
            inherits_permissions=False,
        )
        session.add(self.carpeta)
        self.rol_operativo = OperationalRole(
            id=_uid(), workspace_id=self.workspace.id, name="Contable", slug="contable"
        )
        session.add(self.rol_operativo)
        session.flush()
        session.add(
            FolderPermission(
                id=_uid(),
                folder_id=self.carpeta.id,
                operational_role_id=self.rol_operativo.id,
            )
        )

        self.documento = Process(
            id=_uid(),
            workspace_id=self.workspace.id,
            folder_id=self.carpeta.id,
            document_type="process",
            name="Procedimiento confidencial",
            status="approved",
        )
        session.add(self.documento)
        session.flush()

        self.version = DocumentVersion(
            id=_uid(),
            document_id=self.documento.id,
            version_number=1,
            version_status="APPROVED",
            content_type="imported",
            content_json="{}",
            content_markdown="# Doc",
        )
        session.add(self.version)
        self.run = Run(id=_uid(), document_id=self.documento.id, domain="process")
        session.add(self.run)
        session.commit()

        ws = self.workspace.id
        storage.put(
            f"workspaces/{ws}/documents/{self.documento.id}/versions/{self.version.id}"
            f"/assets/img01.png",
            _png(),
            "image/png",
        )
        storage.put(
            f"workspaces/{ws}/editor-uploads/{self.documento.id}/subida.png", _png(), "image/png"
        )
        storage.put(
            f"workspaces/{ws}/runs/{self.run.id}/assets/paso1.png", _png(), "image/png"
        )

    def usuario(self, *, con_rol_operativo: bool) -> str:
        """Miembro del workspace (base 'member'); el rol operativo decide la carpeta."""
        u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
        self.session.add(u)
        self.session.flush()
        m = WorkspaceMembership(
            id=_uid(),
            user_id=u.id,
            workspace_id=self.workspace.id,
            base_access="member",
        )
        self.session.add(m)
        self.session.flush()
        if con_rol_operativo:
            self.session.add(
                UserOperationalRole(
                    id=_uid(),
                    workspace_membership_id=m.id,
                    operational_role_id=self.rol_operativo.id,
                )
            )
        self.session.commit()
        return u.id


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


@pytest.fixture
def escenario(session, tmp_path, monkeypatch):
    from contextlib import contextmanager

    import process_ai_core.storage as storage_mod

    store = LocalDiskStorage(root=str(tmp_path / "store"))
    env = Escenario(session, store)

    @contextmanager
    def fake_db_session():
        yield session

    for modulo in (versions_mod, content_mod, artifacts_mod):
        monkeypatch.setattr(modulo, "get_db_session", fake_db_session)
        monkeypatch.setattr(
            modulo, "resolve_tenant_workspace_id", lambda _ctx: env.workspace.id
        )
    monkeypatch.setattr(versions_mod, "get_storage", lambda: store)
    monkeypatch.setattr(artifacts_mod, "get_storage", lambda: store)
    monkeypatch.setattr(storage_mod, "get_storage", lambda: store)
    return env


def _pedir_las_tres_imagenes(env, user_id):
    """Las tres familias, con la URL exacta en la mano."""
    return [
        lambda: versions_mod.get_version_asset(
            env.documento.id, env.version.id, "img01.png",
            request=_request(), user_id=user_id, ctx=None,
        ),
        lambda: content_mod.get_editor_image(
            env.documento.id, "subida.png",
            request=_request(), user_id=user_id, ctx=None,
        ),
        lambda: artifacts_mod.get_artifact(
            env.run.id, "assets/paso1.png",
            request=_request(), user_id=user_id, ctx=None,
        ),
    ]


# ── El permiso de carpeta se aplica ──────────────────────────────────────────


def test_sin_permiso_de_carpeta_no_se_sirve_la_imagen_ni_con_la_url_exacta(escenario):
    """
    Es el agujero que motivó todo: un miembro del workspace, con `documents.view`,
    pero SIN el rol operativo que la carpeta exige. Antes veía la imagen con solo
    tener el enlace.
    """
    sin_permiso = escenario.usuario(con_rol_operativo=False)

    for pedir in _pedir_las_tres_imagenes(escenario, sin_permiso):
        with pytest.raises(HTTPException) as exc:
            pedir()
        assert exc.value.status_code == 403
        assert "carpeta" in exc.value.detail.lower()


def test_con_permiso_de_carpeta_la_imagen_se_sirve(escenario):
    con_permiso = escenario.usuario(con_rol_operativo=True)

    for pedir in _pedir_las_tres_imagenes(escenario, con_permiso):
        response = pedir()
        assert response.status_code == 200
        assert response.body[:4] == b"\x89PNG"


def test_un_documento_de_otro_workspace_no_existe(escenario, session):
    """Aislamiento de tenant: 404, no 403 — para el otro tenant no existe."""
    otro = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="Otro", workspace_type="organization")
    session.add(otro)
    session.commit()
    escenario.documento.workspace_id = otro.id
    session.commit()

    with pytest.raises(HTTPException) as exc:
        versions_mod.get_version_asset(
            escenario.documento.id, escenario.version.id, "img01.png",
            request=_request(), user_id=escenario.usuario(con_rol_operativo=True), ctx=None,
        )
    assert exc.value.status_code == 404


def test_el_artefacto_de_run_hereda_el_permiso_del_documento(escenario):
    """El run no tiene permisos propios: se ve si se ve el documento que produjo."""
    sin_permiso = escenario.usuario(con_rol_operativo=False)

    with pytest.raises(HTTPException) as exc:
        artifacts_mod.get_artifact(
            escenario.run.id, "process.pdf",
            request=_request(), user_id=sin_permiso, ctx=None,
        )
    assert exc.value.status_code == 403


# ── Ningún camino sin autenticación ──────────────────────────────────────────


#: Formas de ruta que sirven bytes de un archivo. Si aparece una nueva con esta
#: forma, el test de abajo la encuentra sola y exige que también pida sesión.
_SUFIJOS_DE_ARCHIVO = ("/assets/{filename}", "/editor-images/{filename}")

#: El endpoint de artefactos de run no termina en un sufijo fijo (su último
#: segmento es una ruta libre), así que se reconoce por prefijo.
_PREFIJO_ARTEFACTOS = "/api/v1/artifacts/"


def _rutas_que_sirven_archivos(app) -> list[str]:
    """
    Rutas de archivo declaradas por la app, según su esquema OpenAPI.

    Se enumera por OpenAPI y no recorriendo `app.routes` a propósito. La primera
    versión de este test leía `route.path` de cada entrada de `app.routes`, y en
    Starlette 1.x `include_router` dejó de aplanar las sub-rutas: mete un
    `_IncludedRouter` opaco, sin `.path` ni `.routes`. El test no encontraba
    NINGUNA ruta y pasaba a ser un test que no probaba nada — salvo que la
    aserción final de "revisadas == 3" lo hizo fallar ruidosamente, que es
    justamente para lo que estaba.

    El esquema OpenAPI es contrato público y no cambió entre versiones.
    """
    return sorted(
        ruta
        for ruta in app.openapi()["paths"]
        if ruta.startswith(_PREFIJO_ARTEFACTOS)
        or any(ruta.endswith(sufijo) for sufijo in _SUFIJOS_DE_ARCHIVO)
    )


def test_ninguna_ruta_que_sirva_archivos_responde_sin_autenticacion():
    """
    El requisito no es "estos tres endpoints tienen un Depends" sino "no queda
    NINGÚN camino que devuelva un archivo sin autenticar". Por eso se verifica el
    COMPORTAMIENTO —un GET real sin Authorization— y no la presencia de un objeto
    en la lista de dependencias: un Depends puede estar y no aplicar, y un
    endpoint nuevo con esta forma de ruta queda cubierto sin tocar el test.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    rutas = _rutas_que_sirven_archivos(app)
    assert rutas == [
        "/api/v1/artifacts/{run_id}/{filename}",
        "/api/v1/documents/{document_id}/editor-images/{filename}",
        "/api/v1/documents/{document_id}/versions/{version_id}/assets/{filename}",
    ], "cambió el set de rutas que sirven archivos"

    cliente = TestClient(app)
    for ruta in rutas:
        url = re.sub(r"\{[^}]+\}", "x", ruta)
        respuesta = cliente.get(url)
        assert respuesta.status_code == 401, f"{url} respondió {respuesta.status_code}"


def test_los_endpoints_ya_no_aceptan_token_en_la_url():
    """La firma se eliminó: si volviera, este import volvería a andar."""
    with pytest.raises(ModuleNotFoundError):
        import api.artifact_signing  # noqa: F401


# ── Cache: revalidar en vez de congelar el permiso ───────────────────────────


def test_el_navegador_revalida_en_vez_de_servir_de_su_cache(escenario):
    """
    `private, no-cache` con ETag, igual que el PDF congelado. Ahora que cada
    pedido verifica el permiso, cachear sin revalidar le devolvería la imagen a
    quien ya no tiene acceso — el mismo agujero, del lado del cliente.
    """
    user_id = escenario.usuario(con_rol_operativo=True)

    respuesta = versions_mod.get_version_asset(
        escenario.documento.id, escenario.version.id, "img01.png",
        request=_request(), user_id=user_id, ctx=None,
    )
    assert respuesta.headers["cache-control"] == "private, no-cache"
    etag = respuesta.headers["etag"]
    assert etag

    # Con el ETag en mano: 304 sin cuerpo. La revalidación sigue siendo barata.
    revalidada = versions_mod.get_version_asset(
        escenario.documento.id, escenario.version.id, "img01.png",
        request=_request({"if-none-match": etag}), user_id=user_id, ctx=None,
    )
    assert revalidada.status_code == 304
    assert revalidada.body == b""


def test_el_304_tambien_pasa_por_el_chequeo_de_permiso(escenario):
    """El atajo del 304 no puede correr antes que la autorización."""
    user_id = escenario.usuario(con_rol_operativo=True)
    etag = versions_mod.get_version_asset(
        escenario.documento.id, escenario.version.id, "img01.png",
        request=_request(), user_id=user_id, ctx=None,
    ).headers["etag"]

    sin_permiso = escenario.usuario(con_rol_operativo=False)
    with pytest.raises(HTTPException) as exc:
        versions_mod.get_version_asset(
            escenario.documento.id, escenario.version.id, "img01.png",
            request=_request({"if-none-match": etag}), user_id=sin_permiso, ctx=None,
        )
    assert exc.value.status_code == 403


# ── Lo que va al navegador y lo que se guarda ────────────────────────────────


def test_el_html_que_va_al_navegador_apunta_al_proxy_y_no_a_la_api():
    html = (
        '<img src="/api/v1/documents/doc-1/versions/ver-1/assets/img01.png">'
        '<img src="assets/paso1.png">'
    )
    servido = rewrite_img_src_to_proxy(html, "run-1", tenant_id="tenant-9")

    assert f'src="{PROXY_PREFIX}/api/v1/documents/doc-1/versions/ver-1/assets/img01.png?t=tenant-9"' in servido
    assert f'src="{PROXY_PREFIX}/api/v1/artifacts/run-1/assets/paso1.png?t=tenant-9"' in servido
    # Rutas RELATIVAS: el proxy vive en el front, no en la API.
    assert "http" not in servido


def test_lo_que_se_guarda_no_tiene_ni_url_absoluta_ni_token():
    canonico = (
        '<p>Texto</p>'
        '<img src="/api/v1/documents/doc-1/versions/ver-1/assets/img01.png">'
        '<img src="assets/paso1.png">'
    )
    servido = rewrite_img_src_to_proxy(canonico, "run-1", tenant_id="tenant-9")

    guardado = strip_image_url_tokens(servido)

    assert guardado == canonico
    assert "token=" not in guardado
    assert PROXY_PREFIX not in guardado
    assert "http://" not in guardado and "https://" not in guardado


def test_el_contenido_viejo_con_urls_firmadas_se_limpia_igual():
    """
    Hay `content_html` guardado antes de la normalización, con URLs absolutas y
    token adentro. Al guardar de nuevo tiene que quedar en forma canónica.
    """
    sucio = (
        '<p>Contenido guardado en 2025</p>'
        '<img src="https://api.margaystudio.io/api/v1/documents/doc-1/versions/ver-1'
        '/assets/img01.png?token=1799999999.ws-1.deadbeefcafe">'
        '<img src="https://api.margaystudio.io/api/v1/artifacts/run-1/assets/paso1.png'
        '?token=1799999999.ws-1.otracosa">'
    )

    limpio = strip_image_url_tokens(sucio)

    assert "token=" not in limpio
    assert "margaystudio.io" not in limpio
    assert 'src="/api/v1/documents/doc-1/versions/ver-1/assets/img01.png"' in limpio
    assert 'src="assets/paso1.png"' in limpio


# ── Lo que NO cambia ─────────────────────────────────────────────────────────


def test_el_render_del_servidor_no_depende_de_una_sesion():
    """
    El freeze y el preview resuelven las imágenes con `StorageAssetFetcher`,
    leyendo blobs de object storage. Si dependieran de una sesión o de un token,
    el artefacto de auditoría dependería de que alguien esté logueado para poder
    congelarse.
    """
    import inspect

    from api.routes import _freeze

    fuente_freeze = inspect.getsource(_freeze.freeze_approved_pdf)
    assert "StorageAssetFetcher" in fuente_freeze
    assert "token" not in fuente_freeze.lower()

    fuente_preview = inspect.getsource(versions_mod.get_version_preview_pdf)
    assert "StorageAssetFetcher" in fuente_preview
    assert PROXY_PREFIX not in fuente_preview
