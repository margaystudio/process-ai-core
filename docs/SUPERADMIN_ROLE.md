# Rol de Superadmin

Este documento explica cómo se maneja el rol de superadmin en el sistema, especialmente cuando no tiene un workspace asociado.

## Problema Actual

El código actual (`api/dependencies.py`) verifica si un usuario es superadmin buscando:

1. Un rol llamado `"superadmin"` con `is_system=True`
2. Si el usuario tiene ese rol en **algún workspace** (a través de `WorkspaceMembership`)

```python
def is_superadmin(user_id: str, session: Session) -> bool:
    # Buscar rol superadmin
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    
    # Verificar si el usuario tiene este rol en algún workspace
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        role_id=superadmin_role.id,
    ).first()
    
    return membership is not None
```

**Problema**: Esto requiere que el superadmin tenga un workspace, lo cual no siempre es deseable.

## Soluciones Posibles

### Opción 1: Workspace "Sistema" (Recomendada)

Crear un workspace especial llamado "Sistema" o "Platform" donde se asignan los superadmins.

**Ventajas**:
- Reutiliza la estructura existente
- No requiere cambios en el modelo de datos
- Permite tener múltiples superadmins fácilmente

**Implementación**:

1. Crear workspace "sistema" al inicializar la BD
2. Crear rol "superadmin" si no existe
3. Asignar usuarios superadmin a ese workspace con rol "superadmin"

```python
# Crear workspace sistema
system_workspace = Workspace(
    slug="sistema",
    name="Sistema",
    workspace_type="system",  # Nuevo tipo
    metadata_json=json.dumps({})
)

# Crear rol superadmin
superadmin_role = Role(
    name="superadmin",
    description="Super administrador del sistema",
    workspace_type=None,  # Global
    is_system=True
)

# Asignar usuario como superadmin
membership = WorkspaceMembership(
    user_id=user_id,
    workspace_id=system_workspace.id,
    role_id=superadmin_role.id
)
```

### Opción 2: Campo en User (Alternativa)

Agregar un campo `is_superadmin` directamente en la tabla `User`.

**Ventajas**:
- Más simple conceptualmente
- No requiere workspace

**Desventajas**:
- Requiere migración de BD
- No reutiliza la estructura de roles/permisos

```python
class User(Base):
    # ...
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
```

### Opción 3: Tabla Separada (Alternativa)

Crear una tabla `superadmins` que liste los usuarios superadmin.

**Ventajas**:
- Separación clara
- Fácil de consultar

**Desventajas**:
- Requiere nueva tabla
- Duplica información

## Implementación Recomendada: Workspace "Sistema"

### 1. Actualizar `seed_permissions.py`

Agregar creación del rol "superadmin":

```python
# Crear rol superadmin
role_superadmin = create_role(
    session=session,
    name="superadmin",
    description="Super administrador del sistema. Puede crear workspaces B2B y gestionar todo.",
    workspace_type=None,  # Global, no específico de workspace
    is_system=True,
)

# Asignar todos los permisos al superadmin
for perm in all_permissions:
    assign_permission_to_role(session, role_superadmin.id, perm.id)
```

### 2. Crear Workspace "Sistema"

```python
def create_system_workspace(session: Session) -> Workspace:
    """Crea el workspace 'sistema' para superadmins."""
    existing = session.query(Workspace).filter_by(slug="sistema").first()
    if existing:
        return existing
    
    workspace = Workspace(
        slug="sistema",
        name="Sistema",
        workspace_type="system",
        metadata_json=json.dumps({
            "description": "Workspace del sistema para superadmins",
            "is_system": True
        })
    )
    session.add(workspace)
    session.flush()
    return workspace
```

### 3. Actualizar `create_super_admin.py`

```python
def create_super_admin():
    """Crea el usuario super admin y lo asigna al workspace sistema."""
    with get_db_session() as session:
        # ... crear usuario ...
        
        # Obtener o crear workspace "sistema"
        system_workspace = create_system_workspace(session)
        
        # Obtener rol "superadmin"
        superadmin_role = session.query(Role).filter_by(name="superadmin").first()
        if not superadmin_role:
            print("❌ Rol 'superadmin' no encontrado.")
            print("   Ejecuta tools/seed_permissions.py primero.")
            return
        
        # Asignar usuario al workspace sistema con rol superadmin
        membership = WorkspaceMembership(
            user_id=user.id,
            workspace_id=system_workspace.id,
            role_id=superadmin_role.id,
            role="superadmin"
        )
        session.add(membership)
        session.commit()
        
        print(f"✅ Usuario asignado como superadmin en workspace 'sistema'")
```

### 4. Actualizar `is_superadmin()` (Opcional)

Si queremos que funcione sin workspace, podemos hacer que busque en el workspace "sistema":

```python
def is_superadmin(user_id: str, session: Session) -> bool:
    """Verifica si un usuario es superadmin."""
    # Buscar rol superadmin
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    
    # Buscar workspace "sistema"
    system_workspace = session.query(Workspace).filter_by(slug="sistema").first()
    if not system_workspace:
        return False
    
    # Verificar si el usuario tiene rol superadmin en workspace sistema
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=system_workspace.id,
        role_id=superadmin_role.id,
    ).first()
    
    return membership is not None
```

## Flujo Completo

```
1. Seed de permisos crea rol "superadmin"
2. Se crea workspace "sistema" (una vez, al inicializar)
3. Usuario se crea (create_super_admin.py)
4. Usuario se asigna al workspace "sistema" con rol "superadmin"
5. is_superadmin() verifica membership en workspace "sistema"
```

## Alternativa: Sin Workspace

Si realmente no queremos usar workspace, podemos modificar `is_superadmin()` para verificar directamente:

```python
def is_superadmin(user_id: str, session: Session) -> bool:
    """Verifica si un usuario es superadmin (sin requerir workspace)."""
    # Opción 1: Buscar rol superadmin en cualquier workspace
    superadmin_role = session.query(Role).filter_by(name="superadmin", is_system=True).first()
    if not superadmin_role:
        return False
    
    # Verificar si tiene el rol en cualquier workspace
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        role_id=superadmin_role.id,
    ).first()
    
    return membership is not None
```

**Nota**: Esta opción sigue requiriendo un workspace, pero puede ser cualquier workspace (no necesariamente "sistema").

## Recomendación Final

**Usar Workspace "Sistema"** porque:
1. Reutiliza la estructura existente
2. Es consistente con el modelo de permisos
3. Permite tener múltiples superadmins fácilmente
4. No requiere cambios en el modelo de datos
5. Es fácil de entender y mantener
