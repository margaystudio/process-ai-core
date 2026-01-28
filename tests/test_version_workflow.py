"""
Tests para el flujo de versionado ISO-friendly con enforce DB real.

Prueba:
- Inmutabilidad de versiones APPROVED/REJECTED
- Flujo DRAFT -> IN_REVIEW -> APPROVED/REJECTED
- Clonación de versiones
- Bloqueo de edición
- Enforce de "1 solo DRAFT" y "1 solo IN_REVIEW" (a nivel código y DB)
"""

import pytest
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, DocumentVersion, Validation, Process, Workspace, Folder
from process_ai_core.db.helpers import (
    get_or_create_draft,
    submit_version_for_review,
    approve_version,
    reject_version,
    check_version_immutable,
)


@pytest.fixture
def session():
    """Fixture que proporciona una sesión de base de datos para los tests.
    
    Usa get_db_session() que maneja commit/rollback automáticamente.
    Si hay un error, la sesión hace rollback antes de cerrarse.
    """
    with get_db_session() as db_session:
        yield db_session


@pytest.fixture
def test_workspace(session):
    """Crea un workspace de prueba."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    workspace = Workspace(
        id=f"test-workspace-{unique_id}",
        slug=f"test-workspace-{unique_id}",
        name="Test Workspace",
        workspace_type="organization",
    )
    session.add(workspace)
    session.commit()
    return workspace


@pytest.fixture
def test_folder(session, test_workspace):
    """Crea una carpeta de prueba."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    folder = Folder(
        id=f"test-folder-{unique_id}",
        workspace_id=test_workspace.id,
        name="Test Folder",
        path="Test",
    )
    session.add(folder)
    session.commit()
    return folder


@pytest.fixture
def test_document(session, test_workspace, test_folder):
    """Crea un documento de prueba."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    doc = Process(
        id=f"test-doc-{unique_id}",
        workspace_id=test_workspace.id,
        folder_id=test_folder.id,
        document_type="process",
        name="Test Process",
        description="Test",
        status="draft",
    )
    session.add(doc)
    session.commit()
    return doc


@pytest.fixture
def approved_version(session, test_document):
    """Crea una versión APPROVED."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    version = DocumentVersion(
        id=f"test-version-approved-{unique_id}",
        document_id=test_document.id,
        version_number=1,
        version_status="APPROVED",
        content_type="generated",
        content_json='{"name": "Test Process"}',
        content_markdown="# Test Process",
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    session.add(version)
    session.flush()  # Flush para que la versión tenga ID en la DB antes de la FK
    test_document.approved_version_id = version.id
    test_document.status = "approved"
    session.commit()
    return version


def test_approved_vigente_permite_crear_draft_y_editar(session, test_document, approved_version):
    """Test: APPROVED vigente permite crear DRAFT y editarlo."""
    # Verificar que no bloquea por APPROVED vigente
    is_immutable, reason = check_version_immutable(session, test_document.id)
    assert is_immutable is False, "APPROVED vigente no debe bloquear edición"
    
    # Crear DRAFT desde APPROVED usando get_or_create_draft
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
        source_version_id=None,  # Debe usar APPROVED vigente
    )
    
    assert draft.version_status == "DRAFT"
    assert draft.supersedes_version_id == approved_version.id
    assert draft.version_number == 2
    assert draft.content_json == approved_version.content_json
    
    # Verificar que si llamo de nuevo, devuelve el mismo DRAFT
    draft2 = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    assert draft2.id == draft.id, "Debe devolver el mismo DRAFT, no crear otro"
    
    # Editar DRAFT
    draft.content_json = '{"name": "Test Updated"}'
    draft.content_markdown = "# Test Updated"
    session.commit()
    
    # Verificar que se puede seguir editando
    is_immutable_after_edit, _ = check_version_immutable(session, test_document.id)
    assert is_immutable_after_edit is False
    
    # Verificar que APPROVED sigue vigente
    session.refresh(approved_version)
    assert approved_version.is_current is True
    assert approved_version.version_status == "APPROVED"


def test_get_or_create_draft_devuelve_existente(session, test_document):
    """Test: Si existe DRAFT, get_or_create_draft devuelve el mismo (no crea otro)."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    # Crear DRAFT manualmente
    draft1 = DocumentVersion(
        id=f"draft-1-{unique_id}",
        document_id=test_document.id,
        version_number=1,
        version_status="DRAFT",
        content_type="manual_edit",
        content_json='{"name": "Draft 1"}',
        content_markdown="# Draft 1",
    )
    session.add(draft1)
    session.commit()
    
    # Llamar get_or_create_draft
    draft2 = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Debe devolver el mismo DRAFT
    assert draft2.id == draft1.id
    assert draft2.version_number == 1  # No creó una nueva versión


def test_submit_draft_crea_validation(session, test_document):
    """Test: submit_version_for_review crea Validation y cambia estado a IN_REVIEW."""
    # Crear versión DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar a revisión
    updated_version, validation = submit_version_for_review(session, draft.id)
    
    assert updated_version.version_status == "IN_REVIEW"
    assert updated_version.validation_id == validation.id
    assert validation.status == "pending"
    assert validation.document_id == test_document.id
    assert test_document.status == "pending_validation"


def test_submit_draft_bloquea_si_ya_existe_in_review(session, test_document):
    """Test: No se puede enviar DRAFT a revisión si ya existe IN_REVIEW."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    # FLUJO CORRECTO: crear DRAFT, enviar a IN_REVIEW, luego intentar enviar otro
    # Crear primera versión DRAFT
    draft1 = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar primera DRAFT a revisión
    updated_version1, validation1 = submit_version_for_review(session, draft1.id)
    assert updated_version1.version_status == "IN_REVIEW"
    
    # Crear segunda versión DRAFT (debe fallar porque hay IN_REVIEW)
    with pytest.raises(ValueError, match="tiene una versión IN_REVIEW"):
        get_or_create_draft(
            session=session,
            document_id=test_document.id,
        )
    
    # Intentar enviar otra versión a revisión (no debería existir, pero por si acaso)
    # Primero necesitaríamos crear otra DRAFT, pero eso ya falló arriba
    draft2_manual = DocumentVersion(
        id=f"draft-2-manual-{unique_id}",
        document_id=test_document.id,
        version_number=2,
        version_status="DRAFT",
        content_type="manual_edit",
        content_json='{"name": "Draft 2"}',
        content_markdown="# Draft 2",
    )
    session.add(draft2_manual)
    # Esto debería fallar por enforce DB, pero si no, la lógica debe bloquearlo
    try:
        session.commit()
        # Si llegó aquí, el enforce DB no funcionó, pero la lógica debe bloquearlo
        with pytest.raises(ValueError, match="ya tiene una versión IN_REVIEW"):
            submit_version_for_review(session, draft2_manual.id)
    except IntegrityError:
        # Enforce DB funcionó correctamente
        session.rollback()  # CRÍTICO: rollback después del IntegrityError
        pass


def test_get_or_create_draft_bloquea_si_existe_in_review(session, test_document):
    """Test: get_or_create_draft bloquea si existe IN_REVIEW."""
    # FLUJO CORRECTO: crear DRAFT, enviar a IN_REVIEW, luego intentar crear otro DRAFT
    # Crear versión DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar a revisión
    updated_version, validation = submit_version_for_review(session, draft.id)
    assert updated_version.version_status == "IN_REVIEW"
    
    # Intentar crear DRAFT debe fallar
    with pytest.raises(ValueError, match="tiene una versión IN_REVIEW"):
        get_or_create_draft(
            session=session,
            document_id=test_document.id,
        )


def test_enforce_db_previene_dos_drafts(session, test_document):
    """Test: Enforce DB previene insertar dos DRAFT para el mismo documento.
    
    NOTA: Este test verifica que el índice único parcial funciona a nivel DB.
    Si SQLite no soporta índices parciales correctamente, el test puede fallar
    pero el enforce a nivel código (en get_or_create_draft) sigue funcionando.
    """
    import uuid
    from sqlalchemy import text
    
    # Verificar si el índice existe
    result = session.execute(text("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='uq_document_one_draft'
    """))
    index_exists = result.fetchone() is not None
    
    if not index_exists:
        pytest.skip("Índice único parcial uq_document_one_draft no existe. Ejecuta tools/reset_db_versions.py")
    
    unique_id1 = str(uuid.uuid4())[:8]
    unique_id2 = str(uuid.uuid4())[:8]
    # Crear primer DRAFT
    draft1 = DocumentVersion(
        id=f"draft-1-{unique_id1}",
        document_id=test_document.id,
        version_number=1,
        version_status="DRAFT",
        content_type="manual_edit",
        content_json='{"name": "Draft 1"}',
        content_markdown="# Draft 1",
    )
    session.add(draft1)
    session.commit()
    
    # Intentar crear segundo DRAFT (debe fallar por enforce DB)
    draft2 = DocumentVersion(
        id=f"draft-2-{unique_id2}",
        document_id=test_document.id,
        version_number=2,
        version_status="DRAFT",
        content_type="manual_edit",
        content_json='{"name": "Draft 2"}',
        content_markdown="# Draft 2",
    )
    session.add(draft2)
    
    # Capturar IntegrityError y hacer rollback
    with pytest.raises(IntegrityError):
        session.commit()
    
    # CRÍTICO: Hacer rollback después del IntegrityError para limpiar la sesión
    session.rollback()
    
    # Verificar que solo existe el primer DRAFT
    drafts = session.query(DocumentVersion).filter_by(
        document_id=test_document.id,
        version_status="DRAFT"
    ).all()
    assert len(drafts) == 1
    assert drafts[0].id == draft1.id
    assert drafts[0].version_number == 1


def test_enforce_db_previene_dos_in_review(session, test_document):
    """Test: Enforce DB previene insertar dos IN_REVIEW para el mismo documento.
    
    NOTA: Este test verifica que el índice único parcial funciona a nivel DB.
    Si SQLite no soporta índices parciales correctamente, el test puede fallar
    pero el enforce a nivel código (en submit_version_for_review) sigue funcionando.
    """
    import uuid
    from sqlalchemy import text
    
    # Verificar si el índice existe
    result = session.execute(text("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='uq_document_one_in_review'
    """))
    index_exists = result.fetchone() is not None
    
    if not index_exists:
        pytest.skip("Índice único parcial uq_document_one_in_review no existe. Ejecuta tools/reset_db_versions.py")
    
    unique_id1 = str(uuid.uuid4())[:8]
    unique_id2 = str(uuid.uuid4())[:8]
    # Crear primer IN_REVIEW
    validation1 = Validation(
        id=f"validation-1-{unique_id1}",
        document_id=test_document.id,
        status="pending",
    )
    session.add(validation1)
    
    in_review1 = DocumentVersion(
        id=f"in-review-1-{unique_id1}",
        document_id=test_document.id,
        version_number=1,
        version_status="IN_REVIEW",
        content_type="generated",
        content_json='{"name": "In Review 1"}',
        content_markdown="# In Review 1",
        validation_id=validation1.id,
    )
    session.add(in_review1)
    session.commit()
    
    # Intentar crear segundo IN_REVIEW (debe fallar por enforce DB)
    validation2 = Validation(
        id=f"validation-2-{unique_id2}",
        document_id=test_document.id,
        status="pending",
    )
    session.add(validation2)
    
    in_review2 = DocumentVersion(
        id=f"in-review-2-{unique_id2}",
        document_id=test_document.id,
        version_number=2,
        version_status="IN_REVIEW",
        content_type="generated",
        content_json='{"name": "In Review 2"}',
        content_markdown="# In Review 2",
        validation_id=validation2.id,
    )
    session.add(in_review2)
    
    # Capturar IntegrityError y hacer rollback
    with pytest.raises(IntegrityError):
        session.commit()
    
    # CRÍTICO: Hacer rollback después del IntegrityError para limpiar la sesión
    session.rollback()
    
    # Verificar que solo existe el primer IN_REVIEW
    in_reviews = session.query(DocumentVersion).filter_by(
        document_id=test_document.id,
        version_status="IN_REVIEW"
    ).all()
    assert len(in_reviews) == 1
    assert in_reviews[0].id == in_review1.id
    assert in_reviews[0].version_number == 1


def test_reject_version_permite_crear_draft(session, test_document):
    """Test: Rechazar versión permite crear DRAFT desde ella."""
    # Crear versión DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar a revisión
    updated_version, validation = submit_version_for_review(session, draft.id)
    
    # Rechazar
    rejected = reject_version(session, validation.id, observations="Necesita correcciones")
    
    # Commit para que los cambios se reflejen en la DB
    session.commit()
    
    # Refresh para obtener los valores actualizados
    session.refresh(rejected)
    session.refresh(validation)
    session.refresh(test_document)
    
    assert rejected.version_status == "REJECTED"
    assert rejected.rejected_at is not None
    assert validation.status == "rejected"
    assert test_document.status == "rejected"
    
    # Ahora se puede crear DRAFT desde REJECTED
    new_draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
        source_version_id=rejected.id,
    )
    assert new_draft.supersedes_version_id == rejected.id
    assert new_draft.version_status == "DRAFT"


def test_approve_version_sets_current_and_obsoletes_previous(session, test_document, approved_version):
    """Test: approve_version marca APPROVED, setea current y obsoleta la anterior."""
    # Crear nueva versión DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar a revisión
    updated_version, validation = submit_version_for_review(session, draft.id)
    
    # Aprobar
    approved = approve_version(session, validation.id)
    
    # Commit para que los cambios se reflejen en la DB
    session.commit()
    
    # Refresh para obtener los valores actualizados
    session.refresh(approved)
    session.refresh(approved_version)
    session.refresh(test_document)
    
    assert approved.version_status == "APPROVED"
    assert approved.is_current is True
    assert approved.approved_at is not None
    
    # Verificar que la anterior está obsoleta
    assert approved_version.version_status == "OBSOLETE"
    assert approved_version.is_current is False
    
    # Verificar documento
    assert test_document.approved_version_id == approved.id
    assert test_document.status == "approved"


def test_in_review_bloquea_edicion(session, test_document):
    """Test: IN_REVIEW bloquea edición incluso si hay APPROVED vigente."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    # Crear APPROVED vigente
    approved = DocumentVersion(
        id=f"test-approved-{unique_id}",
        document_id=test_document.id,
        version_number=1,
        version_status="APPROVED",
        content_type="generated",
        content_json='{"name": "Test"}',
        content_markdown="# Test",
        is_current=True,
    )
    session.add(approved)
    session.commit()
    
    # Crear DRAFT
    draft = get_or_create_draft(
        session=session,
        document_id=test_document.id,
    )
    
    # Enviar a revisión
    updated_version, validation = submit_version_for_review(session, draft.id)
    
    # Verificar que bloquea edición
    is_immutable, reason = check_version_immutable(session, test_document.id)
    assert is_immutable is True
    assert "IN_REVIEW" in reason
    
    # Verificar que get_or_create_draft también bloquea
    with pytest.raises(ValueError, match="tiene una versión IN_REVIEW"):
        get_or_create_draft(
            session=session,
            document_id=test_document.id,
        )
