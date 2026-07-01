# GDD-26 — Wizard Nuevo documento: cablear Step 2 (Revisión)

> **Tarea:** cablear el Step 2 del wizard `/documents/new` al backend real.  
> **Estado:** implementado (Bloque A — mínimo de fase).  
> **Alcance:** solo `ui/`. Sin cambios de backend.

---

## Objetivo

Reemplazar el contenido demo hardcodeado ("Cierre de caja") del paso **Revisión** por el borrador real generado en Step 1, y permitir editarlo y persistir los cambios antes de continuar al Step 3.

---

## Archivo modificado

| Archivo | Cambio |
|---------|--------|
| `ui/components/documents/wizard/Step2Revision.tsx` | Cableado completo A1 + A2 |

**Sin cambios** en `NuevoDocumentoWizard.tsx`: ya pasaba `documentId` desde `createProcessRun` (Step 1).

---

## A1 — Borrador generado REAL

### Antes
- Título y cuerpo fijos: `DRAFT_TITLE = "Cierre de caja"` y `DRAFT_BODY` con texto de ejemplo.
- El contenido se parseaba como markdown plano con `\n\n`.
- Comentarios `// TODO(wire)` sin implementar.

### Después
- Al montar (cuando hay `documentId`), carga en paralelo:
  - `getDocument(documentId)` → título del editor (`document.name`).
  - `getEditableContent(documentId)` → HTML de la versión **DRAFT** (`html`, `version_id`).
- Estados de UI: `loading` (skeleton), `error` (mensaje + botón Reintentar), placeholder si `documentId` es `null`.
- Vista de lectura: render inline del HTML con `dangerouslySetInnerHTML` y estilos `.wizard-draft-html` (tipografía alineada al editor Tiptap).
- Botón **Ver PDF** en el header → `usePdfViewer().openVersionPreviewPdf(documentId, versionId)` + `<ModalComponent />`.

### APIs reutilizadas (`ui/lib/api.ts`)
- `getDocument`
- `getEditableContent`
- `getVersionPreviewPdfUrl` (vía hook `usePdfViewer`)

---

## A2 — Editor Editar / Listo → guardar

### Antes
- Modo edición con `<textarea>` local; **Listo** solo cerraba el toggle sin persistir.
- **Cancelar** restauraba el texto demo hardcodeado.

### Después
- Modo edición con **`ManualEditorTiptap`** (mismo componente que la ficha del documento).
- **Listo** → obtiene HTML del editor (`editorRef.getHtml()`) y llama a `saveEditableContent(documentId, html)`.
- **Guardar borrador** (botón interno del Tiptap) usa el mismo `handleSave`.
- **Cancelar** → descarta cambios locales y vuelve a lectura (al reabrir edición, el editor se remonta con el HTML ya guardado).
- Indicador de cambios sin guardar cuando `dirty === true`.
- Estado **Guardando...** en el botón Listo durante el `PUT`.

### Componentes/hooks reutilizados
- `ui/components/documents/ManualEditorTiptap.tsx`
- `ui/hooks/usePdfViewer.tsx`

---

## Flujo de datos

```
Step 1: "Crear borrador"
  └─ createProcessRun(formData) → document_id

Step 2: Step2Revision(documentId)
  ├─ getDocument(documentId)        → title
  ├─ getEditableContent(documentId) → html, version_id (DRAFT)
  ├─ [lectura] render HTML inline
  ├─ [Ver PDF] openVersionPreviewPdf
  └─ [Editar → Listo]
       └─ saveEditableContent(documentId, html) → persiste versión DRAFT
```

---

## Criterios de aceptación

| CA | Estado |
|----|--------|
| Tras "Crear borrador", Step 2 muestra el documento realmente generado (nombre + contenido) | ✅ |
| Editar y tocar "Listo" persiste; al recargar el contenido los cambios están | ✅ |
| `npx tsc --noEmit` en verde | ✅ |

---

## Verificación manual

1. Ir a `/documents/new`.
2. Completar Step 1 (nombre, carpeta, evidencias opcionales) → **Crear borrador**.
3. En Step 2: verificar título y contenido real (no "Cierre de caja").
4. **Editar** → modificar texto → **Listo**.
5. Recargar o volver a abrir el documento desde `/workspace` → `/documents/{id}` y confirmar persistencia.

---

## Fuera de alcance (esta tarea)

- **Resumen de generación** (conteos "3 secciones / 12 pasos", tipos de evidencia demo): sigue hardcodeado; pendiente de bloques posteriores.
- **Step 3** (enviar a aprobación): aún demo; ver Bloque B en `docs/TAREAS_WIZARD_NUEVO_DOCUMENTO.md`.
- **Retomar wizard** desde `/documents/new?documentId=...`: no implementado; el borrador se retoma desde `/workspace` → ficha `/documents/{id}` → **Modificar contenido** → **Edición manual**.

---

## Notas para quien retoma el borrador fuera del wizard

El borrador queda guardado en el **backend** (documento `status: draft`, versión `DRAFT`). Si el usuario sale del wizard:

- En **Biblioteca / Workspace** (`/workspace`), filtrar por **Borrador** y abrir `/documents/{id}`.
- En la ficha, **Editar** (header) edita **metadatos** (nombre, descripción, carpeta).
- Para editar **contenido** como en el wizard: sección **Modificar contenido** → **Mostrar opciones** → **Edición manual** (`ManualEditPanel`).

La UX del wizard (Editar/Listo inline) y la de la ficha (panel colapsable) **no son idénticas**; unificarlas sería trabajo de producto/UX futuro.
