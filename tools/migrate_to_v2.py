"""
Script de migración de modelos v1 (Client/Process) a v2 (Workspace/Document).

Este script:
1. Crea las nuevas tablas (workspaces, documents, users, workspace_memberships, runs_v2, artifacts_v2)
2. Migra datos de Client → Workspace
3. Migra datos de Process → Document
4. Mantiene compatibilidad temporal (no elimina tablas viejas)
"""

from __future__ import annotations

import json
from pathlib import Path

from process_ai_core.db.database import Base, get_db_engine, get_db_session
from process_ai_core.db.models import Client, Process, Run, Artifact
from process_ai_core.db.models_v2 import (
    Workspace,
    Document,
    User,
    WorkspaceMembership,
    RunV2,
    ArtifactV2,
)


def migrate_clients_to_workspaces(session):
    """
    Migra Client → Workspace.
    """
    clients = session.query(Client).all()
    print(f"📦 Migrando {len(clients)} clientes a workspaces...")

    for client in clients:
        # Construir metadata_json desde los campos del Client
        metadata = {
            "country": client.country,
            "business_type": client.business_type,
            "language_style": client.language_style,
            "default_audience": client.default_audience,
            "default_formality": client.default_formality,
            "default_detail_level": client.default_detail_level,
            "context_text": client.context_text,
        }
        # Incluir prefs_json si tiene contenido
        if client.prefs_json and client.prefs_json != "{}":
            try:
                prefs = json.loads(client.prefs_json)
                metadata.update(prefs)
            except:
                pass

        workspace = Workspace(
            id=client.id,  # Mantener el mismo ID para referencias
            slug=client.slug,
            name=client.name,
            workspace_type="organization",
            metadata_json=json.dumps(metadata),
            created_at=client.created_at,
        )
        session.add(workspace)
        print(f"  ✅ {client.name} → Workspace (organization)")

    session.commit()
    print(f"✅ Migrados {len(clients)} workspaces\n")


def migrate_processes_to_documents(session):
    """
    Migra Process → Document.
    """
    processes = session.query(Process).all()
    print(f"📦 Migrando {len(processes)} procesos a documents...")

    for process in processes:
        # Construir domain_metadata_json desde los campos del Process
        metadata = {
            "process_type": process.process_type,
            "audience": process.audience,
            "formality": process.formality,
            "detail_level": process.detail_level,
            "context_text": process.context_text,
        }
        # Incluir preferences_json si tiene contenido
        if process.preferences_json and process.preferences_json != "{}":
            try:
                prefs = json.loads(process.preferences_json)
                metadata.update(prefs)
            except:
                pass

        document = Document(
            id=process.id,  # Mantener el mismo ID
            workspace_id=process.client_id,  # Client → Workspace
            domain="process",
            name=process.name,
            description=process.description,
            status=process.status,
            domain_metadata_json=json.dumps(metadata),
            created_at=process.created_at,
        )
        session.add(document)
        print(f"  ✅ {process.name} → Document (process)")

    session.commit()
    print(f"✅ Migrados {len(processes)} documents\n")


def migrate_runs_to_runs_v2(session):
    """
    Migra Run → RunV2.
    """
    runs = session.query(Run).all()
    print(f"📦 Migrando {len(runs)} runs a runs_v2...")

    for run in runs:
        # Obtener el documento asociado (que fue migrado desde Process)
        document = session.query(Document).filter_by(id=run.process_id).first()
        if not document:
            print(f"  ⚠️  Run {run.id} sin documento asociado, saltando...")
            continue

        run_v2 = RunV2(
            id=run.id,  # Mantener el mismo ID
            document_id=document.id,
            domain="process",  # Todos los runs actuales son de procesos
            profile=run.mode,  # mode → profile
            input_manifest_json=run.input_manifest_json,
            prompt_hash=run.prompt_hash,
            model_text=run.model_text,
            model_transcribe=run.model_transcribe,
            created_at=run.created_at,
        )
        session.add(run_v2)

        # Migrar artifacts
        for artifact in run.artifacts:
            artifact_v2 = ArtifactV2(
                id=artifact.id,
                run_id=run_v2.id,
                type=artifact.type,
                path=artifact.path,
                created_at=artifact.created_at,
            )
            session.add(artifact_v2)

        print(f"  ✅ Run {run.id} → RunV2 + {len(run.artifacts)} artifacts")

    session.commit()
    print(f"✅ Migrados {len(runs)} runs_v2\n")


def create_tables():
    """
    Crea las nuevas tablas en la base de datos.
    """
    engine = get_db_engine(echo=False)
    print("📋 Creando tablas v2...")
    # Importar todos los modelos v2 para que se registren en Base.metadata
    from process_ai_core.db import models_v2  # noqa: F401
    Base.metadata.create_all(engine)
    print("✅ Tablas v2 creadas\n")


def main():
    """
    Ejecuta la migración completa.
    """
    print("🚀 Iniciando migración a modelos v2...\n")

    # Crear tablas
    create_tables()

    # Migrar datos
    with get_db_session() as session:
        try:
            migrate_clients_to_workspaces(session)
            migrate_processes_to_documents(session)
            migrate_runs_to_runs_v2(session)
            print("✅ Migración completada exitosamente!")
        except Exception as e:
            print(f"❌ Error durante la migración: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    main()

