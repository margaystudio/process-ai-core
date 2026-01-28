#!/usr/bin/env python3
"""
Script para resetear/recrear la tabla document_versions con enforce real.

Este script:
- Dropea la tabla document_versions si existe
- La recrea con el schema completo
- Crea índices únicos parciales para enforce "1 solo DRAFT" y "1 solo IN_REVIEW"

USO:
    python tools/reset_db_versions.py

ADVERTENCIA: Este script borra todos los datos de document_versions.

NOTA: Foreign keys se activan automáticamente en database.py mediante event listener.
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine


def reset_document_versions():
    """Resetea la tabla document_versions con schema completo y enforce real."""
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # Foreign keys ya están activadas automáticamente por el event listener en database.py
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Dropear tabla si existe (en orden correcto para FK)
        if "document_versions" in existing_tables:
            print("🗑️  Dropeando tabla document_versions existente...")
            # Desactivar temporalmente foreign keys para poder dropear
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            # Primero dropear índices que puedan tener FK
            try:
                conn.execute(text("DROP INDEX IF EXISTS uq_document_one_draft"))
            except Exception:
                pass
            try:
                conn.execute(text("DROP INDEX IF EXISTS uq_document_one_in_review"))
            except Exception:
                pass
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_document_versions_doc_status"))
            except Exception:
                pass
            
            conn.execute(text("DROP TABLE IF EXISTS document_versions"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
            print("✅ Tabla document_versions dropeada")
        
        # Crear tabla con schema completo
        print("🔨 Creando tabla document_versions con schema completo...")
        conn.execute(text("""
            CREATE TABLE document_versions (
                id VARCHAR(36) PRIMARY KEY,
                document_id VARCHAR(36) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                run_id VARCHAR(36) REFERENCES runs(id) ON DELETE SET NULL,
                version_number INTEGER NOT NULL,
                version_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
                supersedes_version_id VARCHAR(36) REFERENCES document_versions(id) ON DELETE SET NULL,
                content_type VARCHAR(20) NOT NULL,
                content_json TEXT NOT NULL,
                content_markdown TEXT NOT NULL,
                approved_at DATETIME,
                approved_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
                validation_id VARCHAR(36) REFERENCES validations(id) ON DELETE SET NULL,
                rejected_at DATETIME,
                rejected_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
                is_current BOOLEAN DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Crear índices de performance
        print("📊 Creando índices de performance...")
        conn.execute(text("CREATE INDEX idx_document_versions_document_id ON document_versions(document_id)"))
        conn.execute(text("CREATE INDEX idx_document_versions_run_id ON document_versions(run_id)"))
        conn.execute(text("CREATE INDEX idx_document_versions_is_current ON document_versions(is_current)"))
        conn.execute(text("CREATE INDEX idx_document_versions_version_status ON document_versions(version_status)"))
        conn.execute(text("CREATE INDEX idx_document_versions_supersedes_version_id ON document_versions(supersedes_version_id)"))
        conn.execute(text("CREATE INDEX idx_document_versions_approved_by ON document_versions(approved_by)"))
        conn.execute(text("CREATE INDEX idx_document_versions_rejected_by ON document_versions(rejected_by)"))
        conn.execute(text("CREATE INDEX idx_document_versions_validation_id ON document_versions(validation_id)"))
        # Índice compuesto para performance
        conn.execute(text("CREATE INDEX idx_document_versions_doc_status ON document_versions(document_id, version_status)"))
        
        # Crear índices únicos parciales para enforce real
        print("🔒 Creando índices únicos parciales para enforce...")
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_document_one_draft
                ON document_versions(document_id)
                WHERE version_status = 'DRAFT'
            """))
            print("✅ Índice único parcial uq_document_one_draft creado")
        except Exception as e:
            print(f"⚠️  Error creando uq_document_one_draft: {e}")
            print("   Verifica que SQLite sea >= 3.8.0")
        
        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_document_one_in_review
                ON document_versions(document_id)
                WHERE version_status = 'IN_REVIEW'
            """))
            print("✅ Índice único parcial uq_document_one_in_review creado")
        except Exception as e:
            print(f"⚠️  Error creando uq_document_one_in_review: {e}")
            print("   Verifica que SQLite sea >= 3.8.0")
        
        conn.commit()
        print("\n✅ Tabla document_versions recreada exitosamente con enforce real")
        print("📝 Enforce activo:")
        print("   - 1 solo DRAFT por document_id")
        print("   - 1 solo IN_REVIEW por document_id")
        print("   - Foreign keys activadas automáticamente (ON DELETE CASCADE/SET NULL funcionando)")


if __name__ == "__main__":
    reset_document_versions()
