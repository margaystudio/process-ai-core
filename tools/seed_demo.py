# tools/seed_demo.py
from __future__ import annotations

from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace, Process
from process_ai_core.db.helpers import create_organization_workspace


def main():
    with get_db_session() as db:
        # 1) Workspace (empresa / tenant) - reemplaza Client
        slug = "demo"
        workspace = db.query(Workspace).filter(Workspace.slug == slug).first()

        if not workspace:
            workspace = create_organization_workspace(
                session=db,
                name="Cliente Demo",
                slug=slug,
                country="UY",
                business_type="estaciones_servicio",
                language_style="es_uy_formal",
                default_audience="operativo",
                context_text=(
                    "Rubro: estaciones de servicio.\n"
                    "Objetivo de documentos: operativos, entendibles por personal de pista.\n"
                    "Restricción: documentos cortos (ideal 1–2 páginas).\n"
                    "Tono: español uruguayo formal, claro y directo.\n"
                ),
            )
            db.commit()
            db.refresh(workspace)

        # Obtener carpeta raíz del workspace (se crea automáticamente)
        from process_ai_core.db.models import Folder
        root_folder = (
            db.query(Folder)
            .filter(Folder.workspace_id == workspace.id, Folder.parent_id.is_(None))
            .first()
        )
        
        if not root_folder:
            # Si no existe, crear carpeta raíz
            from process_ai_core.db.helpers import create_folder
            root_folder = create_folder(
                session=db,
                workspace_id=workspace.id,
                name=workspace.name,
                path=workspace.name,
                parent_id=None,
                sort_order=0,
            )
            db.commit()
            db.refresh(root_folder)

        # 2) Process (uno dentro del workspace)
        proc_name = "Atender cliente en pista"
        process = (
            db.query(Process)
            .filter(Process.workspace_id == workspace.id, Process.name == proc_name)
            .first()
        )

        if not process:
            process = Process(
                workspace_id=workspace.id,
                folder_id=root_folder.id,  # Asignar carpeta raíz
                document_type="process",
                name=proc_name,
                status="draft",
                description="Atención al cliente en pista: saludo, carga, cobro y cierre.",
                audience="operativo",
                detail_level="breve",
                context_text=(
                    "Proceso en pista. Prioridad: seguridad, claridad y secuencia.\n"
                    "Evitar textos largos y tecnicismos.\n"
                ),
            )
            db.add(process)
            db.commit()
            db.refresh(process)

        print("✅ Workspace:", workspace.id, workspace.slug, workspace.name)
        print("✅ Process:", process.id, process.name)


if __name__ == "__main__":
    main()