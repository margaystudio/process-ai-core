# Handoff — `document_type` pasó a entidad por-tenant (para Nacho)

> Contexto: revisando tu rama `feature/Config-Tipos-de-Doc` vimos que los toggles de
> comportamiento se guardaban en `catalog_option`, que es **global**. Como el PATCH
> quedaba gateado a owner/admin del workspace, **cualquier admin de un tenant podía
> editar el catálogo que ven todos** (leak cross-tenant). Además `document_type` ya era
> una entidad fuerte (columna en `Document`, con `prompt_text` + política), no un valor
> de enum. Así que lo promovimos a su propia tabla, **por-tenant**. Diseño completo:
> `docs/PLAN_DOCUMENT_TYPES.md`.

## Qué cambió

- **Nueva tabla `document_type`** (por-tenant, `workspace_id NOT NULL`). Cada tenant es
  dueño de su set; se siembra con los 14 defaults actuales al provisionar el workspace
  (copy-on-provision) y se backfilleó a los existentes (migración `0008`).
- **Fuente de los defaults**: `process_ai_core/domains/document_types/defaults.py`
  (key, label, prompt_text, behaviors, sort_order, icon, color).
- **API nueva** `/api/v1/document-types` (`api/routes/document_types.py`): GET/PATCH/POST
  scopeados al workspace activo, gate owner/admin del propio tenant, aislamiento 404,
  behaviors validados contra la allowlist.
- **`Document.document_type` no cambió**: sigue guardando el string `key`.

## Qué pasó con tu trabajo

- **Tu UI (`app/document-types/page.tsx`) + el nav**: los **adoptamos y repuntamos** al
  API nuevo (ya reusabas `Switch`/`useAsync`/`canAdministerWorkspace`, quedó igual de
  lindo). Le sumamos selector de **icon/color** y `InheritancePill` (base vs personalizado).
- **Tu migración `0007`** (`catalog_option.behaviors_json`): quedó en la cadena
  (`0006→0007→0008`) porque **ya la habías aplicado al sandbox**. La columna queda
  **vestigial** (no se usa); se puede dropear en una migración aparte.
- **Tu backend de behaviors en `catalog.py`** (el PATCH sobre `catalog_option`): quedó
  **superseded** por el modelo nuevo, no se mergeó.
- El dominio `document_type` se **retiró del seed del catálogo**; los consumidores del
  front (`DocumentTypeSelector`, filtro de biblioteca) ahora leen el API nuevo.

## Cómo trabajar de acá en más

- Para editar/crear tipos: `/api/v1/document-types` (por workspace). No uses `catalog_option`.
- Para agregar un default nuevo para todos los tenants nuevos: `defaults.py`. (Ojo: es
  copy-on-provision, no se propaga a tenants ya creados — eso sería un backfill aparte.)
- Behaviors: allowlist en `domains/document_types/BEHAVIOR_KEYS`
  (`versionado, aprobacion, tyto, relaciones, metadatos`).

## Nota de proceso (para acordar)

Aplicaste la `0007` al **sandbox compartido desde una rama sin mergear**, lo que dejó la
cadena de migraciones divergente para todos (tuvimos que rebasar sobre ella). Mejor
acordar: **las migraciones se aplican al sandbox recién cuando entran a `develop`**.

## Estado

- Todo en `develop` (backend + UI). `0008` aplicada a **sandbox** (370 workspaces × 14).
- **Prod**: migración + deploy pendientes (gateado).
