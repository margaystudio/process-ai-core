#!/usr/bin/env python3
"""
Script para limpiar documentos inconsistentes (sin runs o con runs sin artifacts).

Uso:
    python tools/cleanup_inconsistent_documents.py          # Pide confirmación
    python tools/cleanup_inconsistent_documents.py --yes   # Ejecuta sin confirmación
"""
import sys

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Document, Process, Recipe, Run, Artifact
from pathlib import Path
import shutil
from process_ai_core.config import get_settings


def cleanup_inconsistent_documents(skip_confirmation: bool = False):
    """
    Elimina documentos que no tienen runs o tienen runs sin artifacts.
    
    Args:
        skip_confirmation: Si True, no pide confirmación antes de eliminar.
    """
    print("🧹 Buscando documentos inconsistentes...")
    
    with get_db_session() as session:
        all_docs = session.query(Document).all()
        inconsistent = []
        
        for doc in all_docs:
            runs = session.query(Run).filter_by(document_id=doc.id).all()
            
            # Documento sin runs = inconsistente
            if len(runs) == 0:
                inconsistent.append((doc, "sin runs"))
                continue
            
            # Verificar si todos los runs tienen artifacts
            all_runs_have_artifacts = True
            for run in runs:
                artifacts = session.query(Artifact).filter_by(run_id=run.id).all()
                if len(artifacts) == 0:
                    all_runs_have_artifacts = False
                    break
            
            if not all_runs_have_artifacts:
                inconsistent.append((doc, "runs sin artifacts"))
        
        if not inconsistent:
            print("✅ No se encontraron documentos inconsistentes.")
            return
        
        print(f"\n⚠️  Se encontraron {len(inconsistent)} documentos inconsistentes:")
        for doc, reason in inconsistent:
            print(f"  - {doc.id[:8]}... | {doc.name} | Razón: {reason}")
        
        if not skip_confirmation:
            response = input("\n¿Eliminar estos documentos? (escribe 'SI' para confirmar): ")
            if response != 'SI':
                print("❌ Operación cancelada.")
                return
        else:
            print("\n⚡ Ejecutando sin confirmación (--yes)...")
        
        print("\n🗑️  Eliminando documentos inconsistentes...")
        
        deleted_docs = 0
        deleted_runs = 0
        deleted_artifacts = 0
        deleted_dirs = 0
        
        for doc, reason in inconsistent:
            # Obtener runs del documento
            runs = session.query(Run).filter_by(document_id=doc.id).all()
            
            # Eliminar artifacts y directorios de runs
            for run in runs:
                artifacts = session.query(Artifact).filter_by(run_id=run.id).all()
                for artifact in artifacts:
                    session.delete(artifact)
                    deleted_artifacts += 1
                
                # Eliminar directorio del run
                settings = get_settings()
                run_dir = Path(settings.output_dir) / run.id
                if run_dir.exists():
                    try:
                        shutil.rmtree(run_dir)
                        deleted_dirs += 1
                    except Exception as e:
                        print(f"   ⚠️  No se pudo eliminar directorio {run_dir}: {e}")
                
                session.delete(run)
                deleted_runs += 1
            
            # Eliminar Process o Recipe si existe
            if doc.domain == "process":
                process = session.query(Process).filter_by(id=doc.id).first()
                if process:
                    session.delete(process)
            elif doc.domain == "recipe":
                recipe = session.query(Recipe).filter_by(id=doc.id).first()
                if recipe:
                    session.delete(recipe)
            
            # Eliminar Document
            session.delete(doc)
            deleted_docs += 1
        
        session.commit()
        
        print(f"\n✅ Limpieza completada:")
        print(f"   - Documentos eliminados: {deleted_docs}")
        print(f"   - Runs eliminados: {deleted_runs}")
        print(f"   - Artifacts eliminados: {deleted_artifacts}")
        print(f"   - Directorios eliminados: {deleted_dirs}")


if __name__ == "__main__":
    skip_confirmation = "--yes" in sys.argv or "-y" in sys.argv
    
    try:
        cleanup_inconsistent_documents(skip_confirmation=skip_confirmation)
    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

