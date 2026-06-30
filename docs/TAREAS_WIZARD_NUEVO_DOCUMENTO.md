# Tareas — Terminar la fase "Nuevo documento" (wizard)

> **Estado actual:** el wizard `/documents/new` está construido visualmente y con **Step 1 ya cableado** (evidencias reales como input, carpetas reales, `createProcessRun` real). Falta cablear **Step 2** y **Step 3**, más algunos enhancements. Componentes en `ui/components/documents/wizard/`.
>
> **Convención:** cada tarea trae archivos, qué hacer, criterios de aceptación (CA) y dependencias. Rama `feat/fase-0`. `npx tsc --noEmit` en verde como condición de cada PR.
>
> **Buscá los `// TODO(wire)`** en `ui/components/documents/wizard/` — marcan los puntos pendientes.

---

## Bloque A — Step 2 (Revisión del borrador)

### A1 · Mostrar el borrador generado REAL  · `M`
- **Archivos:** `wizard/Step2Revision.tsx`, `wizard/NuevoDocumentoWizard.tsx`.
- **Qué:** Step 2 ya recibe `documentId` como prop. Cargar `getDocument(documentId)` + `getDocumentVersions(documentId)` → tomar la versión **DRAFT**. Mostrar el **contenido real** generado (el `content_markdown`/`content_html` de la versión DRAFT, o el preview del PDF vía `getVersionPreviewPdfUrl(documentId, draftVersionId)`). **Eliminar** los `DRAFT_TITLE`/`DRAFT_BODY` hardcodeados ("Cierre de caja").
- **CA:** tras "Crear borrador", el Step 2 muestra el documento **realmente generado** (nombre + contenido), no el demo.

### A2 · Editor del borrador (toggle Editar/Listo) → guardar  · `M`
- **Archivos:** `wizard/Step2Revision.tsx`.
- **Qué:** el toggle "Editar" permite editar; "Listo" guarda. Reusar el editor de la ficha (`ui/components/documents/ManualEditPanel.tsx` / Tiptap) y las funciones `getEditableContent` / `saveEditableContent` (o `updateDocumentContent`) de `ui/lib/api.ts`.
- **CA:** editar el borrador y tocar "Listo" persiste; al recargar el documento los cambios están.

---

## Bloque B — Step 3 (Enviar a aprobación)

### B0 · DECISIÓN de producto: ¿selección de aprobadores? 🔒
El prototipo deja **elegir aprobadores específicos**. El backend hoy **no** soporta eso: cualquiera con permiso `documents.approve` en la carpeta puede aprobar (permisos por `folder_permissions`/roles operativos), no se eligen aprobadores por envío.
- **(a) Simplificar (recomendado v1):** Step 3 sin selección de aprobadores; solo "Enviar a aprobación". Mostrar (informativo) quiénes pueden aprobar en esa carpeta.
- **(b) Implementar selección:** backend nuevo (guardar aprobadores elegidos por validación/versión + notificarlos) + front. Más grande → backlog.
> **Confirmar con producto antes de B1–B3.**

### B1 · "Enviar a aprobación" → submit real  · `S`
- **Archivos:** `wizard/NuevoDocumentoWizard.tsx` (footer step 3), `wizard/Step3EnviarAprobacion.tsx`.
- **Qué:** cablear el botón a `submitVersionForReview(documentId, draftVersionId, userId, workspaceId)` (de `ui/lib/api.ts`). Mostrar la card de confirmación con el **nombre real** del documento (no demo).
- **CA:** "Enviar a aprobación" deja el documento en `pending_validation`; aparece en **"Por aprobar"**.

### B2 · Confirmación: volver / retirar  · `S`
- **Archivos:** `wizard/Step3EnviarAprobacion.tsx`, `NuevoDocumentoWizard.tsx`.
- **Qué:** "Volver a documentos" → redirigir a `/documents/{documentId}` (o `/workspace`). "Retirar solicitud" → `cancelDocumentSubmission(documentId, draftVersionId, userId, workspaceId)` (vuelve a DRAFT).
- **CA:** "Retirar solicitud" cancela el envío y el documento vuelve a borrador.

### B3 · (si B0=a) Mostrar aprobadores de la carpeta (informativo)  · `S`
- **Qué:** en vez del picker, listar quiénes pueden aprobar en la carpeta destino (de los roles/permisos), solo informativo.
- **CA:** Step 3 no muestra un picker falso; muestra info real o nada.

---

## Bloque C — Evidencias: procesamiento real (enhancement, "los badges")

> Hoy las evidencias se muestran como **"Listo para usar"** (sin los badges "Audio transcripto / OCR completado / Idioma / N págs") porque **no se procesan al subir** — el procesamiento real ocurre al **generar** (`createProcessRun` transcribe/OCR internamente). Para que los badges del prototipo sean **reales**, hay que procesar cada evidencia al subirla.

### C1 · (BACKEND) Endpoint de procesamiento por archivo  · `L`
- **Qué:** endpoint que recibe un archivo, lo procesa según tipo (audio→transcribir con `TranscriptionProvider`; imagen/PDF escaneado→OCR; PDF con texto→extraer) y devuelve `{ extracted_text, status, metadata }` (idioma, duración, páginas, etc.). Reusar `process_ai_core/ai` (providers de 0.2).
- **Dep:** **`OCRProvider` no está implementado** — 0.2.1 dejó la interfaz; la impl quedó parkeada (estrategia barata: texto embebido del PDF → Tesseract local). Hay que implementarlo (ver `docs/SPEC_FASE_0_1...` épica 1.2).
- **CA:** subir un audio devuelve su transcripción + idioma + duración; subir una imagen devuelve OCR.

### C2 · (FRONT) Mostrar estado/badges reales por evidencia  · `M`
- **Archivos:** `wizard/AddEvidenceModal.tsx`, `wizard/EvidenceCard.tsx`.
- **Qué:** al agregar una evidencia, llamar al endpoint C1 → mostrar "procesando…" → badges reales (transcripto/OCR/idioma/págs), tal cual el prototipo. La generación (`createProcessRun`) puede reusar el texto ya extraído.
- **Dep:** C1.
- **CA:** los badges del prototipo aparecen y son verdaderos.

---

## Bloque D — Settings / loose ends

### D1 · Toggle "Disponible para consultas inteligentes" (Tyto)  · `S` (cuando exista Tyto)
- **Archivos:** `wizard/Step1NuevoDocumento.tsx` (`// TODO(wire): smartQueries`).
- **Qué:** hoy es visual. Cuando exista Tyto, persistir como campo del documento (ej. `documents.tyto_enabled`) y enviarlo al crear. Por ahora **dejar visual o ocultar**.

### D2 · Gaps de datos de la Biblioteca (backlog)  · `M`
- Color por carpeta (campo `color` en `Folder`), endpoint de **"Recientes"** server-side, filtros adicionales (Responsable/Autor/Aprobador/Fecha/Consultas IA) — requieren datos/endpoints nuevos. Hoy ocultos/omitidos. Backlog.

---

## Orden sugerido
```
A1 → A2            (Step 2 funcional)
B0 (decisión) → B1 → B2 → B3   (Step 3 funcional)
   → loop completo end-to-end por el wizard
C1 → C2           (badges reales, enhancement)
D1, D2            (cuando aplique)
```
**Mínimo para "fase terminada":** A1, A2, B1, B2 (+ B0 decidido). Con eso el wizard genera → revisa → envía a aprobación de punta a punta con datos reales. C y D son enhancements.

## Verificación por tarea
- `npx tsc --noEmit` en `ui/` en verde.
- Para las de backend (C1): `py_compile` + app import + (si toca esquema) migración Alembic normal (`revision --autogenerate`).
- Probar el flujo real en `/documents/new`.
