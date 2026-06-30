# Alcance — Refactor de UI del ciclo core del documento

> **Objetivo:** que el ciclo *crear → revisar → aprobar → consultar (lectura)* funcione de punta a punta, prolijo y alineado al prototipo. Estabiliza el producto para que sea **demostrable y usable**, antes de meter el diferencial (Tyto).
>
> **NO incluye** (fases siguientes): Tyto/chat, red documental/relaciones, evidencias (parkeado), importación masiva (más allá de GDD-21), panel con KPIs de Tyto, doble aprobación, portal ciudadano.

---

## Principio

El prototipo quiere que la ficha **"se sienta oficial y confiable"** y que **las acciones por estado/rol sean obvias**. Hoy el ciclo está flojo: el approval flow no muestra acciones que corresponden, los artefactos estaban rotos (ya arreglado), y la UI no matchea el prototipo. El refactor ordena esto.

---

## Item 0 (BLOQUEANTE) — Motor de acciones del documento

**Diagnóstico:** `/documents/[id]/page.tsx` (~1750 líneas) decide qué acciones mostrar (enviar a revisión, aprobar, rechazar, editar, nueva versión, cancelar envío) combinando ~10 variables de permiso/rol/estado que cargan async en momentos distintos (`userId`, `role`, `hasApprovePermission`, `hasDocumentEditPermission`, `versions`, `docStatus`…). Resultado: **condiciones de carrera** → botones que no aparecen aunque correspondan (es lo que rompió D4: superadmin + creador del draft sin botón "Enviar a revisión").

**Fix:** extraer un **selector de acciones puro y testeable**:

```ts
getDocumentActions({ docStatus, versions, role, userId, permissions })
  -> { canSubmitForReview, canApprove, canReject, canEditMetadata,
       canCreateNewVersion, canCancelSubmission, canDelete }
```

- Una sola fuente de verdad para "qué puede hacer el usuario con este documento ahora".
- **Tests unitarios** de la matriz estado×rol (incluido el caso que falló: *superadmin creador de draft → puede enviar a revisión*).
- La ficha consume solo `actions.*`, sin recalcular reglas inline.

Esto **arregla D4** y previene toda la clase de bug. Es prerrequisito del resto.

---

## Pantallas del prototipo (core loop), por prioridad

### 1. Ficha del documento — la más importante
- **Prototipo:** documento oficial y confiable — nombre, tipo, estado, versión, aprobador, fecha, contenido, **acciones claras por estado/rol**, historial/trazabilidad.
- **Hoy:** funcional pero **monolítica** (1750 líneas, lógica de permisos enredada — la fuente de D4).
- **Refactor:** partir en componentes (header con estado+acciones, metadata, versiones, panel de validación, historial); consumir el selector de acciones (Item 0); alinear al design system Margay. Dejar **placeholders** para "relaciones / red / impacto" (fases siguientes), sin construirlos.

### 2. Flujo de aprobación
- **Prototipo:** "Pendientes de aprobación" (bandeja) + "Flujo del aprobador" (panel: PDF + aprobar/rechazar + observaciones + "liberar para otro aprobador"). Microcopy clave: *"Al aprobar esta versión, autorizás que Tyto la use como fuente oficial."*
- **Hoy:** `/dashboard/approval-queue` + `[id]/review` existen, parciales.
- **Refactor:** asegurar el ciclo completo andando (enviar → pendiente → aprobar/rechazar → aprobado); alinear el panel del aprobador al prototipo. *(Doble aprobación = fase posterior.)*

### 3. Alta de documento
- **Prototipo:** "creemos un documento" — datos mínimos, fuentes, generar, revisar. *(Evidencias parkeado → queda como "subí archivos para generar".)*
- **Hoy:** `/processes/new` funcional, con selector de **tipo de documento** ya integrado (Fase 0).
- **Refactor:** alineación visual + de copy. **Bajo esfuerzo.**

### 4. Home / lista documental
- **Prototipo:** "Home documental" + Panel de control con KPIs (varios dependen de Tyto → **omitir esos**).
- **Hoy:** `/workspace` (lista con filtros) + bandejas por rol separadas.
- **Refactor:** definir el home (lista documental como principal); KPIs básicos sin Tyto (borradores, pendientes, aprobados, actividad por carpeta). Consolidar bandejas.

### 5. Vista del documento aprobado (lectura)
- **Prototipo:** documento oficial — "v1 · aprobado por · fecha", solo lectura, confiable.
- **Hoy:** `/dashboard/view` (viewer).
- **Refactor:** reusar la ficha (1) en **modo lectura**; alinear visual.

---

## Orden de ejecución sugerido

```
Item 0 (selector de acciones + fix D4 + tests)
   → 1. Ficha (refactor + componentes + DS)
   → 2. Flujo de aprobación (ciclo completo + panel aprobador)
   → 3. Alta (alineación visual)
   → 4. Home / lista
   → 5. Vista aprobado (modo lectura de la ficha)
```

Item 0 + Ficha + Flujo de aprobación es el **núcleo** (cierra el loop crear→aprobar). El resto es alineación visual de menor riesgo.

---

## Cómo ejecutarlo

- El refactor visual pasa por el **design system Margay**. Hay un agente dedicado (`margay-frontend`, dueño del DS) que conviene usar para construir/alinear pantallas y mantener consistencia.
- El prototipo (`prototipo/Process AI - Prototipo (1).html`) es la **fuente de verdad visual**; cada pantalla se specifica contra él.
- Por pantalla: spec corta (estados, acciones, criterios de aceptación), como hicimos con Fase 0.

---

## Decisiones tomadas
1. **Home = la Biblioteca.** El home es la biblioteca documental (lista/árbol de documentos y carpetas), no un dashboard de KPIs. Las bandejas por rol (por aprobar / en revisión / aprobados) se mantienen como vistas, pero el home es la biblioteca.
2. **Doble aprobación: afuera.** Queda para versiones futuras; el selector de acciones NO la contempla por ahora (aprobación simple de un paso).
3. **Fidelidad total al prototipo.** Las pantallas deben quedar **tal cual el prototipo** (`prototipo/Process AI - Prototipo (1).html` es la fuente de verdad visual). Se construyen contra él vía el design system Margay.
