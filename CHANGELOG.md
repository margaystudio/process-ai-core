# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/), simplificado.
Monorepo: se versiona **por componente** con tags prefijados — `api-vX.Y.Z` y `ui-vX.Y.Z`
(norma: `margay-gcp-run-template/docs/VERSIONING.md`).

## Unreleased

### Changed
- Adopción de la norma de versionado Margay + CI/CD:
  - Un solo `ops/release.py` / `ops/deploy.py` (con `--component api|ui`) + soporte de
    `[image].dockerfile` (Dockerfile.api / Dockerfile.ui). Reemplaza los scripts por componente.
  - GitHub Actions: `release.yml` (tags `api-v*` / `ui-v*`) + `deploy-manual.yml` (dropdown
    entorno + componente). El release file se commitea a `main` (default branch; gitflow).
  - `ops/api/releases/` y `ops/ui/releases/` dejan de ignorarse (registro versión→digest).
- Cutover a europe-west1 + Supabase nuevo (api + ui). Digests de us-central1 archivados
  localmente en `ops/{api,ui}/releases/_archive-us-central1/`.
- `/` (health): expone la versión desde `APP_VERSION` en vez de un literal.

Sin tags semver previos (releases eran `sha-*`): las primeras versiones serán
`api-v0.1.0` / `ui-v0.1.0`.
