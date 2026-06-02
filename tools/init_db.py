from sqlalchemy import text

from process_ai_core.db.database import Base, DATABASE_SCHEMA, get_db_engine

# Importante: registrar modelos ANTES de create_all
from process_ai_core.db.models import Workspace, Document, Process, Recipe, Run, Artifact, Folder, User, WorkspaceMembership  # noqa: F401
from process_ai_core.db.models_catalog import CatalogOption  # noqa: F401


def ensure_schema(engine) -> None:
    if not DATABASE_SCHEMA:
        return
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{DATABASE_SCHEMA}"'))


def main():
    engine = get_db_engine(echo=False)
    ensure_schema(engine)
    Base.metadata.create_all(bind=engine)
    target = DATABASE_SCHEMA or "default"
    print(f"✅ DB creada/verificada en schema '{target}' (DATABASE_URL).")


if __name__ == "__main__":
    main()
