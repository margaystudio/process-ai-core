# Modelos de Datos Genéricos

## Resumen

Los modelos genéricos (`Workspace`/`Document`) reemplazan a `Client`/`Process` y funcionan para múltiples dominios (procesos, recetas, etc.).

## Modelos

### Workspace
Reemplaza a `Client`. Puede ser:
- `organization`: Organización/cliente (para procesos)
- `user`: Usuario individual (para recetas personales)
- `community`: Comunidad/grupo (para recetas compartidas)

### Document
Reemplaza a `Process`. Tiene un campo `domain` que indica el tipo:
- `process`: Documento de proceso
- `recipe`: Receta de cocina
- (futuros dominios)

### User
Nuevo modelo para autenticación/autorización.

### WorkspaceMembership
Relación muchos-a-muchos entre `User` y `Workspace` con roles.

## Uso

### Crear tablas

Las tablas se crean automáticamente al usar los modelos:

```python
from process_ai_core.db.database import Base, get_db_engine

engine = get_db_engine()
Base.metadata.create_all(engine)
```

### Verificar modelos

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import Workspace, Document

with get_db_session() as session:
    workspaces = session.query(Workspace).all()
    documents = session.query(Document).all()
    print(f"Workspaces: {len(workspaces)}")
    print(f"Documents: {len(documents)}")
```

## Uso de los Modelos

### Crear un Workspace de organización

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers import create_organization_workspace

with get_db_session() as session:
    workspace = create_organization_workspace(
        session=session,
        name="Acme Corp",
        slug="acme",
        country="UY",
        business_type="retail",
        default_audience="operativo",
    )
    session.commit()
```

### Crear un Document de proceso

```python
from process_ai_core.db.helpers import create_process_document

with get_db_session() as session:
    document = create_process_document(
        session=session,
        workspace_id=workspace.id,
        name="Recepción de mercadería",
        process_type="operativo",
        audience="pistero",
    )
    session.commit()
```

### Crear un Workspace de usuario (para recetas)

```python
from process_ai_core.db.helpers import create_user_workspace

with get_db_session() as session:
    workspace = create_user_workspace(
        session=session,
        name="Juan Pérez",
        slug="juan-perez",
        preferences={"cuisine": "italian", "diet": "vegetarian"},
    )
    session.commit()
```

## Notas

Los modelos genéricos (`Workspace`, `Document`, `Run`) son los únicos modelos disponibles.
El código debe actualizarse para usar estos modelos en lugar de los antiguos `Client`/`Process`.

## Estructura de Metadata

### Workspace (organization)
```json
{
  "country": "UY",
  "business_type": "retail",
  "language_style": "es_uy_formal",
  "default_audience": "operativo",
  "default_formality": "media",
  "default_detail_level": "estandar",
  "context_text": "..."
}
```

### Workspace (user)
```json
{
  "preferences": {
    "cuisine": "italian",
    "diet": "vegetarian"
  }
}
```

### Document (process)
```json
{
  "process_type": "operativo",
  "audience": "pistero",
  "formality": "baja",
  "detail_level": "bajo",
  "context_text": "..."
}
```

### Document (recipe)
```json
{
  "cuisine": "italian",
  "difficulty": "medium",
  "servings": 4,
  "prep_time": "15 min",
  "cook_time": "20 min"
}
```

