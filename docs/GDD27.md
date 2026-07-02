# GDD-27 — Wizard Nuevo documento: cablear Step 3 (Enviar a aprobación)

> **Tarea:** cablear el Step 3 del wizard `/documents/new` al backend real.  
> **Estado:** implementado (Bloque B — mínimo de fase).  
> **Alcance:** solo `ui/`. Sin cambios de backend.

---

## Objetivo

Reemplazar el flujo demo del paso **Enviar a aprobación** (picker de aprobadores falso, envío simulado) por llamadas reales a la API de revisión, con confirmación y posibilidad de retirar la solicitud.

---

## Decisión de producto (B0)

**Opción (a) simplificar** — confirmada.

- No hay selección de aprobadores por envío (el backend no lo soporta hoy).
- Cualquier usuario con permiso `documents.approve` en la carpeta/workspace puede aprobar.
- Se eliminó el picker interactivo y el campo de comentario (no hay endpoint que los persista en `submitVersionForReview`).

---

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `ui/components/documents/wizard/NuevoDocumentoWizard.tsx` | Orquestación: submit, retiro, footer, navegación |
| `ui/components/documents/wizard/Step3EnviarAprobacion.tsx` | UI Step 3 cableada + aprobadores informativos |
| `ui/components/documents/wizard/data.ts` | Eliminados `Approver` / `APPROVERS` demo |

---

## B1 — "Enviar a aprobación" → submit real

### Antes
- Footer Step 3 habilitaba el botón solo si había aprobadores seleccionados en demo.
- `onPrimary` hacía `setS3({ sent: true })` sin llamar al backend.
- Título hardcodeado: "Cierre de caja".

### Después
- `sendForApproval()` en `NuevoDocumentoWizard.tsx`:
  1. `getDocumentVersions(documentId)` → versión con `version_status === "DRAFT"`.
  2. `submitVersionForReview(documentId, draft.id, userId, workspaceId)`.
  3. Guarda `draftVersionId` (versión `IN_REVIEW`) para poder cancelar después.
  4. `setS3({ sent: true })` solo tras éxito.
- Hooks: `useUserId()`, `useWorkspace()` → `selectedWorkspaceId`.
- Footer: `"Enviar a aprobación"` / `"Enviando…"`, `disabled` si falta `documentId` o está en vuelo.
- `Step3EnviarAprobacion` carga `getDocument(documentId)` → nombre real en formulario y confirmación.
- Errores de submit en banner (`submitError`).

### APIs reutilizadas
- `getDocumentVersions`
- `submitVersionForReview`

---

## B2 — Confirmación: volver / retirar

### Antes
- "Volver a documentos" reseteaba el wizard al Step 1.
- "Retirar solicitud" solo hacía `set({ sent: false })` local.

### Después
- **Volver a documentos** (footer, post-envío) → `router.push(/documents/${documentId})`.
- `withdrawSubmission()` → `cancelDocumentSubmission(documentId, draftVersionId, userId, workspaceId)`.
- Tras retiro exitoso: vuelve al formulario de envío (`sent: false`), limpia `draftVersionId`.
- Estados UI: `withdrawing`, `withdrawError`; botón "Retirando…" mientras corre.

### APIs reutilizadas
- `cancelDocumentSubmission`

---

## B3 — Aprobadores informativos (sin picker)

### Antes
- Lista demo `APPROVERS` con checkboxes seleccionables.
- Textarea "Comentario para los aprobadores" (sin backend).

### Después
- `getWorkspaceMembers(selectedWorkspaceId)` al montar Step 3.
- Filtro: roles `owner`, `admin`, `approver` (alineado a `useHasPermission`).
- Chips **no interactivos** (iniciales + nombre + rol) bajo **"Quiénes pueden aprobar"**.
- Misma lista en la card de confirmación (reemplaza "Aprobadores seleccionados").
- Fallback: *"No hay aprobadores configurados en este workspace."*

### `Step3State` simplificado

```tsx
export interface Step3State {
  folderName: string;
  sent: boolean;
}
```

Eliminados: `approvers`, `comment`.

---

## Flujo de datos

```
Step 3 (pre-envío)
  ├─ getDocument(documentId)           → título real
  └─ getWorkspaceMembers(workspaceId)  → chips informativos

Footer: "Enviar a aprobación"
  └─ getDocumentVersions → DRAFT
       └─ submitVersionForReview → IN_REVIEW + pending_validation

Confirmación
  ├─ "Volver a documentos" → /documents/{id}
  └─ "Retirar solicitud"
       └─ cancelDocumentSubmission → vuelve a DRAFT + draft
```

---

## Criterios de aceptación

| CA | Estado |
|----|--------|
| "Enviar a aprobación" deja el doc en `pending_validation` y aparece en Por aprobar | ✅ |
| "Retirar solicitud" lo vuelve a borrador | ✅ |
| Sin controles falsos (picker / comentario) | ✅ |
| `npx tsc --noEmit` en verde | ✅ |

---

## Verificación manual

1. `/documents/new` → crear borrador → Step 2 → **Continuar**.
2. Step 3: nombre real del documento + lista informativa de aprobadores.
3. **Enviar a aprobación** → card de confirmación.
4. Verificar en `/dashboard/approval-queue` que el documento aparece pendiente.
5. **Retirar solicitud** → volver al formulario; en `/documents/{id}` status `draft`.
6. **Volver a documentos** → navega a la ficha del documento.

---

## Fuera de alcance

- Selección de aprobadores específicos por envío (requiere backend nuevo → backlog).
- Comentario al enviar a revisión (requiere extender `submitVersionForReview`).
- Aprobadores filtrados por carpeta destino (hoy se listan a nivel workspace por rol).
- Resumen de generación demo en Step 2 (Bloque C/D).

---

## Relación con GDD-26

Con GDD-26 (Step 2) + GDD-27 (Step 3), el wizard `/documents/new` queda cableado de punta a punta para el flujo mínimo: **crear borrador → revisar/editar → enviar a aprobación**.
