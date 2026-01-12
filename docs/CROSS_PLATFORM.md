# Compatibilidad Cross-Platform (Mac/Windows/Linux)

Este proyecto ahora es compatible con Mac, Windows y Linux.

## Scripts de Ejecución

### Backend (Python)

#### Opción 1: Script Python (Recomendado - Cross-Platform)

```bash
# Local
python run_api.py local
# o simplemente
python run_api.py

# Test
python run_api.py test

# Production
python run_api.py prod
```

**Ventajas:**
- ✅ Funciona en Mac, Windows y Linux
- ✅ No requiere bash
- ✅ Manejo de errores mejorado

#### Opción 2: Scripts Shell (Mac/Linux)

Los scripts `.sh` originales siguen funcionando en Mac y Linux:

```bash
# Local
./run_api_local.sh

# Test
./run_api_test.sh

# Production
./run_api_prod.sh
```

**Nota:** En Windows, estos scripts no funcionan. Usa la opción 1 (Python).

### Frontend (Node.js)

El frontend ahora usa `cross-env` para compatibilidad cross-platform:

```bash
cd ui

# Instalar dependencias (si es la primera vez)
npm install

# Desarrollo local
npm run dev

# Desarrollo test
npm run dev:test

# Build
npm run build
```

**Cambios realizados:**
- ✅ Agregado `cross-env` para manejar variables de entorno en Windows
- ✅ Scripts npm actualizados para usar `cross-env`

## Requisitos

### Python
- Python 3.10 o superior
- Entorno virtual activado
- Dependencias instaladas: `pip install -e ".[dev]"`

### Node.js
- Node.js 18 o superior
- npm o yarn
- Dependencias instaladas: `npm install` (en el directorio `ui/`)

## Configuración de Ambientes

### Backend

Los archivos de configuración son los mismos en todas las plataformas:

- `.env.local` - Ambiente local
- `.env.test` - Ambiente de test
- `.env.production` - Ambiente de producción

**Nota:** Estos archivos están en `.gitignore` y no se suben al repositorio.

### Frontend

Los archivos de configuración están en `ui/`:

- `ui/.env.local` - Ambiente local
- `ui/.env.test` - Ambiente de test
- `ui/.env.production` - Ambiente de producción

## Solución de Problemas

### Windows: "python no se reconoce como comando"

Asegúrate de tener Python instalado y en el PATH, o usa `py` en lugar de `python`:

```cmd
py run_api.py local
```

### Windows: "uvicorn no se reconoce como comando"

Asegúrate de tener el entorno virtual activado:

```cmd
.venv\Scripts\activate
python run_api.py local
```

### Mac/Linux: "Permission denied" en scripts .sh

Haz los scripts ejecutables:

```bash
chmod +x run_api_local.sh
chmod +x run_api_test.sh
chmod +x run_api_prod.sh
```

## Migración desde Scripts .sh

Si estás usando los scripts `.sh` y quieres migrar al script Python:

1. **No necesitas cambiar nada** - Los scripts `.sh` siguen funcionando
2. **Opcional:** Usa `python run_api.py` en su lugar para mejor compatibilidad

El script Python hace exactamente lo mismo que los scripts `.sh`, pero funciona en todas las plataformas.
