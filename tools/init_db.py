from process_ai_core.db.database import Base, get_db_engine

# Importante: registrar modelos ANTES de create_all
from process_ai_core.db.models import Client, Process, Run, Artifact  # noqa: F401
from process_ai_core.db.models_catalog import CatalogOption  # noqa: F401


def main():
    engine = get_db_engine(echo=False)
    Base.metadata.create_all(bind=engine)
    print("✅ DB creada/verificada usando DATABASE_URL.")


if __name__ == "__main__":
    main()