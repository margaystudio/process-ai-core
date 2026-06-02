# Plan de Implementación — RAG / Asistente de Consulta sobre Procesos

> **Fecha:** 2026-05-28
> **Estado:** Diseño / Fase 2 (post-MVP). El MVP vendible NO incluye RAG — ver `docs/CODE_REVIEW_2026-05_MVP_PLAN.md`.
> **Alcance:** Asistente conversacional que responde preguntas sobre los procesos
> **aprobados** de un workspace, citando la fuente.

Este documento está escrito en tres capas: **Arquitecto de Software**, **Product Owner**
y **UX**. Cada sección lo aclara.

---

## 0. Resumen ejecutivo (PO)

**Qué:** un chat que responde "¿cómo recibo mercadería?" o "¿qué hago si el remito no
coincide?" leyendo los procesos documentados de la organización, y **siempre citando de
qué proceso y versión salió la respuesta.**

**Por qué importa (valor de negocio):**
- Es el diferenciador frente a "un editor de documentos". Convierte documentación estática
  en conocimiento consultable al instante.
- Reduce el costo de onboarding: el empleado nuevo le pregunta al asistente, no al encargado.
- Habilita el caso "consultoría + SaaS": el asistente demuestra valor en cada uso.

**Qué NO es (para no sobre-prometer):**
- No inventa procedimientos. Si no hay un proceso aprobado que lo cubra, dice "no lo sé"
  y sugiere documentarlo.
- No reemplaza la validación humana. Responde sobre lo que ya fue aprobado.

**Métrica de éxito del MVP de RAG:**
- ≥80% de preguntas sobre procesos existentes respondidas con la cita correcta.
- 0 casos de "fuga entre workspaces" (responder con datos de otra organización).
- Tiempo de respuesta percibido < 5s (con streaming, la primera palabra < 2s).

---

## 1. Principio rector: la fuente de verdad ya existe

El modelo de datos actual (`process_ai_core/db/models.py`) ya define la fuente correcta
para indexar:

> `DocumentVersion` con `version_status = "APPROVED"` e `is_current = True`.
> El comentario en `models.py:477` ya lo anticipa: *"Solo la última versión APPROVED
> (is_current=TRUE) es la 'verdad' visible para operarios y para RAG."*

**Regla dura:** el RAG **solo** indexa contenido aprobado y vigente. Nunca DRAFT,
IN_REVIEW, REJECTED ni OBSOLETE. Esto es a la vez una decisión de calidad (no responder
con borradores) y de gobernanza (lo que el asistente dice ya pasó por validación humana).

---

## 2. Arquitectura (Arquitecto de Software)

### 2.1 Pila tecnológica propuesta

| Componente | Elección | Justificación |
|---|---|---|
| Vector store | **pgvector** (extensión de Postgres/Supabase) | Ya vamos a estar en Supabase Postgres. Evita sumar otra pieza de infra (Pinecone/Weaviate). Multi-tenancy con el mismo `workspace_id` que el resto. |
| Embeddings | **OpenAI `text-embedding-3-small`** (1536 dim) | Ya usamos OpenAI; buena relación costo/calidad. Abstraer detrás de interfaz para poder cambiar. |
| Generación | **`gpt-4.1-mini`** (mismo que el pipeline) | Consistencia y costo. Subir a un modelo mayor solo si la calidad lo exige. |
| Orquestación | Código propio en `process_ai_core/domains/rag/` | Evitar el peso de LangChain para un pipeline simple y auditable. |

> **Decisión de arquitecto:** abstraer `EmbeddingProvider` y `LLMProvider` detrás de
> interfaces (siguiendo el patrón `AiClient` ya mencionado en el contexto del proyecto).
> No acoplar el RAG a OpenAI directamente.

### 2.2 Nuevas tablas (encajan con el modelo actual)

```
document_chunks
├── id              (PK)
├── workspace_id    (FK workspaces.id, INDEX)   ← aislamiento multi-tenant
├── document_id     (FK documents.id, INDEX)
├── version_id      (FK document_versions.id)    ← qué versión generó el chunk
├── chunk_index     (int)                        ← orden dentro del documento
├── content         (text)                       ← el fragmento de texto
├── content_hash    (string)                     ← para reindexar solo lo que cambió
├── token_count     (int)
├── metadata_json   (text)                       ← {process_name, folder_path, section, audience}
├── embedding       (vector(1536))               ← pgvector
└── created_at

rag_queries   (analítica + mejora continua, NO opcional)
├── id              (PK)
├── workspace_id    (FK, INDEX)
├── user_id         (FK users.id)
├── question        (text)
├── answer          (text)
├── cited_chunk_ids (text / json)               ← trazabilidad de qué se citó
├── latency_ms      (int)
├── feedback        (string, nullable)          ← "useful" | "not_useful" | null
└── created_at
```

> **Por qué `rag_queries` desde el día 1 (PO + Arquitecto):** sin registrar preguntas no
> sabemos qué procesos faltan documentar ni dónde falla el asistente. Es la materia prima
> para mejorar el producto y para el pitch ("estas son las 10 preguntas más frecuentes de
> tu operación"). Cuidar privacidad: es dato del cliente, sujeto al mismo aislamiento.

### 2.3 Pipeline de indexación (ingest → embeddings)

```
[ Aprobación de una DocumentVersion ]
        │  (evento: version_status pasa a APPROVED + is_current=TRUE)
        ▼
[ chunker ]  → divide content_markdown en fragmentos semánticos
        │      (por sección/paso, con solape; objetivo ~300–500 tokens)
        ▼
[ embed ]    → text-embedding-3-small por chunk
        │
        ▼
[ upsert document_chunks ]  (borra chunks de versiones obsoletas del mismo documento)
```

**Disparador (decisión clave):** la indexación se engancha al **evento de aprobación**,
no a un cron. Cuando una versión pasa a APPROVED/is_current, se (re)indexa ese documento y
se borran los chunks de la versión anterior. Esto mantiene el índice siempre coherente con
"la verdad vigente" y evita responder con procesos obsoletos.

**Reindexación:** job idempotente que se puede correr manualmente por workspace (para
backfill inicial y para recuperación). Usa `content_hash` para no re-embeddear lo que no
cambió (control de costos).

### 2.4 Pipeline de consulta (retrieval → generación)

```
[ pregunta del usuario + workspace_id (del JWT, NUNCA del cliente) ]
        ▼
[ embed pregunta ]
        ▼
[ búsqueda vectorial ]  WHERE workspace_id = :ws   ← filtro de tenant SIEMPRE
        │                ORDER BY embedding <=> :q  LIMIT k
        ▼
[ (opcional) filtro por permisos/visibilidad de carpeta y rol ]
        ▼
[ armar prompt con los top-k chunks + instrucción de citar ]
        ▼
[ LLM → respuesta con citas ]  (streaming al cliente)
        ▼
[ registrar en rag_queries ]
```

> **Regla de seguridad innegociable (Arquitecto):** el `workspace_id`/tenant del filtro
> vectorial sale del **contexto de sesión resuelto por margay-workspace** (JWT de Supabase
> verificado vía JWKS + `GET /api/session/context`), jamás de un parámetro del request. Esto
> depende de que la **Etapa 1 del plan MVP (integración con margay-workspace)** esté hecha.
> **El RAG NO se construye antes de cerrar la integración/seguridad multi-tenant** — si no,
> una consulta podría leer chunks de otra estación de servicio. Ver
> `docs/INTEGRACION_MARGAY_WORKSPACE.md`.

### 2.5 Visibilidad por rol (alineado al RBAC existente)

El sistema ya tiene `Folder.metadata_json.permissions` y roles (pistero/encargado/gerencia).
El retrieval debe respetarlo: un pistero no debe recibir chunks de procesos de gerencia.
**Decisión:** filtrar candidatos por las carpetas visibles para el rol del usuario antes
de pasar al LLM. Empezar simple (filtro por carpeta/rol) y refinar después.

### 2.6 Endpoints nuevos (API)

```
POST   /api/v1/workspaces/{id}/rag/query     → {question} → {answer, citations[], query_id}  (streaming)
POST   /api/v1/rag/queries/{query_id}/feedback → {feedback: useful|not_useful}
POST   /api/v1/workspaces/{id}/rag/reindex   → admin: reindexa el workspace (backfill/recuperación)
GET    /api/v1/workspaces/{id}/rag/status    → cobertura: #docs indexados, #chunks, última indexación
```

---

## 3. Experiencia de usuario (UX)

### 3.1 Dónde vive el asistente
- Acceso desde un botón persistente ("Asistente" / ícono de chat) en el layout del
  workspace, no escondido en un submenú. Es una capacidad central, no un extra.
- Panel lateral deslizante (no pantalla completa): el usuario puede leer un proceso y
  preguntar a la vez.

### 3.2 La respuesta SIEMPRE cita la fuente
- Cada respuesta muestra **de qué proceso(s) y versión** salió, como chips clicleables
  que abren el documento en la sección citada.
- **Por qué (UX + confianza):** en un contexto operativo regulado (seguridad, arqueos),
  el usuario necesita poder verificar. La cita convierte "la IA dijo" en "el proceso
  aprobado dice". Sin cita, no hay confianza ni defensa en auditoría.

### 3.3 Manejo honesto del "no sé"
- Si no hay chunks relevantes por encima de un umbral de similitud, el asistente responde:
  *"No encontré un proceso documentado que cubra esto."* y ofrece **"Sugerir documentar
  este proceso"** (crea una nota para el encargado).
- **Por qué (PO):** un "no sé" honesto + acción es más valioso que una respuesta inventada.
  Además alimenta el backlog de documentación (qué falta) — esto es oro para la consultoría.

### 3.4 Streaming y percepción de velocidad
- Respuesta en streaming token a token. Primera palabra < 2s.
- Mientras recupera, mostrar "Buscando en tus procesos…" (no un spinner mudo).

### 3.5 Feedback de un toque
- Pulgar arriba/abajo en cada respuesta → escribe `rag_queries.feedback`.
- **Por qué:** cierra el loop de mejora continua y da una métrica de calidad real, no
  inferida.

### 3.6 Estados vacíos (onboarding)
- Workspace sin procesos aprobados → el chat explica: *"Cuando apruebes tus primeros
  procesos, el asistente podrá responder sobre ellos."* y linkea a crear un proceso.
- Conecta el valor del RAG con la acción de documentar: refuerza el loop del producto.

---

## 4. Plan de entrega por fases

> Precondición global: **Etapa 1 (seguridad multi-tenant) y Etapa 2 (Postgres + pgvector)
> del plan MVP deben estar cerradas.** El RAG se apoya en ambas.

### Fase R0 — Fundaciones (1 semana)
- Habilitar `pgvector` en Supabase.
- Tablas `document_chunks` y `rag_queries` (vía Alembic).
- Interfaces `EmbeddingProvider` / `LLMProvider` en `process_ai_core/domains/rag/`.

### Fase R1 — Indexación (1–1.5 semanas)
- Chunker semántico sobre `content_markdown`.
- Job de embeddings + upsert idempotente (con `content_hash`).
- Enganche al evento de aprobación de versión.
- Endpoint `reindex` + backfill del workspace de Margay.

### Fase R2 — Consulta (1.5 semanas)
- Endpoint `rag/query` con filtro de `workspace_id` desde JWT + streaming.
- Prompt con instrucción estricta de citar y de decir "no sé".
- Registro en `rag_queries`.

### Fase R3 — UI del asistente (1.5 semanas)
- Panel lateral de chat, citas clicleables, estados vacíos, "no sé" + sugerir documentar.
- Feedback de un toque.

### Fase R4 — Visibilidad por rol + calidad (1 semana)
- Filtro de retrieval por carpeta/rol.
- Evaluación con set de preguntas reales de GPU/Margay; ajuste de `k`, chunking y umbral.
- Endpoint `rag/status` (cobertura documental).

**Estimación total RAG:** ~6–7 semanas, encadenable después del MVP.

---

## 5. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Fuga entre workspaces | `workspace_id` desde JWT + test de aislamiento + (a futuro) RLS sobre `document_chunks`. |
| Respuestas inventadas | Umbral de similitud + instrucción de "no sé" + cita obligatoria. |
| Índice desincronizado de la verdad | Indexación atada al evento de aprobación; borrar chunks de versiones obsoletas. |
| Costo de embeddings | `content_hash` para no re-embeddear; `text-embedding-3-small`. |
| Procesos con imágenes/pasos visuales | V1 indexa texto; las capturas se citan vía el documento. Multimodal = futuro. |
| Privacidad de `rag_queries` | Mismo aislamiento por tenant; política de retención a definir con el cliente. |

---

## 6. Definición de "hecho" (PO)

- [ ] El asistente responde solo con procesos APPROVED + is_current del workspace del usuario.
- [ ] Cada respuesta cita proceso + versión, con link a la sección.
- [ ] "No sé" honesto cuando no hay cobertura, con acción de sugerir documentación.
- [ ] Test automatizado de aislamiento entre workspaces en verde.
- [ ] `rag_queries` registra cada consulta con su feedback.
- [ ] Validado con un set real de preguntas de Margay (dogfooding) antes de GPU.
