"""
Tests mínimos de autorización para validación con segregación de funciones.

Verifica que:
1) Creador no puede aprobar su propia versión
2) Creador no puede rechazar su propia versión
3) Otro usuario sí puede aprobar/rechazar
4) Rechazo requiere observations
"""

import pytest
from sqlalchemy.orm import Session
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Validation, User, Workspace, Folder
from process_ai_core.db.helpers import (
    get_or_create_draft,
    submit_version_for_review,
    approve_version,
    reject_version,
)
import uuid
from datetime import datetime, UTC


@pytest.fixture
def session():
    """Sesión de base de datos para tests."""
    with get_db_session() as s:
        yield s


@pytest.fixture
def workspace(session: Session):
    """Workspace de prueba."""
    unique_id = str(uuid.uuid4())[:8]
    workspace = Workspace(
        id=str(uuid.uuid4()),
        name="Test Workspace",
        slug=f"test-workspace-{unique_id}",
        workspace_type="organization",
    )
    session.add(workspace)
    session.flush()
    return workspace


@pytest.fixture
def folder(session: Session, workspace: Workspace):
    """Carpeta raíz para tests."""
    folder = Folder(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Root",
        path="/",
        parent_id=None,
    )
    session.add(folder)
    session.flush()
    return folder


@pytest.fixture
def creator_user(session: Session):
    """Usuario creador."""
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        id=str(uuid.uuid4()),
        email=f"creator-{unique_id}@test.com",
        name="Creator User",
        external_id=str(uuid.uuid4()),
        auth_provider="test",
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def approver_user(session: Session):
    """Usuario aprobador (diferente del creador)."""
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        id=str(uuid.uuid4()),
        email=f"approver-{unique_id}@test.com",
        name="Approver User",
        external_id=str(uuid.uuid4()),
        auth_provider="test",
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def document(session: Session, workspace: Workspace, folder: Folder):
    """Documento de prueba."""
    from process_ai_core.db.models import Process
    doc = Process(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        document_type="process",
        name="Test Document",
        description="Test description",
        status="draft",
        folder_id=folder.id,
    )
    session.add(doc)
    session.flush()
    return doc


def test_creator_cannot_approve_own_version(session: Session, document: Document, creator_user: User, approver_user: User):
    """Test 1: Creador no puede aprobar su propia versión."""
    # Crear versión DRAFT con created_by = creator_user
    draft = get_or_create_draft(
        session=session,
        document_id=document.id,
        user_id=creator_user.id,
    )
    assert draft.created_by == creator_user.id, "La versión debe tener created_by = creator_user.id"
    
    # Enviar a revisión
    version, validation = submit_version_for_review(
        session=session,
        version_id=draft.id,
        submitter_id=creator_user.id,
    )
    assert version.version_status == "IN_REVIEW"
    assert version.created_by == creator_user.id, "created_by no debe cambiar al submit"
    
    # Intentar aprobar con el creador (debe fallar)
    with pytest.raises(ValueError, match="No puedes aprobar una versión que creaste"):
        approve_version(
            session=session,
            validation_id=validation.id,
            approver_id=creator_user.id,
        )
    
    # Verificar que otro usuario SÍ puede aprobar
    approved_version = approve_version(
        session=session,
        validation_id=validation.id,
        approver_id=approver_user.id,
    )
    assert approved_version.version_status == "APPROVED"
    assert approved_version.approved_by == approver_user.id


def test_creator_cannot_reject_own_version(session: Session, document: Document, creator_user: User, approver_user: User):
    """Test 2: Creador no puede rechazar su propia versión."""
    # Crear versión DRAFT con created_by = creator_user
    draft = get_or_create_draft(
        session=session,
        document_id=document.id,
        user_id=creator_user.id,
    )
    assert draft.created_by == creator_user.id
    
    # Enviar a revisión
    version, validation = submit_version_for_review(
        session=session,
        version_id=draft.id,
        submitter_id=creator_user.id,
    )
    assert version.version_status == "IN_REVIEW"
    
    # Intentar rechazar con el creador (debe fallar)
    with pytest.raises(ValueError, match="No puedes rechazar una versión que creaste"):
        reject_version(
            session=session,
            validation_id=validation.id,
            rejector_id=creator_user.id,
            observations="Observaciones de rechazo",
        )
    
    # Verificar que otro usuario SÍ puede rechazar
    rejected_version = reject_version(
        session=session,
        validation_id=validation.id,
        rejector_id=approver_user.id,
        observations="Observaciones de rechazo válidas",
    )
    assert rejected_version.version_status == "REJECTED"
    assert rejected_version.rejected_by == approver_user.id


def test_other_user_can_approve(session: Session, document: Document, creator_user: User, approver_user: User):
    """Test 3: Otro usuario sí puede aprobar."""
    # Crear versión DRAFT con created_by = creator_user
    draft = get_or_create_draft(
        session=session,
        document_id=document.id,
        user_id=creator_user.id,
    )
    
    # Enviar a revisión
    version, validation = submit_version_for_review(
        session=session,
        version_id=draft.id,
        submitter_id=creator_user.id,
    )
    
    # Aprobar con otro usuario (debe funcionar)
    approved_version = approve_version(
        session=session,
        validation_id=validation.id,
        approver_id=approver_user.id,
    )
    
    assert approved_version.version_status == "APPROVED"
    assert approved_version.approved_by == approver_user.id
    assert approved_version.created_by == creator_user.id  # created_by no cambia


def test_reject_requires_observations(session: Session, document: Document, creator_user: User, approver_user: User):
    """Test 4: Rechazo requiere observations."""
    # Crear versión DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=document.id,
        user_id=creator_user.id,
    )
    
    # Enviar a revisión
    version, validation = submit_version_for_review(
        session=session,
        version_id=draft.id,
        submitter_id=creator_user.id,
    )
    
    # Intentar rechazar sin observations (debe fallar)
    with pytest.raises(ValueError, match="Las observaciones son obligatorias"):
        reject_version(
            session=session,
            validation_id=validation.id,
            rejector_id=approver_user.id,
            observations="",  # Vacío
        )
    
    # Intentar rechazar con observations solo espacios (debe fallar)
    with pytest.raises(ValueError, match="Las observaciones son obligatorias"):
        reject_version(
            session=session,
            validation_id=validation.id,
            rejector_id=approver_user.id,
            observations="   ",  # Solo espacios
        )
    
    # Rechazar con observations válidas (debe funcionar)
    rejected_version = reject_version(
        session=session,
        validation_id=validation.id,
        rejector_id=approver_user.id,
        observations="Observaciones válidas de rechazo",
    )
    assert rejected_version.version_status == "REJECTED"


def test_created_by_not_overwritten_on_submit(session: Session, document: Document, creator_user: User):
    """Test adicional: created_by no se sobrescribe al submit."""
    # Crear versión DRAFT con created_by = creator_user
    draft = get_or_create_draft(
        session=session,
        document_id=document.id,
        user_id=creator_user.id,
    )
    assert draft.created_by == creator_user.id
    
    # Enviar a revisión con submitter_id diferente (si existiera)
    # created_by debe mantenerse
    version, validation = submit_version_for_review(
        session=session,
        version_id=draft.id,
        submitter_id=creator_user.id,  # Mismo usuario, pero podría ser diferente
    )
    assert version.created_by == creator_user.id, "created_by no debe cambiar al submit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
