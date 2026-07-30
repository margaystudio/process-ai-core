#!/usr/bin/env bash
# Postgres local para los tests. Ver docker-compose.yml para el porqué.
#
#   ./tools/dev_db.sh up      levanta el contenedor y aplica las migraciones
#   ./tools/dev_db.sh fresh   destruye el volumen y rearma desde cero
#   ./tools/dev_db.sh down    apaga (conserva los datos)
#   ./tools/dev_db.sh url     imprime la TEST_DATABASE_URL para exportar
set -euo pipefail

cd "$(dirname "$0")/.."

# El driver tiene que ser el mismo que usa la app (psycopg3).
TEST_DB_URL="postgresql+psycopg://process_ai:process_ai@127.0.0.1:55433/process_ai"
CONTENEDOR="margay-process-ai-db"

ALEMBIC="${ALEMBIC:-.venv/bin/alembic}"
[ -x "$ALEMBIC" ] || ALEMBIC="alembic"

PY="${PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY="python3"

esperar_healthy() {
  printf "Esperando a Postgres"
  for _ in $(seq 1 60); do
    if docker inspect -f '{{.State.Health.Status}}' "$CONTENEDOR" 2>/dev/null | grep -q healthy; then
      echo " listo."
      return 0
    fi
    printf "."
    sleep 1
  done
  echo " timeout." >&2
  exit 1
}

migrar() {
  echo "Aplicando migraciones (alembic upgrade head)..."
  # PROCESS_AI_BOOTSTRAP=1 evita que process_ai_core.db.database cargue el .env
  # y nos pise la DATABASE_URL con la del sandbox compartido.
  DATABASE_URL="$TEST_DB_URL" \
  DATABASE_SCHEMA="${DATABASE_SCHEMA:-process_ai}" \
  PROCESS_AI_BOOTSTRAP=1 \
    "$ALEMBIC" upgrade head
}

sembrar() {
  # Las migraciones crean el esquema pero NO los roles de sistema. Sin esto,
  # `sync_membership_from_context` tira "Rol 'admin' (ni 'viewer') encontrado en
  # la DB" y se caen 17 tests (cross-tenant, import semántico, acta). Contra el
  # sandbox compartido no se notaba porque ya venía sembrado de antes.
  # El script es idempotente.
  echo "Sembrando roles y permisos (tools/seed_permissions.py)..."
  DATABASE_URL="$TEST_DB_URL" \
  DATABASE_SCHEMA="${DATABASE_SCHEMA:-process_ai}" \
  PROCESS_AI_BOOTSTRAP=1 \
    "$PY" tools/seed_permissions.py >/dev/null
}

escribir_env_test() {
  # tests/conftest.py lo lee solo: así no hay que exportar nada en cada terminal.
  # `.env.test` ya está en .gitignore.
  cat > .env.test <<EOF
# Generado por tools/dev_db.sh — no se commitea.
# tests/conftest.py lo lee si no hay TEST_DATABASE_URL en el entorno.
TEST_DATABASE_URL=$TEST_DB_URL
EOF
  echo "Escrito .env.test (lo lee pytest solo)."
}

case "${1:-up}" in
  up)
    docker compose up -d
    esperar_healthy
    migrar
    sembrar
    escribir_env_test
    echo
    echo "Listo. Para correr los tests, nada más que:"
    echo "  .venv/bin/pytest"
    ;;
  fresh)
    docker compose down -v
    docker compose up -d
    esperar_healthy
    migrar
    sembrar
    escribir_env_test
    echo "Base recreada desde cero."
    ;;
  down)
    docker compose down
    ;;
  url)
    echo "$TEST_DB_URL"
    ;;
  *)
    echo "Uso: $0 {up|fresh|down|url}" >&2
    exit 1
    ;;
esac
