# Setup del entorno de desarrollo local para Windows (PowerShell).
#
# Qué hace:
#   1. Verifica/instala mkcert (vía Chocolatey o Scoop).
#   2. Instala el CA local de mkcert (una vez por máquina).
#   3. Genera el certificado para *.local.margaystudio.io en ui\.certs\.
#
# El DNS *.local.margaystudio.io ya resuelve a 127.0.0.1 (wildcard en Squarespace),
# así que NO hace falta tocar el archivo hosts.
#
# Uso:  npm run dev:setup   (o:  powershell -ExecutionPolicy Bypass -File scripts\dev-setup.ps1)

$ErrorActionPreference = "Stop"

$CertDir = Join-Path (Split-Path -Parent $PSScriptRoot) ".certs"
$Domain  = "*.local.margaystudio.io"

Write-Host "Setup de entorno local (Windows)"

# 1. mkcert instalado?
if (-not (Get-Command mkcert -ErrorAction SilentlyContinue)) {
    Write-Host "mkcert no encontrado. Intentando instalar..."
    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install mkcert -y
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        scoop install mkcert
    } else {
        Write-Host "ERROR: Instala Chocolatey (https://chocolatey.org) o Scoop, o instala mkcert manualmente:"
        Write-Host "       https://github.com/FiloSottile/mkcert"
        exit 1
    }
}

# 2. CA local instalado (idempotente)
Write-Host "Instalando CA local de mkcert..."
mkcert -install

# 3. Generar certificado
New-Item -ItemType Directory -Force -Path $CertDir | Out-Null
Write-Host "Generando certificado para $Domain en $CertDir ..."
mkcert -cert-file "$CertDir\local-margay.pem" `
       -key-file  "$CertDir\local-margay-key.pem" `
       $Domain "local.margaystudio.io" "localhost"

Write-Host ""
Write-Host "Listo. Certificados en ui\.certs\"
Write-Host "Ahora podes correr:  npm run dev"
