# Entorno de desarrollo local — process-ai

Guía para levantar process-ai en local, integrado con el hub de Margay (SSO real).

## Cómo funciona (resumen)

- Los módulos corren en subdominios de `*.local.margaystudio.io`, que **resuelve a
  `127.0.0.1`** vía un registro DNS wildcard (ya configurado; no tocás `/etc/hosts`).
- Todo corre con **HTTPS local** usando certificados de [mkcert](https://github.com/FiloSottile/mkcert).
  Esto es necesario para que el browser habilite WebCrypto (que el login PKCE de Supabase
  requiere) y para compartir la cookie de sesión entre el hub y los módulos.
- El login es del **hub** (`hub.local.margaystudio.io:3001`); process-ai no tiene login propio.

| Servicio | URL local |
|---|---|
| Hub | https://hub.local.margaystudio.io:3001 |
| Process-ai (frontend) | https://process.local.margaystudio.io:3000 |
| Process-ai (backend) | https://api.local.margaystudio.io:8000 |

## Setup (una sola vez por máquina)

### 1. Generar certificados HTTPS locales

**macOS / Linux:**
```bash
cd ui
npm run dev:setup
```

**Windows (PowerShell):**
```powershell
cd ui
npm run dev:setup:win
```

Esto instala mkcert (si falta), instala el CA local, y genera el certificado en `ui/.certs/`.
> En Windows necesitás [Chocolatey](https://chocolatey.org) o [Scoop](https://scoop.sh) para
> que el script instale mkcert automáticamente.

### 2. Variables de entorno

```bash
cp .env.local.example .env.local
# completá NEXT_PUBLIC_SUPABASE_ANON_KEY (pedísela al equipo)
```

### 3. Backend (.env de la raíz)

El backend necesita, además de su config normal:
```
WORKSPACE_URL=https://margay-workspace-...   # o el workspace local
SUPABASE_JWKS_URL=https://nbigcpjmckewuhrqjzrt.supabase.co/auth/v1/.well-known/jwks.json
PROCESS_AI_APP_KEY=process_ai
ARTIFACT_SIGNING_SECRET=<cualquier-string-en-local>
CORS_ORIGINS=https://process.local.margaystudio.io:3000,https://hub.local.margaystudio.io:3001
```

## Levantar el entorno

Necesitás **3 procesos** (hub, frontend, backend). El hub está en su propio repo.

**Backend** (desde la raíz de process-ai-core):
```bash
source .venv/bin/activate
python run_api.py local        # detecta los certs de ui/.certs y levanta con HTTPS
```

**Frontend** (desde `ui/`):
```bash
npm run dev                     # https://process.local.margaystudio.io:3000
```

**Hub** (en el repo margay-hub, ver su propio README.dev.md):
```bash
npm run dev                     # https://hub.local.margaystudio.io:3001
```

## Probar

1. Abrí **https://process.local.margaystudio.io:3000**
2. Sin sesión → te redirige al login del hub.
3. Logueás con Google → volvés a process-ai ya autenticado.

## Troubleshooting

- **"Failed to fetch" / mixed content:** el backend no está en HTTPS. Verificá que
  `ui/.certs/` tenga los certificados y que `python run_api.py local` muestre "HTTPS habilitado".
- **"WebCrypto not supported":** estás entrando por HTTP o por `localhost` en vez de
  `process.local.margaystudio.io`. Usá siempre la URL `https://...local.margaystudio.io`.
- **Loop de redirect al login:** revisá que `https://hub.local.margaystudio.io:3001/auth/callback`
  esté en Supabase → Auth → URL Configuration → Redirect URLs.
- **Cert no confiable (warning del browser):** corré `mkcert -install` de nuevo y reiniciá el browser.
