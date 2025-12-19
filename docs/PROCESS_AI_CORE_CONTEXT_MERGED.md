# CONTEXTO GLOBAL — PROCESS AI CORE

## 1. Visión de negocio

Process AI Core es un **motor de documentación de procesos asistido por IA**.
Su objetivo es transformar **material operativo real** (videos, audios, imágenes, textos)
en **documentación estructurada, validable y reutilizable**, en distintos niveles:

- Operativo (personal de ejecución)
- Gestión / Dirección
- Auditoría (futuro)

El sistema apunta a organizaciones **sin madurez documental**, donde el conocimiento
está distribuido en personas, audios de WhatsApp, grabaciones de pantalla y notas sueltas.

### Problema que resuelve
- Procesos que viven en la cabeza de la gente
- Dificultad para entrenar, auditar o escalar
- Documentación costosa, lenta y obsoleta

### Propuesta de valor
- La documentación **se genera desde la evidencia real**
- No se escribe “desde cero”: se infiere
- Un mismo proceso genera múltiples vistas (operativo / gestión)
- Base sólida para auditorías, BI y mejora continua

---

## 1.1 Caso de negocio — Plataforma de Documentación Inteligente de Procesos Operativos (v1.3)

**Proyecto:** Plataforma SaaS para empresas con múltiples sucursales (estaciones de servicio, retail, franquicias)  
**Autores:** Santiago & Luis — Consultoría Artesanal / Margay (nombre tentativo)

### 1.1.1 Resumen ejecutivo

La mayoría de las empresas con operaciones distribuidas carecen de procesos documentados, ordenados y actualizados, generando:

- Dependencia del conocimiento oral
- Inconsistencias entre sucursales
- Errores operativos frecuentes
- Dificultades para entrenar nuevo personal
- Problemas en auditorías internas y externas
- Pérdidas económicas por fallas repetitivas

La plataforma propuesta permite:

- Capturar procesos de forma simple (texto, fotos, videos, audio)
- Autogenerar documentos profesionales con IA
- Organizar procesos bajo jerarquías y niveles de visibilidad
- Ejecutar auditorías trimestrales
- Registrar acciones correctivas
- Consultar procesos mediante chat (RAG)
- Medir el estado general de la documentación

Enfocado en empresas con múltiples sucursales: estaciones de servicio, cadenas de retail, logística y franquicias, donde la estandarización y el orden operativo son críticos.

### 1.1.2 El problema

**Problemas principales detectados (estaciones de servicio y retail):**

- **No existe documentación formal**: el conocimiento se transmite “de boca en boca”.
- **Variabilidad entre sucursales**: cada encargado trabaja distinto.
- **Errores operativos recurrentes**:
  - recepción incorrecta de mercadería
  - arqueos mal hechos
  - cierres de turno incompletos
  - fallos en procedimientos de seguridad
- **Rotación alta**: cada baja implica reentrenar desde cero.
- **Auditorías deficientes**: no hay evidencia estructurada de revisión/actualizaciones.
- **Dependencia de personas clave**: si se va alguien, cae la calidad operativa.

**Impacto económico:**

- Pérdidas por errores operativos (mermas, diferencias de caja, faltantes)
- Sanciones o riesgos legales (seguridad e higiene)
- Costos altos de entrenamiento
- Dificultad para escalar o franquiciar

### 1.1.3 La solución: documentación + auditoría + consulta (IA)

#### Captura multimodal

El usuario arma un input con:

- Texto
- Fotos
- Videos
- Audios
- Links a sistemas
- Capturas de pantalla

#### Creación asistida por IA

A partir de una descripción simple, la IA devuelve:

- Nombre del proceso
- Área sugerida
- Audiencia
- Visibilidad
- Tags
- Pasos iniciales
- Documento completo (objetivo, alcance, precondiciones, pasos, checklist)

#### Organización jerárquica

- Áreas (Operativa, Administración, etc.)
- Grupos (Recepción, Arqueos, etc.)
- Procesos
- Versiones
- Pasos

#### Visibilidad por rol

Ejemplo:

- **Pisteros:** solo procesos operativos
- **Encargados:** operativos + control
- **Gerencia/dirección:** comerciales, análisis, decisiones
- **Gerencia/dirección:** nosotros cuando asistimos 

#### Auditorías trimestrales

Permite:

- Revisar cada proceso
- Calificarlo (OK / necesita actualización / obsoleto / faltante)
- Registrar hallazgos
- Crear acciones correctivas
- Generar informe automático

#### RAG (consulta tipo chat)

Ejemplos:

- “¿Cómo recibo mercadería?”
- “¿Qué hago si el remito no coincide?”
- “¿Cuáles son los procesos ligados a control de stock?”

#### Trazabilidad y métricas

- Registro de cambios
- Salud documental por área
- Adopción/consultas por usuario
- Acciones pendientes

### 1.1.4 Beneficios

**Operativos**

- Estandarización entre sucursales
- Reducción de errores humanos
- Onboarding más rápido
- Consistencia en auditorías y controles
- Transferencia de conocimiento a la empresa (no al empleado)

**Financieros**

- Menos pérdidas por fallas
- Menor costo de capacitación
- Menos tiempo de supervisión gerencial

**Estratégicos**

- Preparación para franquiciar / escalar
- Base para certificaciones (ISO, seguridad, higiene)
- Inteligencia sobre áreas que requieren intervención

### 1.1.5 Mercado objetivo

**Sectores prioritarios**

- Estaciones de servicio (múltiples razones sociales, alta rotación, alta regulación)
- Retail multitienda (supermercados, farmacias)
- Franquicias
- Logística y distribución
- Alimentos y bebidas (plantas + sucursales)
- Hotelería / gastronomía

**Oportunidad (Uruguay / LATAM)**

- Falta de soluciones locales
- Problema ya entendido por las empresas
- Alta relación costo/beneficio
- Producto exportable sin localización compleja

### 1.1.6 Diferenciadores

- **IA aplicada al problema real**: no es “un chat”; genera procesos, metadata e informes de auditoría.
- **Adaptación a roles y visibilidad**: cada rol ve lo que le corresponde.
- **Auditorías trimestrales incluidas**: parte del ciclo del producto.
- **Timeline multimodal**: captura procesos reales, no solo texto.
- **Arquitectura moderna para SaaS**: Next.js + Supabase + OpenAI, con AiClient desacoplado.

### 1.1.7 Arquitectura técnica (resumen ejecutivo)

- **Frontend:** Next.js
- **Backend:** API Routes (y Supabase Edge Functions opcionales)
- **Base de datos:** Postgres (Supabase)
- **Storage:** Supabase Storage
- **Autenticación:** Supabase Auth
- **IA:** OpenAI (texto, embeddings, visión, audio)
- **Capacidades clave:** multi-organización, multi-rol, RLS (seguridad por filas), escalabilidad automática, abstracción por AiClient.

### 1.1.8 Módulos funcionales

- Gestión de organizaciones y usuarios
- Jerarquía de procesos
- Ingreso de input multimodal
- Generación automática con IA
- Versionado
- Ciclo de auditorías trimestrales
- Acciones correctivas
- Búsqueda avanzada y tags
- RAG (consulta inteligente)
- Métricas / dashboards
- Seguridad, visibilidad, permisos

### 1.1.9 Modelo de negocio

- **Opción 1 — SaaS por suscripción**
  - 3–5 USD por usuario / mes  
  - o por sucursal: 20–60 USD / mes
- **Opción 2 — Servicio híbrido**
  - Plataforma: tarifa fija mensual  
  - Auditoría: tarifa por hora o por proceso revisado
- **Opción 3 — Consultoría premium + SaaS**
  - Onboarding completo para empresas grandes

### 1.1.10 Roadmap resumido

- **MVP (6–8 semanas)**
  - CRUD procesos
  - Timeline básico
  - IA para generar documento
  - Roles y visibilidad
  - Auditorías básicas
- **Versión 1**
  - IA para creación asistida
  - Tags y búsqueda
  - Acciones correctivas
  - Versionado avanzado
- **Versión 2**
  - RAG (chat sobre procesos)
  - Métricas / dashboards
  - Alertas automáticas

### 1.1.11 Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Complejidad técnica | Arquitectura modular + releases iterativas |
| Adopción baja | IA para facilitar documentación + onboarding guiado |
| Seguridad | RLS, separación por organización |
| Calidad de procesos | Auditorías periódicas + seguimiento de acciones |

### 1.1.12 Conclusión

La plataforma resuelve un problema universal en empresas distribuidas: la falta de documentación y control operativo confiable.

La combinación de timeline multimodal, IA generativa, auditorías estructuradas, roles/visibilidad, consultas inteligentes y arquitectura moderna la convierte en un producto único en el mercado local y con potencial regional.

## 2. Modelo de negocio (definido)

### Clientes objetivo
- Empresas medianas
- Operaciones distribuidas (estaciones, plantas, sucursales)
- Bajo nivel de formalización documental

### Oferta
- Setup inicial
- Generación de procesos asistida
- Auditorías periódicas (futuro)
- Acceso SaaS

### Diferencial
No es un “editor de documentos”.
Es un **sistema de inferencia de procesos**.

---

## 3. Arquitectura general

### Flujo principal

1. Usuario carga insumos:
   - Videos (screen recordings, tutoriales reales)
   - Audios
   - Imágenes sueltas (evidencia)
   - Textos

2. Pipeline backend:
   - Ingesta
   - Enriquecimiento
   - Inferencia con LLM
   - Render estructurado (MD / PDF)

3. Outputs:
   - JSON estructurado (fuente de verdad)
   - Markdown
   - PDF

---

## 4. Decisiones clave (NO negociables)

- ❌ El usuario NO asigna pasos manualmente
- ❌ El usuario NO escribe documentación estructurada
- ✅ Los pasos se infieren desde evidencia
- ✅ Las imágenes del video se asignan automáticamente
- ✅ Las imágenes sueltas son evidencia, no pasos
- ✅ El JSON es la fuente de verdad
- ✅ El render es desacoplado del contenido

---

## 5. Tipos de activos

### RawAsset
- audio
- video
- image (evidence)
- text

### EnrichedAsset
- Transcripción
- Referencias normalizadas
- Metadata limpia

---

## 6. Pipeline técnico (detalle)

### ingest.py
- Descubre archivos en input/
- Soporta sidecar JSON
- Genera IDs estables

### media.py
- Transcribe audio
- Extrae audio de video
- Infere pasos desde timestamps
- Genera frames candidatos
- Selecciona mejor frame por paso (IA visión)
- Separa:
  - images_by_step (capturas)
  - evidence_images (imágenes sueltas)

### llm_client.py
- OpenAI SDK
- Whisper / transcripción
- Inferencia de pasos
- Selección de frames
- Generación del documento JSON final

### doc_engine.py
- Build prompt
- Parse JSON → modelos
- Render Markdown según perfil

---

## 7. Perfiles de documento

### Operativo
- Documento corto
- Lenguaje simple
- Lista de pasos
- Enfocado en ejecución

### Gestión
- Documento completo
- Tabla de pasos
- Riesgos, métricas, oportunidades
- Enfocado en control

Los perfiles:
- Controlan estructura
- Controlan títulos
- NO alteran el contenido base

---

## 8. Render de imágenes (definido)

- Las imágenes NO viven dentro del JSON
- El JSON solo referencia
- El render decide ubicación

Estrategia:
- En pasos: links a capturas
- Sección específica de “Capturas del procedimiento”
- Evidencia visual separada

---

## 9. Persistencia / DB

### Uso actual
- Catálogos de prompts
- Clientes
- Procesos

### Tecnología
- SQLAlchemy
- SQLite (dev)
- PostgreSQL (prod)

### Catálogos
Permiten controlar:
- Audiencia
- Formalidad
- Nivel de detalle
- Tipo de proceso
- Estilo de lenguaje

---

## 10. UI (definida conceptualmente)

### Fase 1 (web)

Pantallas:
1. Login
2. Selección de cliente
3. Alta de proceso
4. Carga de insumos
5. Preview del documento
6. Validación humana
7. Export

### Principios de UX
- El usuario NO “arma documentos”
- El usuario valida / corrige
- La IA propone, el humano decide

---

## 11. Reglas para IA (Cursor / LLM)

Cuando trabajes en este repo:
- NO inventes pasos
- NO mezcles evidencia con pasos
- NO rompas compatibilidad de perfiles
- NO acoples UI con inferencia

Siempre:
- JSON primero
- Render después
- Evidencia manda

---

## 12. Estado actual

✔ Pipeline funcional end-to-end
✔ Video → pasos → capturas
✔ Markdown y PDF
✔ Perfiles operativo / gestión
✔ Documentación técnica completa

Próximos pasos:
- UI web
- Versionado de procesos
- Auditoría
- Mobile

---

## 13. Este archivo

Este archivo es:
- Contexto permanente
- Fuente de verdad conceptual
- Debe ser leído por Cursor siempre

Si algo contradice este archivo → este archivo gana.
