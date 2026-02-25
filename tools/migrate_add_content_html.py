"""
Migración: Agregar campo content_html a document_versions.

Usado para persistir el HTML del editor WYSIWYG (Tiptap) en edición manual.
NULL para versiones existentes; se genera desde content_markdown al abrir el editor.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from process_ai_core.db.database import get_db_session, get_db_engine


def migrate():
    """Agrega la columna content_html a document_versions."""
    engine = get_db_engine()

    with get_db_session() as session:
        print("=" * 70)
        print("  MIGRACIÓN: Agregar campo content_html a document_versions")
        print("=" * 70)
        print()

        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("document_versions")]

        if "content_html" in columns:
            print("✅ La columna content_html ya existe. Migración ya aplicada.")
            return

        print("🔨 Agregando columna content_html (TEXT NULL)...")
        session.execute(text("""
            ALTER TABLE document_versions
            ADD COLUMN content_html TEXT NULL
        """))
        session.commit()
        print("✅ Migración completada.")


if __name__ == "__main__":
    migrate()
