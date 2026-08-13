"""La capa semántica respeta el permiso por CARPETA (hallazgo B1 de la auditoría).

Tres agentes independientes marcaron lo mismo: `semantic.py` verificaba el
tenant y, a lo sumo, un permiso global — nunca la carpeta. Como
`has_permission` es deliberadamente laxo (True si el usuario tiene el nivel en
ALGUNA carpeta), quien podía aprobar en una carpeta leía el `evidence_text`
—fragmentos del contenido— y decidía sobre el grafo semántico de documentos
que ni siquiera puede abrir.

Estos tests fijan que los seis endpoints combinen las dos cosas, como ya hacían
documents y validations.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from process_ai_core.db.database import Base
from process_ai_core.db.models import (
    Document,
    Folder,
    FolderPermission,
    OperationalRole,
    User,
    UserOperationalRole,
    Workspace,
    WorkspaceMembership,
)
from process_ai_core.db.models_semantic import DocumentRelation

from api.routes import semantic as semantic_route


def _uid() -> str:
    return str(uuid.uuid4())


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
def env(session, monkeypatch):
    """Un documento en una carpeta RESTRINGIDA a un rol operativo."""
    ws = Workspace(id=_uid(), slug=f"ws-{_uid()[:8]}", name="WS", workspace_type="organization")
    session.add(ws)
    session.flush()

    carpeta = Folder(
        id=_uid(), workspace_id=ws.id, name="RRHH", path="RRHH",
        inherits_permissions=False,
    )
    session.add(carpeta)
    session.flush()

    rol = OperationalRole(
        id=_uid(), workspace_id=ws.id, name="RRHH", slug="rrhh",
        access_level="aprobacion",
    )
    session.add(rol)
    session.flush()
    session.add(FolderPermission(
        id=_uid(), folder_id=carpeta.id, operational_role_id=rol.id
    ))

    doc = Document(
        id=_uid(), workspace_id=ws.id, folder_id=carpeta.id, domain="process",
        document_type="procedimiento", name="Sumarios", status="approved",
    )
    session.add(doc)
    session.flush()

    relacion = DocumentRelation(
        id=_uid(), workspace_id=ws.id, document_id=doc.id,
        source_type="document", source_id=doc.id,
        target_type="rol", target_id=_uid(),
        relation_type="menciona", status="candidate",
        evidence_text="El gerente firma el acta de sumario",
    )
    session.add(relacion)
    session.commit()

    monkeypatch.setattr(semantic_route, "resolve_tenant_workspace_id", lambda ctx: ws.id)
    return SimpleNamespace(
        session=session, ws=ws, carpeta=carpeta, rol=rol, doc=doc, relacion=relacion
    )


def _usuario(env, *, con_rol: bool):
    """Miembro del workspace; con o sin el rol operativo que abre la carpeta."""
    u = User(id=_uid(), email=f"{_uid()[:8]}@t.io", name="U")
    env.session.add(u)
    env.session.flush()
    m = WorkspaceMembership(
        id=_uid(), user_id=u.id, workspace_id=env.ws.id, base_access="member"
    )
    env.session.add(m)
    env.session.flush()
    if con_rol:
        env.session.add(UserOperationalRole(
            id=_uid(), workspace_membership_id=m.id, operational_role_id=env.rol.id
        ))
    env.session.commit()
    return u.id


def _ctx():
    return SimpleNamespace(tenant=SimpleNamespace(id="tenant-1"), platform_roles=[])


# ── Lectura: relaciones e impacto ────────────────────────────────────────────

def test_sin_acceso_a_la_carpeta_no_se_leen_las_relaciones(env):
    """`evidence_text` son fragmentos del documento restringido."""
    sin_acceso = _usuario(env, con_rol=False)
    with pytest.raises(HTTPException) as exc:
        semantic_route.get_document_relations(
            document_id=env.doc.id, include_all=False,
            user_id=sin_acceso, session=env.session, ctx=_ctx(),
        )
    assert exc.value.status_code == 403


def test_con_el_rol_operativo_si_se_leen_las_relaciones(env):
    con_acceso = _usuario(env, con_rol=True)
    salida = semantic_route.get_document_relations(
        document_id=env.doc.id, include_all=False,
        user_id=con_acceso, session=env.session, ctx=_ctx(),
    )
    assert salida is not None


def test_sin_acceso_a_la_carpeta_no_se_lee_el_impacto(env):
    sin_acceso = _usuario(env, con_rol=False)
    with pytest.raises(HTTPException) as exc:
        semantic_route.get_document_impact(
            document_id=env.doc.id, user_id=sin_acceso,
            session=env.session, ctx=_ctx(),
        )
    assert exc.value.status_code == 403


# ── Decisión sobre el grafo: confirmar / rechazar ────────────────────────────

def test_sin_acceso_a_la_carpeta_no_se_confirma_una_relacion(env):
    """El caso de la auditoría: aprobador de OTRA carpeta decidiendo acá."""
    sin_acceso = _usuario(env, con_rol=False)
    with pytest.raises(HTTPException) as exc:
        semantic_route.confirm_relation(
            relation_id=env.relacion.id, user_id=sin_acceso,
            session=env.session, ctx=_ctx(),
        )
    assert exc.value.status_code == 403


def test_sin_acceso_a_la_carpeta_no_se_rechaza_una_relacion(env):
    sin_acceso = _usuario(env, con_rol=False)
    with pytest.raises(HTTPException) as exc:
        semantic_route.reject_relation(
            relation_id=env.relacion.id, user_id=sin_acceso,
            session=env.session, ctx=_ctx(),
        )
    assert exc.value.status_code == 403


def test_el_merge_de_entidades_exige_administrador(env):
    """Los knowledge objects son del workspace: se alinea con la bandeja
    `GET /relations`, que ya exigía administración."""
    import inspect

    fuente = inspect.getsource(semantic_route.merge_knowledge_object)
    assert '"workspaces.edit"' in fuente
