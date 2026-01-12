#!/usr/bin/env python3
"""
Migración: Agregar tablas de suscripciones e invitaciones.

Crea las siguientes tablas:
- subscription_plans: Planes de suscripción disponibles
- workspace_subscriptions: Suscripciones activas de workspaces
- workspace_invitations: Invitaciones para unirse a workspaces (B2B)

Ejecutar:
    python tools/migrate_add_subscription_tables.py
"""

from sqlalchemy import text
from process_ai_core.db.database import get_db_session


def migrate():
    """Ejecuta la migración."""
    with get_db_session() as session:
        try:
            # 1. Crear tabla subscription_plans
            print("Creando tabla 'subscription_plans'...")
            session.execute(text("""
            CREATE TABLE IF NOT EXISTS subscription_plans (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT DEFAULT '',
                plan_type VARCHAR(20) NOT NULL,
                price_monthly REAL DEFAULT 0.0,
                price_yearly REAL DEFAULT 0.0,
                max_users INTEGER,
                max_documents INTEGER,
                max_documents_per_month INTEGER,
                max_storage_gb REAL,
                features_json TEXT DEFAULT '{}',
                is_active BOOLEAN DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """))
            
            # Crear índice en plan_type
            print("Creando índices en subscription_plans...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_subscription_plans_plan_type 
                ON subscription_plans(plan_type)
            """))
            
            # 2. Crear tabla workspace_subscriptions
            print("Creando tabla 'workspace_subscriptions'...")
            session.execute(text("""
            CREATE TABLE IF NOT EXISTS workspace_subscriptions (
                id VARCHAR(36) PRIMARY KEY,
                workspace_id VARCHAR(36) UNIQUE NOT NULL,
                plan_id VARCHAR(36) NOT NULL,
                status VARCHAR(20) NOT NULL,
                current_period_start DATETIME NOT NULL,
                current_period_end DATETIME NOT NULL,
                current_users_count INTEGER DEFAULT 0,
                current_documents_count INTEGER DEFAULT 0,
                current_documents_this_month INTEGER DEFAULT 0,
                current_storage_gb REAL DEFAULT 0.0,
                payment_provider VARCHAR(50),
                payment_provider_subscription_id VARCHAR(255),
                payment_metadata_json TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (plan_id) REFERENCES subscription_plans(id)
            )
            """))
            
            # Crear índices
            print("Creando índices en workspace_subscriptions...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_subscriptions_workspace_id 
                ON workspace_subscriptions(workspace_id)
            """))
            
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_subscriptions_plan_id 
                ON workspace_subscriptions(plan_id)
            """))
            
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_subscriptions_status 
                ON workspace_subscriptions(status)
            """))
            
            # 3. Crear tabla workspace_invitations
            print("Creando tabla 'workspace_invitations'...")
            session.execute(text("""
            CREATE TABLE IF NOT EXISTS workspace_invitations (
                id VARCHAR(36) PRIMARY KEY,
                workspace_id VARCHAR(36) NOT NULL,
                invited_by_user_id VARCHAR(36) NOT NULL,
                email VARCHAR(200) NOT NULL,
                role_id VARCHAR(36) NOT NULL,
                token VARCHAR(64) UNIQUE NOT NULL,
                status VARCHAR(20) NOT NULL,
                expires_at DATETIME NOT NULL,
                accepted_at DATETIME,
                accepted_by_user_id VARCHAR(36),
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (invited_by_user_id) REFERENCES users(id),
                FOREIGN KEY (role_id) REFERENCES roles(id),
                FOREIGN KEY (accepted_by_user_id) REFERENCES users(id)
            )
            """))
            
            # Crear índices
            print("Creando índices en workspace_invitations...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_invitations_workspace_id 
                ON workspace_invitations(workspace_id)
            """))
            
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_invitations_email 
                ON workspace_invitations(email)
            """))
            
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_invitations_token 
                ON workspace_invitations(token)
            """))
            
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_workspace_invitations_status 
                ON workspace_invitations(status)
            """))
            
            session.commit()
            print("\n✅ Migración completada: Tablas de suscripciones e invitaciones creadas")
            
        except Exception as e:
            session.rollback()
            print(f"\n❌ Error en la migración: {e}")
            raise


if __name__ == "__main__":
    migrate()

