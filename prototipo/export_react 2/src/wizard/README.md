# Nuevo documento — wizard export (React + Tailwind)

The **complete** AI-assisted document-creation wizard, one component per step/state, in the same readable, unbundled style as `export_react`. Recreated from the prototype; data is demo data (`wizard/data.tsx`) — replace with your API.

## Files

```
src/wizard/
├── data.tsx                   # types + demo data: EVIDENCE_TYPES, INITIAL_EVIDENCE, FOLDERS,
│                              #   APPROVERS, GEN_STEPS, CONTEXT_EXAMPLES, DETAIL_LEVELS, Icon, helpers
├── NuevoDocumentoWizard.tsx   # ★ orchestrator: owns state, footer logic, evidence processing, modal
├── WizardContainer.tsx        # stepper (1·2·3) + content slot + bottom action bar (Atrás / primary+hint)
├── Step1NuevoDocumento.tsx    # 2-col: form (Nombre, Guardar en, contexto IA, opciones avanzadas) + Evidencias
├── Step2Revision.tsx          # generation summary + draft editor (read/edit toggle)
├── Step3EnviarAprobacion.tsx  # approver picker + comment  →  "sent" confirmation card
├── GeneratingOverlay.tsx      # full-screen "La IA está armando el borrador" (pipeline)
├── AddEvidenceModal.tsx       # "Agregar evidencia": import (type→file→processing) + record audio (idle→rec→processing→done)
├── EvidenceCard.tsx           # ★ reusable evidence card: type variants + processing/done badges (+ compact variant)
├── FolderSelector.tsx         # ★ "Guardar en / Cambiar" field + folder-picker modal
└── ProcessingSteps.tsx        # reusable vertical pipeline (done ✓ / active spinner / todo)
```

★ = the reusable components called out in the request.

## How it flows

`NuevoDocumentoWizard` renders `WizardContainer` (stepper + footer) around the active step:

1. **Step 1** — fill the form, manage evidence. "Agregar evidencia" opens `AddEvidenceModal`. New evidence shows a brief *Procesando…* state on its card, then its result chips (e.g. *Audio transcripto · Idioma: ES · 1:32*). Footer primary = **Crear borrador** (disabled until a folder is chosen).
2. **Crear borrador** → `GeneratingOverlay` runs the `GEN_STEPS` pipeline (~3s), then advances to Step 2.
3. **Step 2** — generation summary (evidence used + sections/steps/evidence counts) and the draft editor with an **Editar / Listo** toggle. Footer = **Continuar**.
4. **Step 3** — choose approvers + optional comment. **Enviar a aprobación** flips to the confirmation card (selected approvers, what happens on approval, *Pendiente de aprobación*, *Retirar solicitud*).

## Evidence types & states

`EVIDENCE_TYPES` (in `data.tsx`) defines, per type (**Audio / Video / PDF / Imagen / Documento**): accepted formats, result chips, help text, and the **processing pipeline labels**. Examples:

- **Audio** → `Audio guardado → Transcribiendo… → Detectando idioma… → Listo`, chips `Audio transcripto · Idioma: ES · 0:48`
- **PDF** → `PDF guardado → Extrayendo texto… → Procesando páginas… → Listo`, chips `Texto extraído · PDF procesado · 8 págs`
- **Imagen** → `Imagen guardada → OCR en proceso… → Detectando texto… → Listo`, chips `OCR completado · 1 imagen`

`AddEvidenceModal` drives those pipelines via `ProcessingSteps`. The **record** flow has its own states: `idle → rec (timer) → saving (pipeline) → done (describe + add)`.

## Wiring to a real backend

- Replace the `setTimeout`/`setInterval` simulations (`addEvidence`, `generateDraft`, modal pipelines) with real upload + processing + generation calls.
- `Step2Revision`'s draft body is the hardcoded "Cierre de caja" demo — feed it the generated content.
- Approvers come from the destination folder's governance config in the real app.

## Mounting

Render `<NuevoDocumentoWizard />` inside the app shell's content area (it fills height: stepper top, scrollable content, footer bottom). Same Tailwind tokens as `export_react/tailwind.config.js`; no new tokens were needed.

See `screenshots/` for each step and state.
