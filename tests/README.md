
# process-ai-core

**process-ai-core** es el núcleo de inteligencia artificial para generar documentación de procesos
(SOPs, manuales operativos y documentos de gestión) a partir de insumos no estructurados
como audio, video, imágenes y texto.

El objetivo del proyecto es **transformar conocimiento tácito en documentación clara,
usable y auditables**, reduciendo el esfuerzo humano y estandarizando resultados.

---

## ¿Para qué sirve?

Este core está pensado como base para:

- Productos SaaS de documentación de procesos
- Herramientas internas de consultoría y mejora continua
- Automatización de SOPs para empresas sin madurez documental
- Integraciones futuras con Notion, Confluence, SharePoint, Trello, etc.

Casos típicos:
- Un encargado explica un proceso por audio → se genera un procedimiento escrito
- Un video de sistema (Cloud Run, ERP, POS) → se transforma en pasos + capturas
- Notas sueltas + imágenes → documento unificado y consistente

---

## Principios de diseño

- **As-is first**: documenta cómo el proceso se hace hoy, no cómo “debería ser”
- **Audiencia-aware**: el mismo proceso puede generar versiones operativas o de gestión
- **Anti-alucinación**: el modelo solo puede usar activos realmente provistos
- **Trazabilidad**: cada documento queda ligado a inputs, prompt y modelos usados
- **Escalable**: preparado para múltiples clientes, procesos y corridas

---

## Arquitectura general

El sistema se organiza en capas claras:

1. **Ingesta de activos**  
   Archivos crudos (`RawAsset`): audio, video, imagen, texto.

2. **Enriquecimiento**  
   Se extrae texto utilizable:
   - Audio / video → transcripción
   - Imágenes → descripciones / screenshots
   - Texto → normalización

3. **Contexto y catálogos**  
   Preferencias del cliente y del proceso (audiencia, formalidad, nivel de detalle)
   se traducen automáticamente a instrucciones de prompt.

4. **Generación de documento**  
   El modelo genera un JSON estructurado (`ProcessDocument`) que luego se renderiza
   a Markdown y PDF.

5. **Persistencia**  
   Clientes, procesos, corridas y artefactos quedan almacenados para trazabilidad.

---

## Modelo de datos (resumen)

### Client
Representa una organización.

- Defaults de redacción (audiencia, formalidad, nivel de detalle)
- Contexto general del negocio
- Idioma / país

### Process
Un proceso dentro de un cliente.

- Puede sobrescribir defaults del cliente
- Define tipo de proceso (operativo, RRHH, administración, etc.)
- Contexto específico

### Run
Una ejecución concreta del motor.

- Inputs usados (manifest)
- Modelos de IA utilizados
- Hash del prompt generado
- Fecha y modo (operativo / gestión)

### Artifact
Salidas generadas por una Run.

- JSON estructurado
- Markdown
- PDF

---

## Catálogos (modelo A)

Las preferencias no se guardan como texto libre, sino como **valores de catálogo**:

Ejemplos:
- audience: operativo | rrhh | administración | dirección
- detail_level: breve | estándar | detallado | mixto
- formality: baja | media | alta
- process_type: operativo | rrhh | administración | seguridad

Cada opción de catálogo tiene asociado un `prompt_text` que se inyecta automáticamente
en el prompt final.

Ventajas:
- Consistencia
- Fácil evolución
- Base para multilenguaje futuro

---

## Flujo de ejecución

1. Se crea un **Client**
2. Se define un **Process**
3. Se cargan activos (`RawAsset`)
4. Se ejecuta una **Run**
5. El sistema:
   - Enriquece activos
   - Construye el prompt (contexto + catálogos + inputs)
   - Genera JSON del proceso
   - Renderiza Markdown y PDF
6. Se guardan **Artifacts**

---

## Estructura del proyecto

```
process-ai-core/
├── process_ai_core/
│   ├── cli.py                # Entry point CLI
│   ├── engine.py             # Orquestador principal
│   ├── prompts.py            # Prompts base del sistema
│   ├── media.py              # Audio / video / image processing
│   ├── models.py             # Dataclasses (RawAsset, ProcessDocument, etc.)
│   ├── render.py             # Markdown rendering
│   ├── db/
│   │   ├── database.py       # Engine / Session SQLAlchemy
│   │   ├── models_core.py    # Client / Process / Run / Artifact
│   │   └── models_catalog.py # Catálogos
│
├── tools/
│   ├── init_db.py            # Inicialización de DB
│   └── seed_catalog.py       # Seed de catálogos
│
├── input/                    # Inputs crudos
├── output/                   # Outputs generados
├── pyproject.toml
└── README.md
```

---

## Persistencia

- Base de datos: **SQLite**
- ORM: **SQLAlchemy 2.x**
- Objetivo:
  - Simplicidad para el MVP
  - Fácil migración futura a Postgres

La base se puede inspeccionar con herramientas como **DBeaver**.

---

## Requisitos

- Python 3.10+
- OpenAI API Key
- Pandoc (opcional, para PDF)

---

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Variables de entorno:

```bash
export OPENAI_API_KEY=sk-...
```

---

## Estado actual

- ✅ Ingesta de activos
- ✅ Transcripción de audio y video
- ✅ Inferencia de pasos + screenshots
- ✅ Generación Markdown
- ✅ Persistencia con SQLite
- ⏳ Ajustes finos de prompts
- ⏳ UI básica
- ⏳ Versionado de documentos

---

## Visión a futuro

- UI web para carga y revisión
- Comparación entre versiones de procesos
- Multilenguaje real
- Firma / aprobación de procesos
- Integración con herramientas externas

---

## Filosofía

> “El conocimiento no documentado no escala.”

process-ai-core busca capturar conocimiento real,
sin burocracia, sin sobreingeniería,
y convertirlo en algo usable.
