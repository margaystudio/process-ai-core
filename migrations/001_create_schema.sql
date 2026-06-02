-- Schema dedicado de process-ai-core en el Postgres compartido de Supabase (Margay).
-- Convención: margay-workspace usa schema `workspace`; este módulo usa `process_ai`.

CREATE SCHEMA IF NOT EXISTS process_ai;

-- Permisos para roles típicos de Supabase (idempotente).
GRANT USAGE ON SCHEMA process_ai TO postgres, anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA process_ai TO postgres, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA process_ai TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA process_ai
    GRANT ALL ON TABLES TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA process_ai
    GRANT ALL ON SEQUENCES TO postgres, service_role;
