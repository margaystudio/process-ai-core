# Process AI — Análisis de brecha: Prototipo vs. Implementación actual

> **Fecha:** 2026-06-29 · **Fuentes:** Base de conocimiento Notion (Blueprint, Modelo conceptual v2 "El documento conectado", UX & Design, Technical Architecture, Backlog) · Prototipo Claude Design (`prototipo/Process AI - Prototipo (1).html`) · Código actual (`develop`).
>
> **Propósito:** mapear qué del prototipo/visión está soportado hoy y qué no, para armar el plan de desarrollo.

---

## 0. Veredicto en una frase

Hoy tenemos construida, y bastante sólida, **la mitad "gobernanza documental"** del producto: generar un documento desde evidencias multimedia con IA, versionarlo, aprobarlo/rechazarlo con trazabilidad, organizarlo en carpetas con permisos por rol, todo multi-tenant. **Falta casi toda la mitad "documento conectado + Tyto"**: evidencias como entidad de primera clase, red documental (relaciones semánticas), importación masiva, y el asistente Tyto (RAG gobernado sobre lo aprobado). El prototipo muestra el producto completo; el código cubre ~45-50% de ese alcance, concentrado en el ciclo de vida del documento.

---

## 1. El modelo conceptual (Notion) y dónde estamos parados

El modelo de capas validado en diseño es:

```
EVIDENCIAS → ACTIVOS OFICIALES (doc aprobado) → RED DOCUMENTAL GOBERNADA → TYTO
```

| Capa | Estado actual |
|---|---|
| **Evidencias** (video, audio, PDF, foto, entrevista — persisten y se siguen sumando) | ⚠️ Parcial. Se suben archivos como *input de un run* y se transcriben/procesan, pero **no son una entidad persistente** asociada al documento. Se consumen en la generación y no quedan como acervo re-consultable. No hay tabla `evidence`. |
| **Activos oficiales** (documento aprobado, versionado, auditado) | ✅ Sólido. `documents` + `document_versions` con máquina de estados, aprobación, PDF congelado+hash, audit log. **Este es el núcleo que ya funciona.** |
| **Red documental gobernada** (relaciones tipadas entre activos) | ❌ No existe. Sin `document_relations`, sin `knowledge_objects`, sin UI de confirmación de relaciones. |
| **Tyto** (consulta solo la red aprobada, compone respuesta, cita fuentes + niveles de confianza) | ❌ No existe. Sin chunks, sin embeddings, sin endpoint de query, sin chat. |

**Conclusión:** el producto actual es "documento-first" y se detiene en la capa 2. El diferencial del producto (capas 3 y 4 — gobernanza de la *red* + asistente que responde solo sobre lo aprobado) está sin construir.

---

## 2. Cruce pantalla por pantalla (prototipo → código)

Las pantallas/momentos que muestra el prototipo, contra lo implementado:

| # | Pantalla / momento del prototipo | Estado | Dónde está / qué falta |
|---|---|---|---|
| 1 | **Panel de control** (KPIs, carpetas con más actividad, "más consultados por Tyto", borradores, avisos) | ⚠️ Parcial | Hay dashboards por rol (`/dashboard/approval-queue`, `/to-review`, `/view`) pero son **bandejas de trabajo**, no un panel con KPIs/actividad/métricas. Falta el home con métricas y "más consultados por Tyto" (depende de Tyto). |
| 2 | **Home documental** (lista de documentos con estados, búsqueda, carpetas) | ✅ Sí | `/workspace` — filtros por estado/carpeta/búsqueda, árbol de carpetas, preview PDF. |
| 3 | **Administración de carpetas** (herencia, personalizar por carpeta, "cómo usa Tyto esta carpeta", ponderación, permisos por rol) | ⚠️ Parcial | Carpetas jerárquicas + permisos por rol operativo + herencia: ✅ (`folders`, `folder_permissions`, tab Carpetas). Falta toda la capa "**cómo usa Tyto esta carpeta**" / ponderación / tipo documental por defecto (depende de Tyto y de tipos documentales). |
| 4 | **Crear documento desde evidencias** ("creemos un documento desde sus evidencias": grabar audio, capturar, importar archivo existente, drag de evidencia, tipo de evidencia) | ⚠️ Parcial | `/processes/new` permite subir archivos y generar. Falta: **grabación de audio in-app**, **captura**, gestión de evidencia como acervo, "tipo de evidencia", y el encuadre UX de "evidencias" (hoy es "subí archivos para generar"). |
| 5 | **Enriquecimiento del conocimiento** (extraer metadatos: "transcribiendo / detectando idioma / OCR completado / extrayendo texto") | ⚠️ Parcial | Transcripción de audio (Whisper) + selección de frames de video: ✅. Falta: **OCR de PDF/imagen**, detección de idioma explícita, y la **extracción de metadatos/entidades** como paso visible. |
| 6 | **Evidencias del documento** (persisten, se siguen sumando con el tiempo) | ❌ No | No hay entidad `evidence` ni vista de evidencias asociadas a un documento. |
| 7 | **Pendientes de aprobación + Flujo del aprobador** (circuito, **aprobación simple vs doble**, comentario a aprobadores, liberar para otro aprobador) | ⚠️ Parcial | Aprobar/rechazar 1 paso con observaciones + segregación creador≠aprobador + bandeja: ✅. Falta: **doble aprobación / circuito configurable**, "liberar el documento para otro aprobador", comentario dirigido a aprobadores, circuito definido por carpeta. |
| 8 | **Vista del documento aprobado** (ficha oficial: versión, aprobador, fecha, contenido) | ✅ Sí | `/documents/[id]` — muy completa: metadata, versiones, validaciones, audit, PDF. |
| 9 | **Confirmación de relaciones / red documental** ("la IA propuso estas relaciones", confirmar/rechazar/editar, posible duplicado SAP ERP unir/separar, "entidad nueva → crear", baja confianza, red armándose al lado) | ❌ No | **Ausente completo** (front y back). Es el "corazón de la UX" según el doc de UX, y no está. |
| 10 | **Ficha de documento conectado** (relaciones, documentos relacionados, impacto de cambio) | ⚠️ Parcial | La ficha existe (#8) pero **sin relaciones, sin documentos relacionados, sin análisis de impacto**. |
| 11 | **Consulta a Tyto** (preguntar; respuesta breve + pasos + fuente + versión/fecha; "construida con N piezas de la red aprobada"; niveles de confianza 🟢🟡🔴; ver fragmento/fuente; reportar "esto ya no es así") | ❌ No | **Ausente completo.** No hay chat, ni RAG, ni chunks/embeddings, ni endpoint `/tyto/query`. |
| 12 | **Importar documentación existente** (importar PDF/Word, **lote**, idioma distinto del lote, excluir del lote, "importado ≠ aprobado") | ❌ No | No hay pipeline de importación ni UI de lote. Solo existe generación desde cero. (Nota: hay subida de "archivos de contexto" en `/workspace/context`, pero es otra cosa — no produce documentos importables/aprobables.) |
| 13 | **Usuarios y roles** | ✅ Sí | Tab Usuarios + Roles operativos en settings; `operational_roles`, asignación, permisos. |
| 14 | **Tipos documentales** (procedimiento, instructivo, política, normativa, formulario, checklist, trámite, FAQ…) | ❌ No | El modelo solo distingue `process` vs `recipe` (polimorfismo). No existe el catálogo de **tipos documentales** del Blueprint. |
| 15 | **Onboarding / crear workspace** | ✅ Sí | `/onboarding` — workspace, país, tipo de negocio, idioma, audiencia. |
| 16 | **Personalización / branding del workspace** | ✅ Sí | Tab Personalización: icono, extracción de colores, primario/secundario. |
| 17 | **Suscripción y límites** (plan, uso, storage) | ✅ Sí | Planes, suscripción, límites y uso; storage accounting por tenant. |

**Resumen de cobertura:** ✅ 7 · ⚠️ 6 parciales · ❌ 4 ausentes completos — y los 4 ausentes (relaciones, Tyto, importación, evidencias-persistentes) son justamente los diferenciales del producto.

---

## 3. Estado por capa técnica

### 3.1 Datos (`db/models.py` + migraciones)
**Existe:** `workspaces`, `documents` (polimórfico → `processes`/`recipes`), `document_versions` (DRAFT/IN_REVIEW/APPROVED/REJECTED/OBSOLETE + PDF congelado/hash + audit de aprobación), `folders` (+ `folder_permissions`, herencia), `runs`, `validations`, `audit_logs`, `users`/`roles`/`permissions`/`role_permissions`, `workspace_memberships`, `operational_roles`/`user_operational_roles`, `context_folders`/`context_files`, `subscription_plans`/`workspace_subscriptions`/`workspace_invitations`.

**No existe (lo que pide el Blueprint/Technical Architecture):** `evidence`, `document_relations`, `knowledge_objects`, `document_chunks`, embeddings.

> Nota de proceso: las tablas se crean por SQLAlchemy `create_all`, no hay migraciones versionadas de cada tabla (solo 001 schema, 002 PDF cols, 003 drop artifacts). Para producción conviene formalizar migraciones (Alembic) antes de sumar las tablas nuevas grandes.

### 3.2 Backend / API (`api/routes/`)
**Existe:** CRUD documentos, versiones (submit/cancel/clone), contenido editable (Tiptap + JSON patch), runs/process-runs (pipeline de generación + PDF), validaciones (approve/reject + checklist), folders + permisos, workspaces + branding, users, roles operativos, suscripciones/límites, context-files, artifacts firmados (HMAC).

**No existe:** `/imports`, `/relations`, `/tyto/query`, `/tyto/feedback`, evidencias. Recipe-runs está deshabilitado en MVP.

### 3.3 IA / pipelines (`process_ai_core/`)
**Existe:** provider OpenAI (texto + Whisper + Vision para elegir frame), generación de documento con **validación Pydantic + reintento**, builders/renderers de `processes` y `recipes`, transcripción con timestamps, planificación de pasos.

**No existe:** interfaz abstracta de providers (`LLMProvider`/`EmbeddingProvider`/`OCRProvider` — todo está atado a OpenAI), embeddings, chunking, RAG, extracción de entidades/relaciones, OCR, Ollama/local. La estrategia de "IA cara/barata" del Technical Architecture no está implementada.

### 3.4 Storage
**Existe:** abstracción `BlobStorage` con backends Local y Supabase, accounting por workspace, PDF aprobado congelado + sha256, URLs firmadas. **Sólido.** (Falta confirmar `STORAGE_BACKEND=supabase` en Cloud Run prod — ver memoria de proyecto.)

### 3.5 Auth / multitenancy
**Existe:** JWT Supabase validado por firma (JWKS), mapeo a `users.external_id`, contexto de sesión cacheado, roles globales + operativos, permisos por carpeta, aislamiento por workspace en código. **Sólido.** RLS es por código, no policies SQL.

### 3.6 Frontend (`ui/`)
**Existe:** home documental, crear proceso + subir archivos, ficha de documento (1700+ líneas: validación, versiones, corrección por IA/manual-Tiptap/regenerar, audit), bandejas por rol, aprobar/rechazar, carpetas (CRUD + drag-drop + permisos), settings (6 tabs: general/usuarios/roles/carpetas/suscripción/límites/branding), onboarding, perfil, contexto.

**No existe:** UI de relaciones/red, chat Tyto, importación masiva (drag&drop de lote), gestión de evidencias persistentes, catálogo de tipos documentales, panel de control con KPIs.

---

## 4. Los 4 pilares faltantes (los diferenciales)

Ordenados por valor de producto y por dependencia técnica:

### Pilar A — Evidencias como entidad de primera clase
Hoy los archivos son input efímero de un run. El modelo conceptual exige que **persistan, se asocien al documento y se sigan sumando**. Es prerrequisito UX del flujo "creemos un documento desde sus evidencias" y de "agregar evidencia" sobre un doc existente.
- **Datos:** tabla `evidence` (FK a `document` y/o `document_version`, `kind`, `storage_key`, `sha256`, `extracted_text`, `transcript_json`, `metadata`, `added_at`, `added_by`).
- **Back:** endpoints CRUD de evidencias; reusar pipeline de transcripción/extracción ya existente; OCR para PDF/imagen (nuevo).
- **Front:** sección "Evidencias del documento", agregar/grabar/capturar/importar, estados de procesamiento.

### Pilar B — Red documental: knowledge objects + relaciones
El "corazón de la UX" (UX & Design §5). Requiere extracción semántica + confirmación humana.
- **Datos:** `knowledge_objects` (sistema, rol, área, formulario, trámite…) y `document_relations` (tipo de relación, `status` candidate/confirmed/rejected/obsolete, `confidence`, `evidence_text`, `source_document_version_id`, `created_by_ai`, `confirmed_by/at`).
- **Back:** pipeline semántico (extracción de entidades → normalización → matching exacto/fuzzy/embedding → relaciones candidatas), endpoints `/documents/{id}/relations`, `/relations/{id}/confirm|reject`, detección de duplicados/merge.
- **Front:** pantalla de confirmación de relaciones (agrupado por tipo, confianza, "posible duplicado → unir/separar", "entidad nueva → crear", red armándose al lado). Objetivo UX: confirmar en 30s.

### Pilar C — Tyto (RAG gobernado)
El producto que se vende. Depende de chunks/embeddings (C bajo) y se potencia con la red (B).
- **Datos:** `document_chunks` (por `document_version`, con embedding) — embeddings pertenecen a la **versión vigente aprobada**.
- **Back:** al aprobar versión → generar chunks + embeddings + marcar current; `TytoQueryService`: validar workspace/permisos → filtrar **solo aprobados** → recuperar chunks → **expandir por relaciones confirmadas** → componer respuesta → verificar que haya fuentes → devolver citas + **niveles de confianza** (🟢 aprobado / 🟡 referencia no validada / 🔴 inferido). Endpoints `/tyto/query`, `/tyto/feedback`. Tests críticos: nunca responder con importados sin aprobar; siempre citar fuente.
- **Front:** chat con tarjeta de respuesta (respuesta breve + pasos + fuente + versión/fecha + "construida con N piezas" + niveles de confianza + ver fragmento + reportar "esto ya no es así"). Portal ciudadano (intendencias) como variante simplificada.

### Pilar D — Importación masiva
Clave comercial: muchas orgs ya tienen documentación y no la van a rehacer.
- **Back:** pipeline de importación (archivo → hash → storage → extracción texto/OCR → clasificación → chunks → relaciones candidatas → `DocumentVersion` estado *imported*, **no aprobado**). Endpoints `/imports`, `/imports/{id}`. Aprobación por lote.
- **Front:** elegir carpeta → drag de lote → progreso → detección OCR/idioma → clasificación → excluir del lote → revisar por lote → enviar a aprobación. Mensaje fuerte: "importado ≠ aprobado".

**Habilitador transversal — Tipos documentales:** introducir el catálogo (procedimiento, instructivo, política, normativa, formulario, checklist, trámite, FAQ validada, manual interno/externo) en lugar del binario process/recipe. Atraviesa generación, importación, clasificación y Tyto.

---

## 5. Plan para los devs (fases, épicas, dependencias)

Esfuerzo en talla relativa (S/M/L/XL); secuenciado por dependencias técnicas y valor demostrable.

### Fase 0 — Cimientos (habilita todo lo demás)
| Épica | Talla | Notas |
|---|---|---|
| 0.1 Migraciones versionadas (Alembic) | S | Antes de sumar tablas grandes; reemplaza `create_all` implícito. |
| 0.2 Abstracción de providers IA (`LLMProvider`, `EmbeddingProvider`, `OCRProvider`) | M | Refactor de `llm_client.py`; habilita embeddings, OCR, y estrategia caro/barato. |
| 0.3 Catálogo de **tipos documentales** | M | Tabla/enum + selector en alta + clasificación. Atraviesa A–D. |

### Fase 1 — Evidencias de primera clase (Pilar A)
| Épica | Talla | Dep. |
|---|---|---|
| 1.1 Tabla `evidence` + endpoints CRUD | M | 0.1 |
| 1.2 OCR de PDF/imagen + detección de idioma | M | 0.2 |
| 1.3 UI "Evidencias del documento" (agregar/grabar/capturar/importar, estados) | L | 1.1 |
| 1.4 Reencuadre de `/processes/new` → "crear desde evidencias" | M | 1.1, 1.3 |

### Fase 2 — Importación masiva (Pilar D)
| Épica | Talla | Dep. |
|---|---|---|
| 2.1 Pipeline de importación (hash → extracción/OCR → clasificación → `imported`) | L | 0.2, 0.3 |
| 2.2 Endpoints `/imports` + aprobación por lote | M | 2.1 |
| 2.3 UI importación masiva (drag de lote, progreso, excluir, revisar por lote) | L | 2.2 |

### Fase 3 — Red documental (Pilar B)
| Épica | Talla | Dep. |
|---|---|---|
| 3.1 Tablas `knowledge_objects` + `document_relations` | M | 0.1 |
| 3.2 Pipeline semántico (entidades → normalización → matching → candidatas) | XL | 0.2, 3.1 |
| 3.3 Endpoints relaciones (listar/confirmar/rechazar/editar/merge) | M | 3.1 |
| 3.4 UI confirmación de relaciones (agrupada, confianza, duplicados, red en vivo) | XL | 3.3 |
| 3.5 Ficha conectada: relacionados + análisis de impacto | L | 3.3 |

### Fase 4 — Tyto, el asistente (Pilar C) — el diferencial que se vende
| Épica | Talla | Dep. |
|---|---|---|
| 4.1 `document_chunks` + embeddings al aprobar versión vigente | L | 0.2, 0.1 |
| 4.2 `TytoQueryService`: filtrar aprobados → recuperar → expandir por relaciones → componer + citar | XL | 4.1, 3.x |
| 4.3 Niveles de confianza (🟢🟡🔴) + verificación "hay fuentes" | M | 4.2 |
| 4.4 Endpoints `/tyto/query` + `/tyto/feedback` + tests críticos approved-only | M | 4.2 |
| 4.5 UI chat Tyto (tarjeta de respuesta, piezas, citas, reportar) | L | 4.4 |
| 4.6 Portal ciudadano (variante simplificada para intendencias) | M | 4.5 |

### Fase 5 — Cierre de gobernanza y panel
| Épica | Talla | Dep. |
|---|---|---|
| 5.1 Doble aprobación / circuito configurable por carpeta + liberar a otro aprobador | M | — |
| 5.2 "Cómo usa Tyto esta carpeta" (ponderación, tipo doc por defecto) | M | 4.x |
| 5.3 Panel de control con KPIs (incl. "más consultados por Tyto", preguntas sin respuesta) | M | 4.x |

**Camino crítico al diferencial comercial:** 0.1 → 0.2 → (1.x evidencias) → 3.1/3.2 (relaciones) → 4.1/4.2 (Tyto). La importación (Fase 2) puede ir en paralelo a la 1, y es el mayor argumento de venta para clientes con documentación existente.

**MVP demostrable más corto** (si hay que mostrar el diferencial antes): 0.2 → 4.1 (chunks/embeddings sobre lo ya aprobado) → 4.2/4.4/4.5 (Tyto básico citando fuentes, **sin** expansión por relaciones todavía). Da "preguntale a Tyto y responde solo sobre lo aprobado, citando versión y fecha" — el núcleo del pitch — reusando todo lo que ya está aprobado en el sistema. La red (Fase 3) lo enriquece después con la composición multi-pieza.

---

## 6. Riesgos / decisiones abiertas a confirmar con producto
1. **Qué evidencia dispara nueva versión** vs. solo se adjunta (pregunta abierta del modelo conceptual §9).
2. **Versionado de la red** cuando cambia un activo del que dependen otros.
3. **Estrategia de embeddings**: proveedor, costo, y si se indexa solo aprobados (recomendado por gobernanza) o también para sugerir relaciones en importación.
4. **OCR**: cloud (Google Vision/Textract) vs. local (Tesseract) — impacta costo y privacidad.
5. **Formalizar migraciones** (Alembic) antes de las tablas grandes para no romper prod.
6. **Tipos documentales**: confirmar el catálogo cerrado del Blueprint antes de Fase 0.3.
