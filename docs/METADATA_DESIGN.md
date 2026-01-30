# Diseño de Metadata: JSON vs Columnas

Este documento analiza el uso actual de `metadata_json` y evalúa si conviene migrar a columnas.

## Uso Actual de `metadata_json`

### Workspace (organization)
```json
{
  "country": "UY",
  "business_type": "estaciones_servicio",
  "language_style": "es_uy_formal",
  "default_audience": "operativo",
  "default_detail_level": "estandar",
  "context_text": "Contexto libre del negocio..."
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

**Nota**: `Process` ya tiene columnas para `audience`, `detail_level`, `context_text`, pero algunos campos están duplicados en metadata_json.

## Análisis: JSON vs Columnas

### Ventajas de JSON

1. **Flexibilidad**
   - Diferentes tipos de workspace/document pueden tener diferentes campos
   - No requiere migraciones cuando se agregan nuevos campos
   - Permite estructuras anidadas

2. **Simplicidad**
   - Un solo campo para toda la metadata
   - Fácil de agregar nuevos campos sin cambios en el schema

3. **Polimorfismo**
   - Workspace puede ser "organization", "user", "community" con diferentes campos
   - Document puede ser "process", "recipe", "will" con diferentes campos

### Desventajas de JSON

1. **Queries y Filtros**
   ```python
   # Con JSON: difícil y lento
   session.query(Workspace).filter(
       Workspace.metadata_json['country'].astext == 'UY'
   ).all()
   
   # Con columnas: fácil y rápido
   session.query(Workspace).filter_by(country='UY').all()
   ```

2. **Indexación**
   - No se puede indexar fácilmente campos dentro de JSON
   - Queries por campos JSON son más lentas

3. **Validación**
   - No hay validación de tipos en la BD
   - Errores solo se detectan en runtime

4. **Performance**
   - Parsing JSON en cada query
   - No se puede hacer JOIN eficiente por campos JSON

5. **Tipado**
   - No hay type hints en Python
   - IDE no puede autocompletar

## Recomendación: Enfoque Híbrido

### Campos Comunes → Columnas

**Workspace (organization)**:
- `country` (String) - usado para filtros
- `business_type` (String) - usado para filtros y contexto
- `language_style` (String) - usado para prompts
- `default_audience` (String) - usado frecuentemente
- `default_detail_level` (String) - usado frecuentemente
- `context_text` (Text) - usado en prompts

**Document (process)**:
- Ya tiene: `audience`, `detail_level`, `context_text` ✅
- Agregar: `process_type` (String) - usado para filtros

**Workspace (user)**:
- Mantener en JSON (campos muy variables: cuisine, diet, allergies, etc.)

### Campos Opcionales/Específicos → JSON

- Preferencias de usuario (muy variables)
- Metadata de pago (estructura compleja)
- Configuraciones avanzadas (pocas veces consultadas)

## Propuesta de Migración

### Fase 1: Agregar Columnas (Sin Romper)

```python
class Workspace(Base):
    # ... campos existentes ...
    
    # Nuevas columnas (nullable para compatibilidad)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    business_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    language_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_audience: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_detail_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Mantener metadata_json para campos opcionales
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
```

### Fase 2: Migrar Datos

```python
def migrate_workspace_metadata_to_columns(session: Session):
    """Migra datos de metadata_json a columnas."""
    workspaces = session.query(Workspace).all()
    for ws in workspaces:
        if not ws.metadata_json:
            continue
        
        meta = json.loads(ws.metadata_json)
        
        # Migrar campos comunes
        if 'country' in meta:
            ws.country = meta['country']
        if 'business_type' in meta:
            ws.business_type = meta['business_type']
        # ... etc
        
        # Limpiar metadata_json (solo dejar campos opcionales)
        remaining_meta = {
            k: v for k, v in meta.items()
            if k not in ['country', 'business_type', 'language_style', ...]
        }
        ws.metadata_json = json.dumps(remaining_meta)
    
    session.commit()
```

### Fase 3: Actualizar Helpers

```python
def create_organization_workspace(
    session: Session,
    name: str,
    slug: str,
    country: str = "UY",
    business_type: str = "",
    language_style: str = "es_uy_formal",
    default_audience: str = "operativo",
    context_text: str = "",
) -> Workspace:
    """Crea workspace usando columnas en lugar de JSON."""
    workspace = Workspace(
        slug=slug,
        name=name,
        workspace_type="organization",
        country=country,
        business_type=business_type,
        language_style=language_style,
        default_audience=default_audience,
        context_text=context_text,
        metadata_json="{}",  # Solo para campos opcionales
    )
    session.add(workspace)
    return workspace
```

## Comparación de Queries

### Antes (JSON)
```python
# Filtro por país
workspaces = session.query(Workspace).filter(
    Workspace.metadata_json['country'].astext == 'UY'
).all()

# Filtro por tipo de negocio
workspaces = session.query(Workspace).filter(
    Workspace.metadata_json['business_type'].astext == 'estaciones_servicio'
).all()
```

### Después (Columnas)
```python
# Filtro por país (indexado, rápido)
workspaces = session.query(Workspace).filter_by(country='UY').all()

# Filtro por tipo de negocio (indexado, rápido)
workspaces = session.query(Workspace).filter_by(business_type='estaciones_servicio').all()

# Filtro combinado (eficiente)
workspaces = session.query(Workspace).filter(
    Workspace.country == 'UY',
    Workspace.business_type == 'estaciones_servicio'
).all()
```

## Recomendación Final

### ✅ Migrar a Columnas

**Workspace (organization)**:
- `country`, `business_type`, `language_style`, `default_audience`, `default_detail_level`, `context_text`

**Document (process)**:
- Ya tiene `audience`, `detail_level`, `context_text` ✅
- Agregar `process_type` si no existe

### ❌ Mantener en JSON

**Workspace (user)**:
- Preferencias muy variables (cuisine, diet, allergies, etc.)

**User**:
- Preferencias personales (avatar_url, theme, etc.)

**WorkspaceSubscription**:
- `payment_metadata_json` (estructura compleja, pocas veces consultada)

## Plan de Implementación

1. **Agregar columnas nullable** (no rompe código existente)
2. **Crear migración de datos** (mover de JSON a columnas)
3. **Actualizar helpers** (usar columnas en lugar de JSON)
4. **Actualizar queries** (usar columnas para filtros)
5. **Limpiar metadata_json** (solo campos opcionales)

## Conclusión

**Para campos comunes y frecuentemente consultados**: Usar columnas
- Mejor performance
- Queries más fáciles
- Indexación
- Validación de tipos

**Para campos opcionales y variables**: Mantener JSON
- Flexibilidad
- Sin migraciones constantes
- Estructuras anidadas

El enfoque híbrido es el mejor balance entre flexibilidad y performance.
