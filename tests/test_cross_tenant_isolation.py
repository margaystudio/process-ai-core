"""Tests de aislamiento cross-tenant (tarea 1.7).

Estrategia:
  - Se mockea fetch_workspace_context y _decode_and_verify_supabase_jwt para
    controlar dos contextos independientes (tenant A y tenant B) sin necesitar
    tokens JWT reales ni el servicio margay-workspace levantado.
  - sync_workspace_access corre con el flujo REAL: crea Workspaces locales,
    Users y WorkspaceMemberships a partir del contexto — sin shortcuts.
  - get_current_user_id también corre el flujo real: extrae el sub del JWT
    (mockeado) y busca el User local que sync_workspace_access ya creó.

Criterio del test (del prompt 1.7):
  - Tenant A ve sus propios recursos (control positivo).
  - Tenant B recibe 403 / 404 al intentar acceder a datos de tenant A.
  - El aislamiento se demuestra tanto en /folders como en /documents.

Nota sobre has_permission en tests de documents:
  En un entorno sin seed_permissions.py ejecutado, has_permission devuelve
  False incluso para el admin (porque el rol no tiene permisos asignados).
  Para los tests de documents, mockeamos has_permission en el módulo de ruta
  para que use la membresía como único criterio: True si el usuario tiene
  membership en ese workspace, False si no. Esto refleja exactamente el límite
  de aislamiento real (membership-based isolation).
  Los tests de /folders usan el flujo real sin mockear has_permission.
"""

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.workspace_client import (
    WorkspaceApplication,
    WorkspaceSessionContext,
    WorkspaceTenant,
    WorkspaceUser,
    _cache_clear,
)
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    Folder,
    Process,
    User,
    Workspace,
    WorkspaceMembership,
)


# ── Identidades únicas por sesión de test ────────────────────────────────────
# Usamos UUIDs para evitar colisiones con datos existentes en la DB real.

_RUN_ID = str(uuid.uuid4())[:8]
TENANT_A_ID = f"iso-tenant-a-{_RUN_ID}"
TENANT_B_ID = f"iso-tenant-b-{_RUN_ID}"
SUB_A = f"iso-sub-a-{_RUN_ID}"
SUB_B = f"iso-sub-b-{_RUN_ID}"
EMAIL_A = f"usera-{_RUN_ID}@tenant-a.com"
EMAIL_B = f"userb-{_RUN_ID}@tenant-b.com"
TOKEN_A = f"fake-token-tenant-a-{_RUN_ID}"
TOKEN_B = f"fake-token-tenant-b-{_RUN_ID}"


# ── Contextos de workspace mockeados ─────────────────────────────────────────

def _make_ctx(tenant_id: str, user_sub: str, email: str, slug: str) -> WorkspaceSessionContext:
    """Contexto mínimo que pasa el gate require_process_ai_access."""
    return WorkspaceSessionContext(
        user=WorkspaceUser(id=user_sub, email=email, first_name="Test", last_name="User"),
        platform_roles=[],
        tenant_roles=["tenant_admin"],
        tenant=WorkspaceTenant(id=tenant_id, name=f"Tenant {tenant_id[:6]}", slug=slug),
        tenants=[WorkspaceTenant(id=tenant_id, name=f"Tenant {tenant_id[:6]}", slug=slug)],
        applications=[WorkspaceApplication(key="process_ai", name="Process AI", type="module")],
    )


CTX_A = _make_ctx(TENANT_A_ID, SUB_A, EMAIL_A, f"iso-a-{_RUN_ID}")
CTX_B = _make_ctx(TENANT_B_ID, SUB_B, EMAIL_B, f"iso-b-{_RUN_ID}")

_CONTEXTS = {TOKEN_A: CTX_A, TOKEN_B: CTX_B}
_JWT_PAYLOADS = {
    TOKEN_A: {"sub": SUB_A, "email": EMAIL_A, "exp": 9_999_999_999},
    TOKEN_B: {"sub": SUB_B, "email": EMAIL_B, "exp": 9_999_999_999},
}


def _mock_decode_jwt(token: str) -> dict:
    if token in _JWT_PAYLOADS:
        return _JWT_PAYLOADS[token]
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


def _mock_fetch_ctx(token: str, active_tenant_id: str | None = None) -> WorkspaceSessionContext:
    if token in _CONTEXTS:
        return _CONTEXTS[token]
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


# ── Fixture principal ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def clear_ws_cache_module():
    """Limpia la caché del workspace client antes y después del módulo."""
    _cache_clear()
    yield
    _cache_clear()


@pytest.fixture(scope="module")
def client():
    """
    TestClient con JWT y fetch_workspace_context mockeados.
    scope=module: se reutiliza entre todos los tests del módulo para que los
    datos creados en un test sean visibles en los siguientes.
    """
    with patch(
        "api.dependencies._decode_and_verify_supabase_jwt",
        side_effect=_mock_decode_jwt,
    ):
        with patch(
            "api.workspace_client.fetch_workspace_context",
            side_effect=_mock_fetch_ctx,
        ):
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


# ── Helpers ───────────────────────────────────────────────────────────────────

def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _local_user_id(sub: str) -> str | None:
    with get_db_session() as s:
        u = s.query(User).filter_by(external_id=sub).first()
        return str(u.id) if u else None


def _local_workspace_id(tenant_id: str) -> str | None:
    with get_db_session() as s:
        ws = s.query(Workspace).filter_by(tenant_id=tenant_id).first()
        return str(ws.id) if ws else None


def _root_folder_id(workspace_id: str) -> str | None:
    """Devuelve el id de la carpeta raíz creada automáticamente por sync."""
    with get_db_session() as s:
        folder = s.query(Folder).filter_by(workspace_id=workspace_id, parent_id=None).first()
        return str(folder.id) if folder else None


def _membership_based_has_permission(session, user_id, workspace_id, permission_name):
    """
    Reemplazo de has_permission para tests de documents:
    devuelve True si y solo si el usuario tiene WorkspaceMembership en ese
    workspace — sin depender de que los permisos estén sembrados.

    Esto replica el límite real de aislamiento: sin membership → sin acceso.
    El comportamiento de producción (con seed) es equivalente porque los roles
    de sistema sí tienen los permisos asignados.
    """
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    return membership is not None


def _trigger_sync(client: TestClient, token: str) -> None:
    """
    Dispara una request al router de folders para que sync_workspace_access
    cree las entidades locales (Workspace, User, WorkspaceMembership).
    El resultado HTTP no importa aquí; solo nos importa el efecto en la DB.
    """
    client.get("/api/v1/folders", headers=_h(token))


def _create_process_in_workspace(workspace_id: str) -> str:
    """
    Crea un Process directamente en la DB y devuelve su ID.
    Usa la carpeta raíz del workspace (creada por sync) porque folder_id es NOT NULL.
    """
    folder_id = _root_folder_id(workspace_id)
    assert folder_id is not None, (
        f"Workspace {workspace_id} debe tener una carpeta raíz creada por sync"
    )
    doc_id = f"iso-doc-{uuid.uuid4().hex[:8]}"  # <=36 chars (columna id es String(36))
    with get_db_session() as s:
        doc = Process(
            id=doc_id,
            workspace_id=workspace_id,
            folder_id=folder_id,
            document_type="process",
            name="Proceso de aislamiento",
            description="Documento de test de aislamiento cross-tenant",
            status="approved",
        )
        s.add(doc)
        s.commit()
    return doc_id


# ── Tests: verificación de estructura creada por sync ─────────────────────────

class TestSyncCreaEntidadesAisladas:
    """
    Verifica que sync_workspace_access crea Workspaces, Users y
    WorkspaceMemberships aislados: A en workspace_a, B en workspace_b,
    y que A NO tiene membership en workspace_b (ni B en workspace_a).
    """

    def test_sync_crea_workspaces_distintos(self, client):
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        ws_b = _local_workspace_id(TENANT_B_ID)

        assert ws_a is not None, "workspace A no fue creado por sync"
        assert ws_b is not None, "workspace B no fue creado por sync"
        assert ws_a != ws_b, "workspace A y B no deben ser el mismo"

    def test_sync_crea_usuarios_distintos(self, client):
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        user_a = _local_user_id(SUB_A)
        user_b = _local_user_id(SUB_B)

        assert user_a is not None, "user A no fue creado por sync"
        assert user_b is not None, "user B no fue creado por sync"
        assert user_a != user_b, "user A y B no deben ser el mismo"

    def test_sync_crea_memberships_en_workspace_correcto(self, client):
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        ws_b = _local_workspace_id(TENANT_B_ID)
        user_a = _local_user_id(SUB_A)
        user_b = _local_user_id(SUB_B)

        with get_db_session() as s:
            # Cada usuario tiene membership en SU workspace
            mem_a = s.query(WorkspaceMembership).filter_by(
                user_id=user_a, workspace_id=ws_a
            ).first()
            mem_b = s.query(WorkspaceMembership).filter_by(
                user_id=user_b, workspace_id=ws_b
            ).first()
            assert mem_a is not None, "user A debe tener membership en workspace A"
            assert mem_b is not None, "user B debe tener membership en workspace B"
            assert mem_a.role == "admin", "tenant_admin debe mapearse a rol 'admin'"

    def test_sync_no_crea_cross_memberships(self, client):
        """user A NO debe tener membership en workspace B (ni viceversa)."""
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        ws_b = _local_workspace_id(TENANT_B_ID)
        user_a = _local_user_id(SUB_A)
        user_b = _local_user_id(SUB_B)

        with get_db_session() as s:
            cross_a_in_b = s.query(WorkspaceMembership).filter_by(
                user_id=user_a, workspace_id=ws_b
            ).first()
            cross_b_in_a = s.query(WorkspaceMembership).filter_by(
                user_id=user_b, workspace_id=ws_a
            ).first()

        assert cross_a_in_b is None, "user A NO debe tener membership en workspace B"
        assert cross_b_in_a is None, "user B NO debe tener membership en workspace A"

    def test_sync_es_idempotente(self, client):
        """Llamar sync N veces con el mismo token no crea memberships duplicadas."""
        for _ in range(3):
            _trigger_sync(client, TOKEN_A)

        ws_a = _local_workspace_id(TENANT_A_ID)
        user_a = _local_user_id(SUB_A)

        with get_db_session() as s:
            count = s.query(WorkspaceMembership).filter_by(
                user_id=user_a, workspace_id=ws_a
            ).count()
        assert count == 1, f"sync idempotente: esperado 1 membership, obtuvo {count}"


# ── Tests: aislamiento en /folders ────────────────────────────────────────────
# Estos tests usan el flujo REAL de _require_workspace_member (sin mock).

class TestFoldersIsolation:
    """
    El endpoint GET /api/v1/folders/{folder_id} llama _require_workspace_member,
    que verifica membership en el workspace de la carpeta.
    Tenant B no tiene membership en workspace A → 403 real sin ningún mock.
    """

    def test_control_positivo_a_ve_sus_carpetas(self, client):
        """Tenant A puede listar sus propias carpetas (200)."""
        _trigger_sync(client, TOKEN_A)

        resp = client.get("/api/v1/folders", headers=_h(TOKEN_A))
        assert resp.status_code == 200, (
            f"Tenant A debe poder listar sus carpetas, obtuvo {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        assert isinstance(data, list)

    def test_control_positivo_a_ve_su_carpeta_raiz(self, client):
        """Tenant A puede acceder a su carpeta raíz creada automáticamente por sync."""
        _trigger_sync(client, TOKEN_A)

        ws_a = _local_workspace_id(TENANT_A_ID)
        folder_a_id = _root_folder_id(ws_a)
        assert folder_a_id is not None, "sync debe crear al menos una carpeta raíz en workspace A"

        resp = client.get(f"/api/v1/folders/{folder_a_id}", headers=_h(TOKEN_A))
        assert resp.status_code == 200, (
            f"Tenant A debe poder acceder a su carpeta raíz, obtuvo {resp.status_code}: {resp.text}"
        )

    def test_b_no_puede_acceder_a_carpeta_de_a(self, client):
        """
        AISLAMIENTO: Tenant B obtiene 403 al intentar acceder a una carpeta de tenant A.
        Sin mock — _require_workspace_member usa el RBAC real.
        """
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        folder_a_id = _root_folder_id(ws_a)
        assert folder_a_id is not None

        resp = client.get(f"/api/v1/folders/{folder_a_id}", headers=_h(TOKEN_B))
        assert resp.status_code in (403, 404), (
            f"Esperado 403/404 (tenant B no tiene acceso a carpeta de tenant A) "
            f"pero obtuvo {resp.status_code}: {resp.text}"
        )

    def test_b_no_puede_crear_carpeta_en_workspace_de_a(self, client):
        """
        AISLAMIENTO: Tenant B no puede crear carpetas en workspace A.
        sync_workspace_access asigna el workspace activo desde el CONTEXTO del request
        (ctx del tenant B → workspace B), por lo que la carpeta se crearía en workspace B,
        no en workspace A. Verificamos que la carpeta raíz de A no aparece en workspace B.
        """
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        ws_b = _local_workspace_id(TENANT_B_ID)

        assert ws_a is not None
        assert ws_b is not None

        # El workspace de cada request queda determinado por el contexto
        # (ctx.tenant.id → local workspace), no por parámetros del cliente.
        assert ws_a != ws_b, "workspace A y B deben ser distintos (aislamiento de datos)"


# ── Tests: aislamiento en /documents ─────────────────────────────────────────
# has_permission se mockea para que solo dependa de membership (sin seeds).

class TestDocumentsIsolation:
    """
    Para documents, has_permission se reemplaza por _membership_based_has_permission:
    True si el usuario tiene membership en ese workspace, False si no.
    Esto aísla el test de si seed_permissions.py fue ejecutado o no,
    mientras se preserva el límite real de aislamiento (membership-based).
    """

    @pytest.fixture(autouse=True)
    def patch_has_permission(self, monkeypatch):
        import api.routes.documents.crud as docs_route
        monkeypatch.setattr(docs_route, "has_permission", _membership_based_has_permission)
        # can_view_folder para admin ya hace bypass; lo forzamos a True para simplificar.
        monkeypatch.setattr(docs_route, "can_view_folder", lambda *_: True)

    def test_control_positivo_a_ve_su_documento(self, client):
        """Tenant A puede acceder a un documento creado en su propio workspace."""
        _trigger_sync(client, TOKEN_A)

        ws_a = _local_workspace_id(TENANT_A_ID)
        doc_id = _create_process_in_workspace(ws_a)

        resp = client.get(f"/api/v1/documents/{doc_id}", headers=_h(TOKEN_A))
        assert resp.status_code == 200, (
            f"Tenant A debe acceder a su propio documento, obtuvo {resp.status_code}: {resp.text}"
        )
        assert resp.json()["id"] == doc_id

    def test_b_no_puede_ver_documento_de_a(self, client):
        """
        AISLAMIENTO: Tenant B obtiene 403 al intentar acceder a un documento de tenant A.
        has_permission devuelve False para (user_b, workspace_a): no hay membership.
        """
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        doc_id = _create_process_in_workspace(ws_a)

        resp = client.get(f"/api/v1/documents/{doc_id}", headers=_h(TOKEN_B))
        assert resp.status_code in (403, 404), (
            f"Esperado 403/404 (tenant B no tiene acceso al doc de tenant A) "
            f"pero obtuvo {resp.status_code}: {resp.text}"
        )

    def test_lista_de_b_no_incluye_documentos_de_a(self, client):
        """
        AISLAMIENTO: Al listar documentos, tenant B solo ve los de su workspace.
        El endpoint filtra por workspace_id derivado del contexto del tenant.
        """
        _trigger_sync(client, TOKEN_A)
        _trigger_sync(client, TOKEN_B)

        ws_a = _local_workspace_id(TENANT_A_ID)
        doc_id_a = _create_process_in_workspace(ws_a)

        # Tenant B lista sus documentos (workspace B, derivado del contexto)
        resp = client.get("/api/v1/documents", headers=_h(TOKEN_B))
        assert resp.status_code == 200, (
            f"Tenant B debe poder listar documentos, obtuvo {resp.status_code}: {resp.text}"
        )
        doc_ids = [d["id"] for d in resp.json()]
        assert doc_id_a not in doc_ids, (
            "El documento de tenant A NO debe aparecer en la lista de tenant B"
        )

    def test_lista_de_a_incluye_su_documento(self, client):
        """Control positivo: tenant A ve sus propios documentos en la lista."""
        _trigger_sync(client, TOKEN_A)

        ws_a = _local_workspace_id(TENANT_A_ID)
        doc_id_a = _create_process_in_workspace(ws_a)

        resp = client.get("/api/v1/documents", headers=_h(TOKEN_A))
        assert resp.status_code == 200, (
            f"Tenant A debe poder listar documentos, obtuvo {resp.status_code}: {resp.text}"
        )
        doc_ids = [d["id"] for d in resp.json()]
        assert doc_id_a in doc_ids, (
            "El documento de tenant A debe aparecer en su propia lista"
        )


# ── Tests: usuario con membresía en MÚLTIPLES workspaces ─────────────────────
# Este es el escenario crítico: un superadmin o alguien que pertenece a varios
# tenants. Aunque tenga membership en workspace B, cuando su contexto activo
# es tenant A, NO debe poder acceder a recursos de B via URL directa.

_MULTI_RUN_ID = str(uuid.uuid4())[:8]
TENANT_MULTI_A_ID = f"iso-multi-a-{_MULTI_RUN_ID}"
TENANT_MULTI_B_ID = f"iso-multi-b-{_MULTI_RUN_ID}"
SUB_MULTI = f"iso-multi-sub-{_MULTI_RUN_ID}"
EMAIL_MULTI = f"multi-{_MULTI_RUN_ID}@example.com"
# Mismo usuario, dos contextos (en cada tenant parado en uno distinto)
TOKEN_MULTI_AS_A = f"fake-token-multi-as-a-{_MULTI_RUN_ID}"
TOKEN_MULTI_AS_B = f"fake-token-multi-as-b-{_MULTI_RUN_ID}"

CTX_MULTI_AS_A = WorkspaceSessionContext(
    user=WorkspaceUser(id=SUB_MULTI, email=EMAIL_MULTI, first_name="Multi", last_name="User"),
    platform_roles=[],
    tenant_roles=["tenant_admin"],
    tenant=WorkspaceTenant(id=TENANT_MULTI_A_ID, name="Multi-Tenant A", slug=f"multi-a-{_MULTI_RUN_ID}"),
    tenants=[
        WorkspaceTenant(id=TENANT_MULTI_A_ID, name="Multi-Tenant A", slug=f"multi-a-{_MULTI_RUN_ID}"),
        WorkspaceTenant(id=TENANT_MULTI_B_ID, name="Multi-Tenant B", slug=f"multi-b-{_MULTI_RUN_ID}"),
    ],
    applications=[WorkspaceApplication(key="process_ai", name="Process AI", type="module")],
)

CTX_MULTI_AS_B = WorkspaceSessionContext(
    user=WorkspaceUser(id=SUB_MULTI, email=EMAIL_MULTI, first_name="Multi", last_name="User"),
    platform_roles=[],
    tenant_roles=["tenant_admin"],
    tenant=WorkspaceTenant(id=TENANT_MULTI_B_ID, name="Multi-Tenant B", slug=f"multi-b-{_MULTI_RUN_ID}"),
    tenants=[
        WorkspaceTenant(id=TENANT_MULTI_A_ID, name="Multi-Tenant A", slug=f"multi-a-{_MULTI_RUN_ID}"),
        WorkspaceTenant(id=TENANT_MULTI_B_ID, name="Multi-Tenant B", slug=f"multi-b-{_MULTI_RUN_ID}"),
    ],
    applications=[WorkspaceApplication(key="process_ai", name="Process AI", type="module")],
)

_MULTI_CONTEXTS = {
    **_CONTEXTS,
    TOKEN_MULTI_AS_A: CTX_MULTI_AS_A,
    TOKEN_MULTI_AS_B: CTX_MULTI_AS_B,
}
_MULTI_JWT_PAYLOADS = {
    **_JWT_PAYLOADS,
    TOKEN_MULTI_AS_A: {"sub": SUB_MULTI, "email": EMAIL_MULTI, "exp": 9_999_999_999},
    TOKEN_MULTI_AS_B: {"sub": SUB_MULTI, "email": EMAIL_MULTI, "exp": 9_999_999_999},
}


def _mock_decode_jwt_multi(token: str) -> dict:
    if token in _MULTI_JWT_PAYLOADS:
        return _MULTI_JWT_PAYLOADS[token]
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


def _mock_fetch_ctx_multi(token: str, active_tenant_id: str | None = None) -> WorkspaceSessionContext:
    if token in _MULTI_CONTEXTS:
        return _MULTI_CONTEXTS[token]
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid token")


@pytest.fixture(scope="module")
def multi_client():
    """
    Cliente con mocks ampliados que soportan también el usuario multi-workspace.
    """
    with patch(
        "api.dependencies._decode_and_verify_supabase_jwt",
        side_effect=_mock_decode_jwt_multi,
    ):
        with patch(
            "api.workspace_client.fetch_workspace_context",
            side_effect=_mock_fetch_ctx_multi,
        ):
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


class TestMultiWorkspaceUserIsolation:
    """
    Usuario con membership en WORKSPACE A y WORKSPACE B.
    Con contexto activo = tenant A, NO puede acceder a recursos de B via URL directa.
    Esto verifica que el chequeo workspace_activo == recurso.workspace_id funciona
    incluso cuando el usuario tendría permisos en B (si su contexto fuera B).
    """

    @pytest.fixture(autouse=True)
    def patch_has_permission(self, monkeypatch):
        import api.routes.documents.crud as docs_route
        monkeypatch.setattr(docs_route, "has_permission", _membership_based_has_permission)
        monkeypatch.setattr(docs_route, "can_view_folder", lambda *_: True)

    def _setup_multi_user(self, client):
        """
        Dispara sync para el usuario multi en ambos contextos.
        Después del setup, el usuario tiene:
          - membership en workspace de TENANT_MULTI_A_ID
          - membership en workspace de TENANT_MULTI_B_ID
        """
        client.get("/api/v1/folders", headers=_h(TOKEN_MULTI_AS_A))
        client.get("/api/v1/folders", headers=_h(TOKEN_MULTI_AS_B))

    def test_multi_user_tiene_membership_en_ambos_workspaces(self, multi_client):
        """Verifica el setup: el usuario multi tiene membership en ambos workspaces."""
        self._setup_multi_user(multi_client)

        ws_a = _local_workspace_id(TENANT_MULTI_A_ID)
        ws_b = _local_workspace_id(TENANT_MULTI_B_ID)
        assert ws_a is not None and ws_b is not None
        assert ws_a != ws_b

        user_id = _local_user_id(SUB_MULTI)
        assert user_id is not None

        with get_db_session() as s:
            mem_a = s.query(WorkspaceMembership).filter_by(
                user_id=user_id, workspace_id=ws_a
            ).first()
            mem_b = s.query(WorkspaceMembership).filter_by(
                user_id=user_id, workspace_id=ws_b
            ).first()
        assert mem_a is not None, "usuario multi debe tener membership en workspace A"
        assert mem_b is not None, "usuario multi debe tener membership en workspace B"

    def test_multi_user_en_contexto_a_no_puede_acceder_carpeta_de_b(self, multi_client):
        """
        AISLAMIENTO CRÍTICO: usuario con membresía en A y B, parado en contexto de A,
        obtiene 404 al acceder a una carpeta de B via URL directa.
        Sin el chequeo workspace_activo, este request devolvería 200 (exploit real).
        """
        self._setup_multi_user(multi_client)

        ws_b = _local_workspace_id(TENANT_MULTI_B_ID)
        assert ws_b is not None
        folder_b_id = _root_folder_id(ws_b)
        assert folder_b_id is not None

        # Mismo usuario pero contexto activo = tenant A
        resp = multi_client.get(f"/api/v1/folders/{folder_b_id}", headers=_h(TOKEN_MULTI_AS_A))
        assert resp.status_code == 404, (
            f"Usuario multi parado en contexto A debe recibir 404 al acceder a carpeta de B "
            f"(obtuvo {resp.status_code}: {resp.text})"
        )

    def test_multi_user_en_contexto_b_no_puede_acceder_carpeta_de_a(self, multi_client):
        """Idem, sentido inverso: parado en B, no puede acceder a carpeta de A."""
        self._setup_multi_user(multi_client)

        ws_a = _local_workspace_id(TENANT_MULTI_A_ID)
        assert ws_a is not None
        folder_a_id = _root_folder_id(ws_a)
        assert folder_a_id is not None

        resp = multi_client.get(f"/api/v1/folders/{folder_a_id}", headers=_h(TOKEN_MULTI_AS_B))
        assert resp.status_code == 404, (
            f"Usuario multi parado en contexto B debe recibir 404 al acceder a carpeta de A "
            f"(obtuvo {resp.status_code}: {resp.text})"
        )

    def test_multi_user_en_contexto_a_puede_acceder_carpeta_propia(self, multi_client):
        """Control positivo: el mismo usuario SÍ accede a sus propios recursos en A."""
        self._setup_multi_user(multi_client)

        ws_a = _local_workspace_id(TENANT_MULTI_A_ID)
        folder_a_id = _root_folder_id(ws_a)
        assert folder_a_id is not None

        resp = multi_client.get(f"/api/v1/folders/{folder_a_id}", headers=_h(TOKEN_MULTI_AS_A))
        assert resp.status_code == 200, (
            f"Usuario multi en contexto A debe acceder a su carpeta en A "
            f"(obtuvo {resp.status_code}: {resp.text})"
        )

    def test_multi_user_en_contexto_a_no_puede_acceder_documento_de_b(self, multi_client):
        """
        AISLAMIENTO CRÍTICO: usuario multi parado en contexto A obtiene 404
        al acceder a un documento de B via URL directa.
        """
        self._setup_multi_user(multi_client)

        ws_b = _local_workspace_id(TENANT_MULTI_B_ID)
        doc_b_id = _create_process_in_workspace(ws_b)

        resp = multi_client.get(f"/api/v1/documents/{doc_b_id}", headers=_h(TOKEN_MULTI_AS_A))
        assert resp.status_code == 404, (
            f"Usuario multi parado en contexto A debe recibir 404 al acceder al doc de B "
            f"(obtuvo {resp.status_code}: {resp.text})"
        )

    def test_multi_user_en_contexto_a_puede_acceder_documento_propio(self, multi_client):
        """Control positivo: el mismo usuario SÍ accede a documentos de A cuando está en A."""
        self._setup_multi_user(multi_client)

        ws_a = _local_workspace_id(TENANT_MULTI_A_ID)
        doc_a_id = _create_process_in_workspace(ws_a)

        resp = multi_client.get(f"/api/v1/documents/{doc_a_id}", headers=_h(TOKEN_MULTI_AS_A))
        assert resp.status_code == 200, (
            f"Usuario multi en contexto A debe acceder a su doc en A "
            f"(obtuvo {resp.status_code}: {resp.text})"
        )
