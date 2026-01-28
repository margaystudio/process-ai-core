#!/usr/bin/env python3
"""
Script funcional para probar el flujo completo de versionado ISO-friendly.

Este script demuestra:
1. Crear un documento de proceso
2. Crear una versión DRAFT
3. Editar el DRAFT
4. Enviar a revisión (IN_REVIEW)
5. Aprobar la versión
6. Crear un nuevo DRAFT desde la versión aprobada
7. Rechazar una versión y crear DRAFT desde rechazada

USO:
    python tools/test_versioning_flow.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace, Process, Folder, DocumentVersion, Validation
from process_ai_core.db.helpers import (
    create_organization_workspace,
    create_folder,
    get_or_create_draft,
    submit_version_for_review,
    approve_version,
    reject_version,
    check_version_immutable,
)


def print_section(title: str):
    """Imprime un separador de sección."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_version_info(version: DocumentVersion, label: str = "Versión"):
    """Imprime información de una versión."""
    print(f"\n{label}:")
    print(f"  ID: {version.id}")
    print(f"  Número: v{version.version_number}")
    print(f"  Estado: {version.version_status}")
    print(f"  Tipo: {version.content_type}")
    print(f"  Creada: {version.created_at}")
    if version.approved_at:
        print(f"  Aprobada: {version.approved_at}")
    if version.rejected_at:
        print(f"  Rechazada: {version.rejected_at}")
    if version.supersedes_version_id:
        print(f"  Reemplaza: {version.supersedes_version_id}")
    print(f"  Es actual: {version.is_current}")


def main():
    """Ejecuta el flujo completo de versionado."""
    print_section("PRUEBA FUNCIONAL: Flujo de Versionado ISO-friendly")
    
    with get_db_session() as session:
        # ====================================================================
        # PASO 1: Crear Workspace y Documento
        # ====================================================================
        print_section("PASO 1: Crear Workspace y Documento")
        
        workspace = create_organization_workspace(
            session=session,
            name="Test Versioning Flow",
            slug="test-versioning-flow",
            country="UY",
            default_audience="operativo",
        )
        session.commit()
        print(f"✅ Workspace creado: {workspace.name} (ID: {workspace.id})")
        
        # Obtener carpeta raíz (se crea automáticamente por create_organization_workspace)
        root_folder = session.query(Folder).filter_by(
            workspace_id=workspace.id,
            parent_id=None
        ).first()
        
        if not root_folder:
            # Si no existe, crearla manualmente
            root_folder = create_folder(
                session=session,
                workspace_id=workspace.id,
                name=workspace.name,
                path=workspace.name,
                parent_id=None,
            )
            session.commit()
        
        # Crear documento de proceso
        process = Process(
            workspace_id=workspace.id,
            folder_id=root_folder.id,
            document_type="process",
            name="Proceso de Prueba - Versionado",
            description="Documento para probar el flujo de versionado",
            status="draft",
            audience="operativo",
        )
        session.add(process)
        session.commit()
        print(f"✅ Documento creado: {process.name} (ID: {process.id})")
        
        # ====================================================================
        # PASO 2: Crear primera versión DRAFT
        # ====================================================================
        print_section("PASO 2: Crear primera versión DRAFT")
        
        draft1 = get_or_create_draft(
            session=session,
            document_id=process.id,
            source_version_id=None,  # Primera versión, no hay fuente
        )
        session.commit()
        print_version_info(draft1, "DRAFT 1 creada")
        print(f"  Contenido JSON: {draft1.content_json[:100]}...")
        
        # ====================================================================
        # PASO 3: Editar DRAFT
        # ====================================================================
        print_section("PASO 3: Editar DRAFT")
        
        # Verificar que se puede editar
        is_immutable, reason = check_version_immutable(session, process.id)
        if is_immutable:
            print(f"❌ ERROR: No se puede editar - {reason}")
            return
        print("✅ Documento es editable (no hay IN_REVIEW)")
        
        # Editar contenido
        draft1.content_json = '{"process_name": "Proceso Editado v1", "objetivo": "Objetivo editado"}'
        draft1.content_markdown = "# Proceso Editado v1\n\nObjetivo editado"
        draft1.content_type = "manual_edit"
        session.commit()
        print("✅ DRAFT editado exitosamente")
        print_version_info(draft1, "DRAFT 1 después de editar")
        
        # ====================================================================
        # PASO 4: Enviar a revisión (IN_REVIEW)
        # ====================================================================
        print_section("PASO 4: Enviar DRAFT a revisión")
        
        updated_version, validation = submit_version_for_review(
            session=session,
            version_id=draft1.id,
            submitter_id=None,  # En producción vendría del contexto de auth
        )
        session.commit()
        print_version_info(updated_version, "Versión enviada a revisión")
        print(f"✅ Validation creada: {validation.id} (status: {validation.status})")
        
        # Verificar que ahora es inmutable
        is_immutable, reason = check_version_immutable(session, process.id)
        if not is_immutable:
            print(f"⚠️  ADVERTENCIA: Debería ser inmutable - {reason}")
        else:
            print(f"✅ Documento ahora es inmutable: {reason}")
        
        # Intentar crear otro DRAFT (debe fallar)
        try:
            draft2_fail = get_or_create_draft(session=session, document_id=process.id)
            print("❌ ERROR: No debería poder crear DRAFT con IN_REVIEW existente")
        except ValueError as e:
            print(f"✅ Correctamente bloqueado: {e}")
        
        # ====================================================================
        # PASO 5: Aprobar versión
        # ====================================================================
        print_section("PASO 5: Aprobar versión")
        
        approved = approve_version(
            session=session,
            validation_id=validation.id,
            approver_id=None,  # En producción vendría del contexto de auth
        )
        session.commit()
        print_version_info(approved, "Versión aprobada")
        
        # Verificar documento
        session.refresh(process)
        print(f"✅ Documento status: {process.status}")
        print(f"✅ Documento approved_version_id: {process.approved_version_id}")
        
        # ====================================================================
        # PASO 6: Crear nuevo DRAFT desde versión aprobada
        # ====================================================================
        print_section("PASO 6: Crear nuevo DRAFT desde versión aprobada")
        
        # Verificar que ahora se puede editar (no hay IN_REVIEW)
        is_immutable, reason = check_version_immutable(session, process.id)
        if is_immutable:
            print(f"❌ ERROR: No debería ser inmutable - {reason}")
        else:
            print("✅ Documento es editable (no hay IN_REVIEW)")
        
        draft2 = get_or_create_draft(
            session=session,
            document_id=process.id,
            source_version_id=None,  # Usará APPROVED vigente automáticamente
        )
        session.commit()
        print_version_info(draft2, "DRAFT 2 creada desde APPROVED")
        print(f"  Reemplaza versión: {draft2.supersedes_version_id}")
        print(f"  Contenido clonado: {draft2.content_json[:100]}...")
        
        # ====================================================================
        # PASO 7: Flujo de rechazo
        # ====================================================================
        print_section("PASO 7: Flujo de rechazo (crear DRAFT, enviar, rechazar)")
        
        # Crear DRAFT 3
        draft3 = get_or_create_draft(
            session=session,
            document_id=process.id,
            source_version_id=None,
        )
        draft3.content_json = '{"process_name": "Proceso con errores", "objetivo": "Necesita correcciones"}'
        draft3.content_markdown = "# Proceso con errores\n\nNecesita correcciones"
        session.commit()
        print_version_info(draft3, "DRAFT 3 creada")
        
        # Enviar a revisión
        updated_version3, validation3 = submit_version_for_review(
            session=session,
            version_id=draft3.id,
        )
        session.commit()
        print(f"✅ DRAFT 3 enviada a revisión (validation: {validation3.id})")
        
        # Rechazar
        rejected = reject_version(
            session=session,
            validation_id=validation3.id,
            rejector_id=None,
            observations="Necesita correcciones en el objetivo",
        )
        session.commit()
        print_version_info(rejected, "Versión rechazada")
        print(f"  Observaciones: {validation3.observations}")
        
        # Crear DRAFT desde versión rechazada
        draft4 = get_or_create_draft(
            session=session,
            document_id=process.id,
            source_version_id=rejected.id,
        )
        session.commit()
        print_version_info(draft4, "DRAFT 4 creada desde REJECTED")
        print(f"  Reemplaza versión rechazada: {draft4.supersedes_version_id}")
        
        # ====================================================================
        # RESUMEN FINAL
        # ====================================================================
        print_section("RESUMEN FINAL")
        
        # Obtener todas las versiones del documento
        all_versions = session.query(DocumentVersion).filter_by(
            document_id=process.id
        ).order_by(DocumentVersion.version_number).all()
        
        print(f"\nTotal de versiones creadas: {len(all_versions)}")
        print("\nHistorial de versiones:")
        for v in all_versions:
            status_icon = {
                "DRAFT": "📝",
                "IN_REVIEW": "⏳",
                "APPROVED": "✅",
                "REJECTED": "❌",
                "OBSOLETE": "🗄️",
            }.get(v.version_status, "❓")
            current_marker = " ⭐ (current)" if v.is_current else ""
            print(f"  {status_icon} v{v.version_number}: {v.version_status}{current_marker}")
            if v.supersedes_version_id:
                supersedes = session.query(DocumentVersion).filter_by(id=v.supersedes_version_id).first()
                if supersedes:
                    print(f"      └─ Reemplaza v{supersedes.version_number} ({supersedes.version_status})")
        
        print("\n✅ Flujo de versionado completado exitosamente!")
        print(f"\n📊 Workspace: {workspace.name} (ID: {workspace.id})")
        print(f"📄 Documento: {process.name} (ID: {process.id})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
