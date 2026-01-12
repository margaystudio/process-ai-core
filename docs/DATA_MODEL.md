# Modelo de Datos - MER (Modelo Entidad-Relación)

## Resumen

El sistema usa una estructura de herencia (Joined Table Inheritance) donde `Process` y `Recipe` heredan de `Document`, permitiendo compartir campos comunes y tener campos específicos por tipo.

## Diagrama de Entidades

```
┌─────────────────────────────────────────────────────────────┐
│                        Workspace                             │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ slug (UNIQUE)                                                │
│ name                                                         │
│ workspace_type (organization|user|community)                │
│ metadata_json (JSON)                                         │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ 1:N
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                        Document                              │
│                    (Clase Base)                              │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ workspace_id (FK → Workspace.id)                            │
│ document_type (process|recipe|...)                           │
│ name                                                         │
│ description                                                  │
│ status (draft|active|archived)                               │
│ folder_id (FK → Folder.id, NULLABLE)                        │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ Herencia (Joined Table)
         │
         ├──────────────────────┬──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│    Process       │  │     Recipe       │  │  (Futuros tipos) │
├──────────────────┤  ├──────────────────┤  │                  │
│ id (PK, FK →     │  │ id (PK, FK →     │  │                  │
│    Document.id)  │  │    Document.id)  │  │                  │
│ audience         │  │ cuisine          │  │                  │
│ detail_level     │  │ difficulty       │  │                  │
│ context_text     │  │ servings         │  │                  │
│                  │  │ prep_time        │  │                  │
│                  │  │ cook_time        │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Folder                                │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ workspace_id (FK → Workspace.id)                             │
│ name                                                         │
│ path                                                         │
│ parent_id (FK → Folder.id, NULLABLE)                        │
│ sort_order                                                   │
│ metadata_json (JSON)                                         │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ 1:N
         │
         ▼
    Document (folder_id)

┌─────────────────────────────────────────────────────────────┐
│                         Run                                  │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ document_id (FK → Document.id)                              │
│ document_type (process|recipe|...)                           │
│ profile                                                      │
│ input_manifest_json (JSON)                                  │
│ prompt_hash                                                  │
│ model_text                                                   │
│ model_transcribe                                             │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ 1:N
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Artifact                               │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ run_id (FK → Run.id)                                        │
│ type (json|md|pdf)                                          │
│ path                                                        │
│ created_at                                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         User                                 │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ email (UNIQUE)                                               │
│ name                                                         │
│ password_hash                                                │
│ metadata_json (JSON)                                        │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ N:M
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                  WorkspaceMembership                         │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ user_id (FK → User.id)                                      │
│ workspace_id (FK → Workspace.id)                            │
│ role (owner|admin|member|viewer)                            │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    CatalogOption                            │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                      │
│ domain (audience|detail_level|language_style|...)          │
│ value                                                        │
│ label                                                        │
│ prompt_text                                                  │
│ is_active                                                    │
│ created_at                                                   │
└─────────────────────────────────────────────────────────────┘
```

## Relaciones

### 1. Workspace → Document (1:N)
- Un workspace puede tener múltiples documentos
- Los documentos pueden ser Process, Recipe, o futuros tipos
- Relación: `workspace.documents` ↔ `document.workspace`

### 2. Document → Process/Recipe (Herencia)
- `Process` y `Recipe` heredan de `Document` usando Joined Table Inheritance
- Comparten campos comunes (id, workspace_id, name, etc.)
- Tienen campos específicos en sus propias tablas
- El campo `document_type` en `Document` actúa como discriminador

### 3. Folder → Document (1:N)
- Una carpeta puede contener múltiples documentos
- Los documentos pueden estar en una carpeta o sin carpeta (folder_id NULL)
- Relación: `folder.documents` ↔ `document.folder`

### 4. Folder → Folder (Auto-referencia, 1:N)
- Las carpetas pueden tener subcarpetas (estructura jerárquica)
- `parent_id` referencia a otra carpeta
- Relación: `folder.children` ↔ `folder.parent`

### 5. Document → Run (1:N)
- Un documento puede tener múltiples ejecuciones (runs)
- Cada run genera nuevos artefactos (JSON, Markdown, PDF)
- Relación: `document.runs` ↔ `run.document`

### 6. Run → Artifact (1:N)
- Un run genera múltiples artefactos (JSON, Markdown, PDF)
- Relación: `run.artifacts` ↔ `artifact.run`

### 7. User ↔ Workspace (N:M)
- Un usuario puede pertenecer a múltiples workspaces
- Un workspace puede tener múltiples usuarios
- La relación se modela a través de `WorkspaceMembership`
- Cada membresía tiene un rol (owner, admin, member, viewer)

## Campos Clave

### Workspace
- **workspace_type**: Determina el tipo de workspace
  - `organization`: Para procesos empresariales
  - `user`: Para recetas personales
  - `community`: Para recetas compartidas

### Document
- **document_type**: Discriminador para herencia polimórfica
  - `process`: Documento de proceso
  - `recipe`: Receta de cocina
  - (futuros tipos: `will`, etc.)

### Process (hereda de Document)
- **audience**: Audiencia del proceso (`operativo` | `gestion`)
- **detail_level**: Nivel de detalle (`breve` | `estandar` | `detallado`)
- **context_text**: Contexto libre del proceso

### Recipe (hereda de Document)
- **cuisine**: Tipo de cocina (`italian`, `mexican`, etc.)
- **difficulty**: Dificultad (`easy` | `medium` | `hard`)
- **servings**: Cantidad de porciones
- **prep_time**: Tiempo de preparación
- **cook_time**: Tiempo de cocción

### Run
- **document_type**: Tipo de documento (se infiere del documento asociado)
- **profile**: Perfil usado para la generación
- **input_manifest_json**: JSON con los inputs de la corrida

### Artifact
- **type**: Tipo de artefacto (`json` | `md` | `pdf`)
- **path**: Ruta relativa al archivo generado

## Ventajas de esta Estructura

1. **Herencia Polimórfica**: Permite agregar nuevos tipos de documentos (ej: `Will`) sin modificar la estructura base
2. **Campos Tipados**: Los campos específicos están en tablas separadas, no en JSON
3. **Queries Eficientes**: Se pueden hacer queries específicas por tipo (solo Process, solo Recipe)
4. **Extensibilidad**: Fácil agregar nuevos tipos sin romper código existente
5. **Separación de Concerns**: Cada dominio (procesos, recetas) puede tener su propia lógica

## Ejemplo de Uso

### Crear un Process
```python
process = Process(
    workspace_id=workspace.id,
    folder_id=folder.id,
    document_type="process",
    name="Recepción de mercadería",
    audience="operativo",
    detail_level="estandar",
    context_text="Proceso para recepción en depósito"
)
```

### Crear un Recipe
```python
recipe = Recipe(
    workspace_id=workspace.id,
    folder_id=folder.id,
    document_type="recipe",
    name="Pasta Carbonara",
    cuisine="italian",
    difficulty="medium",
    servings=4,
    prep_time="15 min",
    cook_time="20 min"
)
```

### Query Polimórfica
```python
# Obtener todos los documentos (Process y Recipe)
documents = session.query(Document).all()

# Obtener solo Process
processes = session.query(Process).all()

# Obtener solo Recipe
recipes = session.query(Recipe).all()
```

## Notas de Implementación

- SQLAlchemy maneja automáticamente las JOINs cuando se consulta `Document`
- El campo `document_type` actúa como discriminador para el polimorfismo
- Los campos comunes están en `documents`, los específicos en `processes`/`recipes`
- La relación con `Run` y `Artifact` funciona con cualquier tipo de `Document`



