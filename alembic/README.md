# Migraciones (Alembic)

Migraciones de base versionadas para el schema `process_ai`. Reemplazan el viejo
flujo de `tools/init_db.py` + scripts `tools/migrate_*.py` puntuales.

La configuración (URL y schema) la toma `alembic/env.py` desde
`process_ai_core.db.database` (`DATABASE_URL` / `DATABASE_SCHEMA`, vía `.env`), así
que migraciones y app comparten exactamente la misma config. No hace falta poner la
URL en `alembic.ini`.

> La base es **compartida** con margay-workspace (schema `workspace`). El
> autogenerate está scopeado a `process_ai`: nunca toca otros schemas.

## Comandos

```bash
# Aplicar todas las migraciones pendientes (requiere Postgres). Idempotente.
alembic upgrade head

# Estado actual / historial
alembic current
alembic history

# Generar una migración nueva a partir de cambios en los modelos
alembic revision --autogenerate -m "agrega tabla X"
#   -> revisar SIEMPRE el archivo generado en alembic/versions/ antes de commitear.

# Revertir la última migración
alembic downgrade -1
```

## Flujo para agregar/modificar tablas

1. Editás los modelos en `process_ai_core/db/models.py`.
2. `alembic revision --autogenerate -m "..."`.
3. Revisás el archivo generado (autogenerate no es perfecto: revisá tipos, índices,
   defaults y datos a migrar).
4. `alembic upgrade head` en local contra Postgres y verificás.
5. Commit del modelo + la migración juntos.

## Baseline (congelado)

`0001_baseline` crea el schema y **todas** las tablas a partir de un snapshot DDL
**fijo** (`0001_baseline.sql`), generado una vez desde los modelos. **No** usa
`create_all`, así que **no cambia** cuando cambian los modelos.

Consecuencia: las migraciones posteriores son **normales** — `op.create_table`,
`op.add_column`, `op.alter_column`, etc. — sin guards ni chequeos de existencia.
El flujo es el estándar de Alembic: editás el modelo, `revision --autogenerate`,
revisás, `upgrade head`.

> Si algún día el esquema base cambia mucho y querés re-congelar, se regenera el
> `.sql` desde los modelos (mock engine de SQLAlchemy) y se vuelve a snapshotear.

## Aplicar en cada ambiente

- **Local / test:** `alembic upgrade head` con el `.env` correspondiente.
- **Prod (Supabase `mqld…`):** correr `alembic upgrade head` con la `DATABASE_URL`
  de prod **como paso de deploy gated** (no automático). Ver `docs/AMBIENTES.md`.

## Smoke test

`tests/test_migrations_smoke.py` valida `upgrade head` + `downgrade base` contra un
Postgres real. Corre solo si se define `ALEMBIC_SMOKE_DATABASE_URL`:

```bash
ALEMBIC_SMOKE_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db" \
    pytest tests/test_migrations_smoke.py -v
```
