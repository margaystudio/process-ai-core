# Relación Usuario - Rol

Este documento explica cómo se relacionan los usuarios con los roles en el sistema.

## Estructura de Datos

### Tablas Involucradas

```
┌─────────────┐         ┌──────────────────────┐         ┌─────────────┐
│   User      │         │ WorkspaceMembership  │         │    Role     │
├─────────────┤         ├──────────────────────┤         ├─────────────┤
│ id (PK)     │◀────────│ user_id (FK)         │         │ id (PK)     │
│ email       │         │ workspace_id (FK)    │────────▶│ name        │
│ name        │         │ role_id (FK)          │         │ description │
│ ...         │         │ role (string, DEPREC) │         │ ...         │
└─────────────┘         └──────────────────────┘         └─────────────┘
                                │
                                │
                                ▼
                        ┌─────────────┐
                        │  Workspace  │
                        ├─────────────┤
                        │ id (PK)     │
                        │ name        │
                        │ slug        │
                        │ ...         │
                        └─────────────┘
```

### Modelo `WorkspaceMembership`

La tabla `workspace_memberships` es la **tabla intermedia** que relaciona:
- **Usuario** (`user_id`)
- **Workspace** (`workspace_id`)
- **Rol** (`role_id`)

```python
class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    
    id: str  # UUID
    user_id: str  # FK a users.id
    workspace_id: str  # FK a workspaces.id
    role_id: str  # FK a roles.id (NUEVO - usar este)
    role: str | None  # DEPRECATED - mantener para compatibilidad
    created_at: datetime
```

**Puntos clave**:
- Un usuario puede tener **diferentes roles en diferentes workspaces**
- Un usuario puede pertenecer a **múltiples workspaces**
- El rol es **específico por workspace** (no global)

## Relación Usuario → Rol

### 1. Relación Indirecta (a través de WorkspaceMembership)

```
User (1) ──(N)── WorkspaceMembership (N)──(1)── Role
```

**Ejemplo**:
- Usuario `sdalto@margaystudio.io` (ID: `user-123`)
- Workspace `empresa-abc` (ID: `ws-456`)
- Rol `owner` (ID: `role-789`)

```sql
INSERT INTO workspace_memberships (id, user_id, workspace_id, role_id)
VALUES ('membership-001', 'user-123', 'ws-456', 'role-789');
```

### 2. Cómo Obtener el Rol de un Usuario

#### En un Workspace Específico

```python
from process_ai_core.db.models import WorkspaceMembership, Role

# Obtener membership
membership = session.query(WorkspaceMembership).filter_by(
    user_id=user_id,
    workspace_id=workspace_id,
).first()

if membership:
    # Obtener el rol desde role_id
    role = session.query(Role).filter_by(id=membership.role_id).first()
    role_name = role.name  # "owner", "admin", etc.
```

#### Todos los Roles de un Usuario (en todos los workspaces)

```python
memberships = session.query(WorkspaceMembership).filter_by(
    user_id=user_id
).all()

for membership in memberships:
    role = session.query(Role).filter_by(id=membership.role_id).first()
    workspace = session.query(Workspace).filter_by(id=membership.workspace_id).first()
    print(f"Usuario en {workspace.name}: {role.name}")
```

## Asignar Rol a un Usuario

### Método 1: Helper Function

```python
from process_ai_core.db.helpers import add_user_to_workspace_helper

membership = add_user_to_workspace_helper(
    session=session,
    user_id="user-123",
    workspace_id="ws-456",
    role_name="owner"  # "owner", "admin", "creator", "viewer", "approver"
)
```

### Método 2: API Endpoint

```bash
POST /api/v1/users/{user_id}/workspaces/{workspace_id}/membership?role_name=owner
```

### Método 3: Directamente en la BD

```python
from process_ai_core.db.models import WorkspaceMembership, Role

# Buscar el rol por nombre
role = session.query(Role).filter_by(name="owner").first()

# Crear membership
membership = WorkspaceMembership(
    user_id=user_id,
    workspace_id=workspace_id,
    role_id=role.id,
    role="owner"  # Deprecated, pero mantener para compatibilidad
)
session.add(membership)
session.commit()
```

## Obtener Permisos de un Usuario

Los permisos se obtienen a través del rol:

```python
from process_ai_core.db.permissions import get_user_permissions

# Obtener permisos del usuario en un workspace
permissions = get_user_permissions(
    session=session,
    user_id=user_id,
    workspace_id=workspace_id
)
# Retorna: ["documents.create", "documents.view", "documents.edit", ...]
```

**Flujo interno**:
1. Buscar `WorkspaceMembership` por `user_id` y `workspace_id`
2. Obtener `role_id` del membership
3. Buscar `Role` por `role_id`
4. Obtener `RolePermission` asociados al rol
5. Retornar lista de nombres de permisos

## Ejemplo Completo

### Crear Usuario y Asignar Rol

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import User, Workspace, Role, WorkspaceMembership

with get_db_session() as session:
    # 1. Crear usuario
    user = User(
        email="admin@empresa.com",
        name="Admin Usuario"
    )
    session.add(user)
    session.flush()
    
    # 2. Obtener workspace
    workspace = session.query(Workspace).filter_by(slug="empresa-abc").first()
    
    # 3. Obtener rol "owner"
    role = session.query(Role).filter_by(name="owner").first()
    
    # 4. Crear membership (asignar rol)
    membership = WorkspaceMembership(
        user_id=user.id,
        workspace_id=workspace.id,
        role_id=role.id,
        role="owner"  # Deprecated
    )
    session.add(membership)
    session.commit()
    
    print(f"Usuario {user.email} asignado como {role.name} en {workspace.name}")
```

### Consultar Rol de un Usuario

```python
from process_ai_core.db.database import get_db_session
from process_ai_core.db.models import WorkspaceMembership, Role

with get_db_session() as session:
    # Obtener membership
    membership = session.query(WorkspaceMembership).filter_by(
        user_id="user-123",
        workspace_id="ws-456"
    ).first()
    
    if membership:
        # Obtener rol
        role = session.query(Role).filter_by(id=membership.role_id).first()
        print(f"Rol: {role.name}")  # "owner", "admin", etc.
    else:
        print("Usuario no pertenece a este workspace")
```

## Roles Disponibles

Los roles predefinidos (creados por `tools/seed_permissions.py`):

1. **owner**: Dueño del workspace (todos los permisos)
2. **admin**: Administrador (gestión y aprobación)
3. **approver**: Aprobador (aprobar/rechazar documentos)
4. **creator**: Creador (crear y editar documentos)
5. **viewer**: Visualizador (solo lectura)

## Relación con Permisos

```
User ──(WorkspaceMembership)── Role ──(RolePermission)── Permission
```

**Ejemplo**:
- Usuario tiene rol `owner` en workspace `empresa-abc`
- Rol `owner` tiene permisos: `documents.create`, `documents.view`, `documents.edit`, etc.
- Usuario puede crear, ver y editar documentos en `empresa-abc`

## Consultas Útiles

### Obtener todos los usuarios de un workspace con sus roles

```python
memberships = session.query(WorkspaceMembership).filter_by(
    workspace_id=workspace_id
).all()

for membership in memberships:
    user = session.query(User).filter_by(id=membership.user_id).first()
    role = session.query(Role).filter_by(id=membership.role_id).first()
    print(f"{user.email}: {role.name}")
```

### Obtener todos los workspaces de un usuario con sus roles

```python
memberships = session.query(WorkspaceMembership).filter_by(
    user_id=user_id
).all()

for membership in memberships:
    workspace = session.query(Workspace).filter_by(id=membership.workspace_id).first()
    role = session.query(Role).filter_by(id=membership.role_id).first()
    print(f"{workspace.name}: {role.name}")
```

### Verificar si un usuario tiene un permiso específico

```python
from process_ai_core.db.permissions import get_user_permissions

permissions = get_user_permissions(session, user_id, workspace_id)
has_permission = "documents.create" in permissions
```

## Endpoints API

### Asignar Usuario a Workspace con Rol

```bash
POST /api/v1/users/{user_id}/workspaces/{workspace_id}/membership?role_name=owner
```

### Obtener Rol de Usuario en Workspace

```bash
GET /api/v1/users/{user_id}/role/{workspace_id}
```

### Obtener Todos los Workspaces de un Usuario

```bash
GET /api/v1/users/{user_id}/workspaces
```

## Resumen

1. **Usuario NO tiene rol directo**: El rol se asigna a través de `WorkspaceMembership`
2. **Rol es por workspace**: Un usuario puede tener diferentes roles en diferentes workspaces
3. **WorkspaceMembership es la tabla clave**: Contiene `user_id`, `workspace_id`, y `role_id`
4. **Permisos vienen del rol**: Los permisos se obtienen a través del rol asignado en el workspace
5. **Un usuario puede tener múltiples roles**: Uno por cada workspace al que pertenece
