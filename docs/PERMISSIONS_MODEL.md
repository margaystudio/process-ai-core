# Modelo de Permisos y Autenticación

## Diseño General

El sistema usa un modelo de permisos basado en **Usuario - Rol - Permiso**, con soporte para autenticación externa (OAuth, SSO) en el futuro.

## Estructura de Datos

### User (Usuario)
- `id`: UUID único
- `email`: Email único (usado para login)
- `name`: Nombre completo
- `password_hash`: Hash de contraseña (opcional, si usamos login propio)
- `external_id`: ID del usuario en el sistema externo (OAuth/SSO)
- `auth_provider`: Proveedor de autenticación ("local" | "google" | "microsoft" | "okta" | etc.)
- `metadata_json`: Metadata adicional (avatar, preferencias, etc.)

### Role (Rol)
- `id`: UUID único
- `name`: Nombre del rol (ej: "approver", "creator", "viewer")
- `description`: Descripción del rol
- `workspace_type`: Tipo de workspace donde aplica ("organization" | "user" | "community" | null para global)
- `is_system`: Si es un rol del sistema (no se puede eliminar)
- `metadata_json`: Metadata adicional

### Permission (Permiso)
- `id`: UUID único
- `name`: Nombre del permiso (ej: "documents.approve", "documents.create", "documents.view")
- `description`: Descripción del permiso
- `category`: Categoría del permiso (ej: "documents", "workspaces", "users")
- `metadata_json`: Metadata adicional

### RolePermission (Relación Rol-Permiso)
- `role_id`: FK a Role
- `permission_id`: FK a Permission
- Relación muchos-a-muchos: un rol tiene múltiples permisos, un permiso puede estar en múltiples roles

### WorkspaceMembership (Actualizado)
- `user_id`: FK a User
- `workspace_id`: FK a Workspace
- `role_id`: FK a Role (en lugar de string)
- Mantiene la relación usuario-workspace con un rol específico

## Roles Predefinidos

### Para Workspaces de tipo "organization"
1. **owner**: Dueño del workspace
   - Permisos: todos
2. **admin**: Administrador
   - Permisos: gestionar usuarios, aprobar documentos, crear documentos
3. **approver**: Aprobador
   - Permisos: aprobar/rechazar documentos, ver documentos
4. **creator**: Creador
   - Permisos: crear documentos, editar sus documentos, ver documentos
5. **viewer**: Visualizador
   - Permisos: ver documentos aprobados

### Para Workspaces de tipo "user" o "community"
- Roles similares pero con alcance personal/comunitario

## Permisos Base

### documents.*
- `documents.create`: Crear nuevos documentos
- `documents.view`: Ver documentos
- `documents.edit`: Editar documentos (propios o todos según rol)
- `documents.delete`: Eliminar documentos
- `documents.approve`: Aprobar documentos
- `documents.reject`: Rechazar documentos con observaciones
- `documents.export`: Exportar documentos (PDF, etc.)

### workspaces.*
- `workspaces.view`: Ver workspace
- `workspaces.edit`: Editar configuración del workspace
- `workspaces.manage_users`: Gestionar usuarios del workspace
- `workspaces.manage_folders`: Gestionar estructura de carpetas

### users.*
- `users.view`: Ver usuarios
- `users.manage`: Crear/editar usuarios

## Autenticación Futura

### Campos en User para soportar OAuth/SSO
- `external_id`: ID del usuario en el proveedor externo
- `auth_provider`: Proveedor ("local" | "google" | "microsoft" | "okta" | "auth0")
- `auth_metadata_json`: Metadata del proveedor (tokens, refresh tokens, etc.)

### Flujo de Autenticación (Futuro)
1. Usuario se autentica con proveedor externo
2. Sistema busca usuario por `external_id` + `auth_provider`
3. Si no existe, crea nuevo usuario
4. Si existe, actualiza metadata si es necesario
5. Retorna sesión/token JWT

## Migración desde Modelo Actual

El modelo actual tiene:
- `WorkspaceMembership.role` como string ("owner" | "admin" | "member" | "viewer")

Migración:
1. Crear tablas `roles`, `permissions`, `role_permissions`
2. Crear roles predefinidos
3. Asignar permisos a roles
4. Migrar `WorkspaceMembership.role` (string) a `WorkspaceMembership.role_id` (FK)
5. Mapear roles antiguos a nuevos roles

## Uso en el Código

### Verificar Permisos
```python
def has_permission(session, user_id, workspace_id, permission_name):
    # Obtener membership
    membership = session.query(WorkspaceMembership).filter_by(
        user_id=user_id,
        workspace_id=workspace_id,
    ).first()
    
    if not membership:
        return False
    
    # Obtener rol
    role = membership.role  # Ahora es objeto Role, no string
    
    # Verificar si el rol tiene el permiso
    return any(p.name == permission_name for p in role.permissions)
```

### Endpoints con Verificación de Permisos
```python
@router.post("/documents/{document_id}/approve")
async def approve_document(document_id: str, user_id: str, workspace_id: str):
    if not has_permission(session, user_id, workspace_id, "documents.approve"):
        raise HTTPException(status_code=403, detail="No tiene permisos para aprobar")
    # ...
```


