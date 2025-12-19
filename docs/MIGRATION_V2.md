# Migración a Modelos V2

## Resumen

Los modelos v2 reemplazan `Client`/`Process` con `Workspace`/`Document` genéricos que funcionan para múltiples dominios (procesos, recetas, etc.).

## Nuevos Modelos

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

## Migración

### Paso 1: Crear tablas

```bash
python tools/migrate_to_v2.py
```

Este script:
1. Crea las nuevas tablas (workspaces, documents, users, etc.)
2. Migra datos de `Client` → `Workspace`
3. Migra datos de `Process` → `Document`
4. Migra datos de `Run` → `RunV2`
5. **NO elimina** las tablas viejas (compatibilidad temporal)

### Paso 2: Verificar migración

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models_v2 import Workspace, Document

with get_db_session() as session:
    workspaces = session.query(Workspace).all()
    documents = session.query(Document).all()
    print(f"Workspaces: {len(workspaces)}")
    print(f"Documents: {len(documents)}")
```

## Uso de los Nuevos Modelos

### Crear un Workspace de organización

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.helpers_v2 import create_organization_workspace

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
from process_ai_core.db.helpers_v2 import create_process_document

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
from process_ai_core.db.helpers_v2 import create_user_workspace

with get_db_session() as session:
    workspace = create_user_workspace(
        session=session,
        name="Juan Pérez",
        slug="juan-perez",
        preferences={"cuisine": "italian", "diet": "vegetarian"},
    )
    session.commit()
```

## Compatibilidad

Los modelos v1 (`Client`, `Process`, `Run`) siguen existiendo y funcionando. El código existente que usa estos modelos seguirá funcionando.

**Recomendación**: Migrar gradualmente el código para usar los nuevos modelos v2.

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

