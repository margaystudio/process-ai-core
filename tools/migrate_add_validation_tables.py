#!/usr/bin/env python3
"""
Migración: Agregar tablas de validación, auditoría y versiones de documentos.

Crea las siguientes tablas:
- validations: Validaciones realizadas sobre documentos/runs
- audit_logs: Registro de auditoría de todas las acciones
- document_versions: Versiones aprobadas de documentos

También extiende:
- documents: Agrega approved_version_id y extiende status
- runs: Agrega validation_id e is_approved
"""

import sqlite3
from pathlib import Path
import sys

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from process_ai_core.db.database import get_db_engine


def migrate():
    """Ejecuta la migración."""
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # Verificar si las tablas ya existen
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Crear tabla validations
        if "validations" not in existing_tables:
            print("Creando tabla validations...")
            conn.execute(text("""
                CREATE TABLE validations (
                    id VARCHAR(36) PRIMARY KEY,
                    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
                    run_id VARCHAR(36) REFERENCES runs(id),
                    validator_user_id VARCHAR(36) REFERENCES users(id),
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    observations TEXT DEFAULT '',
                    checklist_json TEXT DEFAULT '{}',
                    created_at DATETIME NOT NULL,
                    completed_at DATETIME
                )
            """))
            conn.execute(text("CREATE INDEX idx_validations_document_id ON validations(document_id)"))
            conn.execute(text("CREATE INDEX idx_validations_run_id ON validations(run_id)"))
            conn.execute(text("CREATE INDEX idx_validations_validator_user_id ON validations(validator_user_id)"))
            print("✅ Tabla validations creada")
        else:
            print("⚠️  Tabla validations ya existe, omitiendo...")
        
        # Crear tabla audit_logs
        if "audit_logs" not in existing_tables:
            print("Creando tabla audit_logs...")
            conn.execute(text("""
                CREATE TABLE audit_logs (
                    id VARCHAR(36) PRIMARY KEY,
                    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
                    run_id VARCHAR(36) REFERENCES runs(id),
                    user_id VARCHAR(36) REFERENCES users(id),
                    action VARCHAR(50) NOT NULL,
                    entity_type VARCHAR(20),
                    entity_id VARCHAR(36),
                    changes_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    created_at DATETIME NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX idx_audit_logs_document_id ON audit_logs(document_id)"))
            conn.execute(text("CREATE INDEX idx_audit_logs_run_id ON audit_logs(run_id)"))
            conn.execute(text("CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id)"))
            conn.execute(text("CREATE INDEX idx_audit_logs_action ON audit_logs(action)"))
            print("✅ Tabla audit_logs creada")
        else:
            print("⚠️  Tabla audit_logs ya existe, omitiendo...")
        
        # Crear tabla document_versions
        if "document_versions" not in existing_tables:
            print("Creando tabla document_versions...")
            conn.execute(text("""
                CREATE TABLE document_versions (
                    id VARCHAR(36) PRIMARY KEY,
                    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
                    run_id VARCHAR(36) REFERENCES runs(id),
                    version_number INTEGER NOT NULL,
                    content_type VARCHAR(20) NOT NULL,
                    content_json TEXT NOT NULL,
                    content_markdown TEXT NOT NULL,
                    approved_at DATETIME NOT NULL,
                    approved_by VARCHAR(36) REFERENCES users(id),
                    validation_id VARCHAR(36) REFERENCES validations(id),
                    is_current BOOLEAN DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX idx_document_versions_document_id ON document_versions(document_id)"))
            conn.execute(text("CREATE INDEX idx_document_versions_run_id ON document_versions(run_id)"))
            conn.execute(text("CREATE INDEX idx_document_versions_is_current ON document_versions(is_current)"))
            print("✅ Tabla document_versions creada")
        else:
            print("⚠️  Tabla document_versions ya existe, omitiendo...")
        
        # Extender tabla documents
        print("Extendiendo tabla documents...")
        try:
            # Verificar si approved_version_id ya existe
            if 'documents' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('documents')]
            else:
                columns = []
            
            if 'approved_version_id' not in columns:
                conn.execute(text("ALTER TABLE documents ADD COLUMN approved_version_id VARCHAR(36) REFERENCES document_versions(id)"))
                conn.execute(text("CREATE INDEX idx_documents_approved_version_id ON documents(approved_version_id)"))
                print("✅ Columna approved_version_id agregada a documents")
            else:
                print("⚠️  Columna approved_version_id ya existe en documents")
        except Exception as e:
            print(f"⚠️  Error al extender documents: {e}")
        
        # Extender tabla runs
        print("Extendiendo tabla runs...")
        try:
            if 'runs' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('runs')]
            else:
                columns = []
            
            if 'validation_id' not in columns:
                conn.execute(text("ALTER TABLE runs ADD COLUMN validation_id VARCHAR(36) REFERENCES validations(id)"))
                conn.execute(text("CREATE INDEX idx_runs_validation_id ON runs(validation_id)"))
                print("✅ Columna validation_id agregada a runs")
            else:
                print("⚠️  Columna validation_id ya existe en runs")
            
            if 'is_approved' not in columns:
                conn.execute(text("ALTER TABLE runs ADD COLUMN is_approved BOOLEAN DEFAULT 0"))
                conn.execute(text("CREATE INDEX idx_runs_is_approved ON runs(is_approved)"))
                print("✅ Columna is_approved agregada a runs")
            else:
                print("⚠️  Columna is_approved ya existe en runs")
        except Exception as e:
            print(f"⚠️  Error al extender runs: {e}")
        
        conn.commit()
        print("\n✅ Migración completada exitosamente")


if __name__ == "__main__":
    migrate()

