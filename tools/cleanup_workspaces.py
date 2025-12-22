"""
Script para limpiar workspaces y dejar solo "margay".

Elimina todos los workspaces excepto "margay", o crea "margay" si no existe.

Uso:
    python tools/cleanup_workspaces.py [--yes]
"""

import sys
import argparse
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace, Document, Folder, WorkspaceMembership
from process_ai_core.db.helpers import create_organization_workspace


def cleanup_workspaces(yes: bool = False):
    """Elimina todos los workspaces excepto 'margay'."""
    with get_db_session() as session:
        # Buscar workspace "margay"
        margay = session.query(Workspace).filter_by(slug="margay").first()
        
        # Obtener todos los workspaces
        all_workspaces = session.query(Workspace).all()
        
        print(f"📦 Encontrados {len(all_workspaces)} workspaces")
        
        # Contar documentos y carpetas por workspace
        workspaces_to_delete = []
        for ws in all_workspaces:
            if ws.slug == "margay":
                continue
            
            doc_count = session.query(Document).filter_by(workspace_id=ws.id).count()
            folder_count = session.query(Folder).filter_by(workspace_id=ws.id).count()
            membership_count = session.query(WorkspaceMembership).filter_by(workspace_id=ws.id).count()
            
            workspaces_to_delete.append({
                "workspace": ws,
                "documents": doc_count,
                "folders": folder_count,
                "memberships": membership_count,
            })
        
        if not workspaces_to_delete:
            print("✅ No hay workspaces para eliminar (solo existe 'margay')")
        else:
            print(f"\n🗑️  Workspaces a eliminar: {len(workspaces_to_delete)}")
            for item in workspaces_to_delete:
                ws = item["workspace"]
                print(f"  - {ws.name} (slug: {ws.slug})")
                print(f"    - Documentos: {item['documents']}")
                print(f"    - Carpetas: {item['folders']}")
                print(f"    - Memberships: {item['memberships']}")
            
            # Confirmar
            if not yes:
                print("\n⚠️  Esta acción eliminará permanentemente estos workspaces y todos sus datos asociados.")
                response = input("¿Continuar? (s/n): ").strip().lower()
                
                if response != "s":
                    print("❌ Cancelado.")
                    return
            
            # Eliminar workspaces
            print("\n🗑️  Eliminando workspaces...")
            for item in workspaces_to_delete:
                ws = item["workspace"]
                print(f"  Eliminando {ws.name}...")
                
                # Los documentos y carpetas se eliminarán en cascada por las relaciones
                # Pero eliminamos explícitamente para asegurar
                session.query(Document).filter_by(workspace_id=ws.id).delete()
                session.query(Folder).filter_by(workspace_id=ws.id).delete()
                session.query(WorkspaceMembership).filter_by(workspace_id=ws.id).delete()
                session.delete(ws)
            
            session.commit()
            print("✅ Workspaces eliminados.")
        
        # Verificar o crear "margay"
        if not margay:
            print("\n📦 Creando workspace 'margay'...")
            margay = create_organization_workspace(
                session=session,
                name="Margay",
                slug="margay",
                country="UY",
                business_type="",
                language_style="es_uy_formal",
                default_audience="operativo",
                context_text="",
            )
            session.commit()
            print(f"✅ Workspace 'margay' creado (ID: {margay.id})")
        else:
            print(f"\n✅ Workspace 'margay' ya existe (ID: {margay.id})")
        
        # Resumen final
        remaining = session.query(Workspace).count()
        print(f"\n📊 Resumen:")
        print(f"  - Workspaces restantes: {remaining}")
        print(f"  - Todos los workspaces:")
        for ws in session.query(Workspace).all():
            doc_count = session.query(Document).filter_by(workspace_id=ws.id).count()
            print(f"    - {ws.name} (slug: {ws.slug}) - {doc_count} documentos")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpiar workspaces y dejar solo 'margay'")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Ejecutar sin confirmación interactiva",
    )
    args = parser.parse_args()
    
    cleanup_workspaces(yes=args.yes)

