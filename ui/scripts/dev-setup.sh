#!/usr/bin/env bash
#
# Setup del entorno de desarrollo local para macOS / Linux.
#
# Qué hace:
#   1. Verifica/instala mkcert (genera certificados HTTPS locales confiables).
#   2. Instala el CA local de mkcert (una vez por máquina).
#   3. Genera el certificado para *.local.margaystudio.io en ui/.certs/.
#
# El DNS *.local.margaystudio.io ya resuelve a 127.0.0.1 (registro wildcard en
# Squarespace), así que NO hace falta tocar /etc/hosts.
#
# Uso:  npm run dev:setup   (o:  bash scripts/dev-setup.sh)

set -euo pipefail

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.certs"
DOMAIN="*.local.margaystudio.io"

echo "🔧 Setup de entorno local (macOS/Linux)"

# 1. mkcert instalado?
if ! command -v mkcert >/dev/null 2>&1; then
  echo "📦 mkcert no encontrado. Instalando..."
  if command -v brew >/dev/null 2>&1; then
    brew install mkcert nss
  else
    echo "❌ Homebrew no encontrado. Instalá mkcert manualmente: https://github.com/FiloSottile/mkcert"
    exit 1
  fi
fi

# 2. CA local instalado (idempotente)
echo "🔐 Instalando CA local de mkcert (puede pedir tu contraseña)..."
mkcert -install

# 3. Generar certificado
mkdir -p "$CERT_DIR"
echo "📜 Generando certificado para $DOMAIN en $CERT_DIR ..."
mkcert -cert-file "$CERT_DIR/local-margay.pem" \
       -key-file  "$CERT_DIR/local-margay-key.pem" \
       "$DOMAIN" "local.margaystudio.io" "localhost"

echo ""
echo "✅ Listo. Certificados en ui/.certs/"
echo "   Ahora podés correr:  npm run dev"
