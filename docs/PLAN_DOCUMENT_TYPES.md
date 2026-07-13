# Plan — `document_type` como entidad de primera clase (por-tenant)

> **Estado:** Diseño cerrado, en ejecución.
> **Contexto:** revisión de la rama `feature/Config-Tipos-de-Doc` (Nacho), que agregó
> toggles de comportamiento a `catalog_option`. Ese modelo es global y editable por
> cualquier admin de tenant → leak cross-tenant. Además, `document_type` ya es una
> entidad fuerte (columna en `Document`, con `prompt_text` + política), no un valor de enum.

## 1. Decisión de modelo

`document_type` sale de `catalog_option` a **su propia tabla, por-tenant**
(`workspace_id NOT NULL`). **Cada tenant es dueño de su set de tipos.** Al crear un
tenant se lo siembra con los **defaults actuales** (los 14 tipos de hoy).

- **Aislamiento por construcción:** no hay filas globales que un admin pueda pisar; un
  admin solo edita los tipos de su propio workspace.
- **Copy-on-provision (snapshot):** los defaults se copian al crear el tenant. Si más
  adelante cambiamos un default, **no se propaga** a los tenants ya creados (es lo
  buscado: "se crea con los que tenemos ahora").
- **`Document.document_type` no cambia:** sigue guardando el string `key`
  (`"procedimiento"`). La resolución es *soft* por `(workspace_id, key)`, sin FK duro,
  para que el tipo del documento sobreviva aunque el tipo se desactive/borre.

## 2. Tabla `document_type`

| Columna | Tipo | Constraints | Qué es |
|---|---|---|---|
| `id` | String(36) | PK, UUID | Identificador interno (UUID, como Document/Folder). |
| `workspace_id` | String(36) | NOT NULL, FK→`workspaces.id`, index | El tenant dueño. Aislamiento por construcción. |
| `key` | String(50) | NOT NULL, `UNIQUE(workspace_id, key)` | Slug estable (`"procedimiento"`). Lo referencia `Document.document_type`. No cambia al editar el label. |
| `label` | String(200) | NOT NULL | Texto visible en UI. Editable por el tenant. |
| `prompt_text` | Text | NOT NULL, default `""` | Texto inyectado al prompt de generación para este tipo. Editable. |
| `behaviors_json` | Text (JSON) | NOT NULL, default `"{}"` | Toggles: `{versionado, aprobacion, tyto, relaciones, metadatos}` → bool. Validado contra allowlist en la API. |
| `is_active` | Boolean | NOT NULL, default `true` | Tipo habilitado o no (ocultar sin borrar; no afecta docs ya creados). |
| `sort_order` | Integer | NOT NULL, default `0` | Orden en la UI. |
| `origin` | String(20) | NOT NULL, default `'custom'` | `'default'` (sembrado) o `'custom'` (creado por el tenant). |
| `icon` | String(50) | nullable | Nombre de ícono (lucide). Seleccionable. |
| `color` | String(20) | nullable | Color hex (como las carpetas). Seleccionable. |
| `created_at` | DateTime | default utcnow | Auditoría. |
| `updated_at` | DateTime | default utcnow, onupdate | Última edición del tenant. |

**Behaviors (allowlist MVP):** `versionado`, `aprobacion`, `tyto`, `relaciones`, `metadatos`.

## 3. Plan de ejecución

- **Fase 0 — Coordinación.** No mergear `feature/Config-Tipos-de-Doc` como está (modelo
  global). Rescatar su UI + primitivos y repuntear el backend. Su migración `0007`
  (behaviors en `catalog_option`) queda *superseded*.
- **Fase 1 — Template de defaults.** `process_ai_core/domains/document_types/defaults.py`:
  `DEFAULT_DOCUMENT_TYPES` con los 14 tipos actuales (`key`, `label`, `prompt_text`,
  `behaviors`, `sort_order`, `icon`, `color`). Fuente: seed actual + behaviors de Nacho.
- **Fase 2 — Modelo + migración `0008_document_types`.** Crea la tabla y **backfillea**
  cada workspace existente copiando el template.
- **Fase 3 — Seeding en provisión.** En `get_or_create_workspace_for_tenant` (helpers.py),
  tras crear Workspace + carpeta raíz, sembrar `DEFAULT_DOCUMENT_TYPES` para el nuevo `workspace_id`.
- **Fase 4 — API por-tenant.** `api/routes/document_types.py`: `GET` (lista del tenant),
  `PATCH /{id}` (label/prompt/behaviors/is_active/icon/color), opcional `POST`. Gate:
  owner/admin del propio workspace. Deriva `workspace_id` de `resolve_tenant_workspace_id(ctx)`.
- **Fase 5 — Frontend.** Repuntar la página `document-types` a los endpoints nuevos.
  Reusa `<Switch>`, `useAsync`, `canAdministerWorkspace`; suma selector de `icon`/`color`.
- **Fase 6 — Retiro de `document_type` del catálogo.** Sacar el dominio de `catalog_option`
  y del seed.
- **Fase 7 — Tests.** Aislamiento (tenant A edita → B intacto), provisión siembra defaults,
  backfill deja cada workspace con su set.
- **Fase 8 — Rollout.** Migración sandbox → verificar backfill → prod. Deploy API + UI.

## 4. Follow-up (fuera de este plan)

- `business_type` / `language_style` (1 opción, "de cliente") → campos del **Workspace**, no catálogo.
- `detail_level` / `process_type` / `audience` → quedan en `catalog_option`, **superadmin-only**.
