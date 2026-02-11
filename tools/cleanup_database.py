#!/usr/bin/env python3
"""
Script para limpiar la base de datos, eliminando todos los documentos generados
y sus datos relacionados (runs, artifacts, validations, versions, audit logs).

Mantiene:
- Workspaces (clientes)
- Folders (carpetas raíz de workspaces)
- CatalogOptions (opciones del catálogo)
- Estructura de tablas

IMPORTANTE: Este script elimina TODOS los datos de documentos.
Úsalo solo en desarrollo o cuando quieras empezar desde cero.

Uso:
    python tools/cleanup_database.py          # Pide confirmación
    python tools/cleanup_database.py --yes    # Ejecuta sin confirmación
"""
import sys

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import (
    Document,
    Process,
    Recipe,
    Run,
    Artifact,
    Validation,
    DocumentVersion,
    AuditLog,
    Folder,
    Workspace,
)
from process_ai_core.config import get_settings
from pathlib import Path
import shutil


def cleanup_database(skip_confirmation: bool = False):
    """
    Elimina todos los documentos y sus datos relacionados.
    
    Args:
        skip_confirmation: Si True, no pide confirmación antes de eliminar.
    """
    print("🧹 Iniciando limpieza de base de datos...")
    
    with get_db_session() as session:
        # Contar registros antes de eliminar
        counts = {
            'documents': session.query(Document).count(),
            'runs': session.query(Run).count(),
            'artifacts': session.query(Artifact).count(),
            'validations': session.query(Validation).count(),
            'versions': session.query(DocumentVersion).count(),
            'audit_logs': session.query(AuditLog).count(),
        }
        
        print("\n📊 Registros a eliminar:")
        for entity, count in counts.items():
            print(f"  - {entity}: {count}")
        
        # Confirmar
        total = sum(counts.values())
        if total == 0:
            print("\n✅ La base de datos ya está limpia. No hay nada que eliminar.")
        else:
            print(f"\n⚠️  Se eliminarán {total} registros en total.")
            print("   Esto incluye:")
            print("   - Todos los documentos (procesos, recetas)")
            print("   - Todos los runs y artifacts")
            print("   - Todas las validaciones y versiones")
            print("   - Todo el historial de auditoría")
            print("\n   Se mantendrán:")
            print("   - Workspaces (clientes)")
            print("   - Folders (carpetas raíz)")
            print("   - CatalogOptions (opciones del catálogo)")
            
            if not skip_confirmation:
                response = input("\n¿Continuar? (escribe 'SI' para confirmar): ")
                if response != 'SI':
                    print("❌ Operación cancelada.")
                    return
            else:
                print("\n⚡ Ejecutando sin confirmación (--yes)...")
            
            print("\n🗑️  Eliminando registros...")
            
            # Orden de eliminación (respetando foreign keys)
            # 1. AuditLog (referencia a documents, runs, etc.)
            deleted_audit = session.query(AuditLog).delete()
            print(f"   ✓ AuditLog: {deleted_audit} registros eliminados")
            
            # 2. Anular approved_version_id en documents (FK a document_versions)
            updated_docs = session.query(Document).filter(Document.approved_version_id.isnot(None)).update(
                {Document.approved_version_id: None}, synchronize_session=False
            )
            if updated_docs:
                print(f"   ✓ Document.approved_version_id anulados: {updated_docs} documentos")
            
            # 3. Anular validation_id en DocumentVersion y Run (FK a validations) para poder borrar validations
            updated_versions_fk = session.query(DocumentVersion).filter(
                DocumentVersion.validation_id.isnot(None)
            ).update({DocumentVersion.validation_id: None}, synchronize_session=False)
            if updated_versions_fk:
                print(f"   ✓ DocumentVersion.validation_id anulados: {updated_versions_fk} versiones")
            updated_runs_fk = session.query(Run).filter(Run.validation_id.isnot(None)).update(
                {Run.validation_id: None}, synchronize_session=False
            )
            if updated_runs_fk:
                print(f"   ✓ Run.validation_id anulados: {updated_runs_fk} runs")
            
            # 4. Validation (referencia a documents, runs; ya nadie la referencia)
            deleted_validations = session.query(Validation).delete()
            print(f"   ✓ Validation: {deleted_validations} registros eliminados")
            
            # 5. DocumentVersion (referencia a documents, runs)
            deleted_versions = session.query(DocumentVersion).delete()
            print(f"   ✓ DocumentVersion: {deleted_versions} registros eliminados")
            
            # 6. Artifact (referencia a runs)
            deleted_artifacts = session.query(Artifact).delete()
            print(f"   ✓ Artifact: {deleted_artifacts} registros eliminados")
            
            # 7. Run (referencia a documents)
            deleted_runs = session.query(Run).delete()
            print(f"   ✓ Run: {deleted_runs} registros eliminados")
            
            # 8. Process y Recipe (tablas hijas de Document)
            deleted_processes = session.query(Process).delete()
            print(f"   ✓ Process: {deleted_processes} registros eliminados")
            
            deleted_recipes = session.query(Recipe).delete()
            print(f"   ✓ Recipe: {deleted_recipes} registros eliminados")
            
            # 9. Document (tabla base)
            deleted_documents = session.query(Document).delete()
            print(f"   ✓ Document: {deleted_documents} registros eliminados")
            
            # 10. Folders (excepto root folders)
            # Los root folders tienen parent_id = None y son creados automáticamente
            # Eliminamos solo las carpetas que no son raíz
            deleted_folders = session.query(Folder).filter(Folder.parent_id.isnot(None)).delete()
            print(f"   ✓ Folder (no raíz): {deleted_folders} registros eliminados")
            
            # Commit
            session.commit()
            
            print("\n✅ Limpieza de base de datos completada!")
    
    # Limpiar archivos físicos en output/ (fuera del contexto de sesión)
    print("\n🗑️  Limpiando archivos físicos en output/...")
    settings = get_settings()
    output_dir = Path(settings.output_dir)
    
    if output_dir.exists():
        deleted_dirs = 0
        deleted_files = 0
        
        # Eliminar todos los directorios de runs (UUIDs)
        for item in output_dir.iterdir():
            if item.is_dir():
                # Verificar que sea un UUID (formato típico de run_id)
                try:
                    # Intentar parsear como UUID
                    import uuid
                    uuid.UUID(item.name)
                    # Es un directorio de run, eliminarlo
                    shutil.rmtree(item)
                    deleted_dirs += 1
                except (ValueError, AttributeError):
                    # No es un UUID, probablemente es un archivo o directorio especial
                    # Lo dejamos intacto
                    pass
            elif item.is_file() and item.name != '.gitkeep':
                # Eliminar archivos sueltos (excepto .gitkeep)
                item.unlink()
                deleted_files += 1
        
        print(f"   ✓ Directorios eliminados: {deleted_dirs}")
        print(f"   ✓ Archivos eliminados: {deleted_files}")
    else:
        print("   ℹ️  Directorio output/ no existe, nada que limpiar.")
    
    # Verificar estado final (necesitamos nueva sesión)
    with get_db_session() as session:
        
        # Verificar
        remaining = {
            'documents': session.query(Document).count(),
            'runs': session.query(Run).count(),
            'artifacts': session.query(Artifact).count(),
            'validations': session.query(Validation).count(),
            'versions': session.query(DocumentVersion).count(),
            'audit_logs': session.query(AuditLog).count(),
            'workspaces': session.query(Workspace).count(),
            'folders': session.query(Folder).count(),
        }
        
        print("\n📊 Estado final de la base de datos:")
        for entity, count in remaining.items():
            print(f"  - {entity}: {count}")
        
        print("\n✅ Limpieza completa finalizada!")


if __name__ == "__main__":
    skip_confirmation = "--yes" in sys.argv or "-y" in sys.argv
    
    try:
        cleanup_database(skip_confirmation=skip_confirmation)
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

