# Roles operativos y permisos por carpeta — Documentación de implementación

---

## 1. Objetivo

Se agregó una **segunda capa de permisos** basada en **roles operativos**, configurable por workspace.

- **Roles de sistema** (preexistentes): `owner`, `admin`, `approver`, `creator`, `viewer`
  → Definen **qué puede hacer** un usuario en la plataforma.

- **Roles operativos** (nuevos): ej. Pistero, Cajero, Administración, Jefe de pista, Gerencia
  → Definen **en qué parte de la estructura de carpetas** puede hacerlo.

**Permiso efectivo = rol de sistema + acceso operativo a la carpeta**

---

## 2. Modelo de datos

### 2.1 Tablas nuevas

#### `operational_roles`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | VARCHAR(36) PK | UUID |
| workspace_id | VARCHAR(36) FK | Workspace al que pertenece |
| name | VARCHAR(200) | Nombre visible (ej. "Pistero") |
| slug | VARCHAR(100) | Slug normalizado (ej. "pistero") |
| description | TEXT | Descripción opcional |
| is_active | BOOLEAN | Si está activo (default true) |
| created_at | DATETIME | Fecha de creación |
| updated_at | DATETIME | Última actualización |

#### `user_operational_roles`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | VARCHAR(36) PK | UUID |
| workspace_membership_id | VARCHAR(36) FK | Membership del usuario en el workspace |
| operational_role_id | VARCHAR(36) FK | Rol operativo asignado |
| assigned_at | DATETIME | Fecha de asignación |
| assigned_by | VARCHAR(36) FK NULL | Quién lo asignó |

#### `folder_permissions`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | VARCHAR(36) PK | UUID |
| folder_id | VARCHAR(36) FK | Carpeta restringida |
| operational_role_id | VARCHAR(36) FK | Rol operativo con acceso |
| created_at | DATETIME | Fecha de creación |

### 2.2 Columna nueva en tabla existente

#### `folders.inherits_permissions`

- Tipo: `BOOLEAN`, default `TRUE`
- Si es `true`, la carpeta hereda los permisos de su padre.
- Si es `false`, la carpeta usa su propia lista de `folder_permissions`.

### 2.3 Modelos SQLAlchemy

Archivo: `process_ai_core/db/models.py`

- `OperationalRole` — con relaciones a `Workspace`, `UserOperationalRole`, `FolderPermission`.
- `UserOperationalRole` — con relaciones a `WorkspaceMembership` y `OperationalRole`.
- `FolderPermission` — con relaciones a `Folder` y `OperationalRole`.
- `Folder` — se agregó campo `inherits_permissions` y relación `folder_permissions`.
- `Workspace` — se agregó relación `operational_roles`.
- `WorkspaceMembership` — se agregó relación `user_operational_roles`.

### 2.4 Migración

Archivo: `tools/migrate_add_operational_roles.py`

Script ejecutable que crea las 3 tablas nuevas y agrega la columna `inherits_permissions` a `folders`. Idempotente (usa `IF NOT EXISTS`).

---

## 3. Lógica de autorización

Archivo: `process_ai_core/db/permissions.py`

### 3.1 Helpers internos

| Función | Descripción |
|---------|-------------|
| `_is_superadmin(session, user_id)` | True si el usuario tiene rol `superadmin` en cualquier workspace |
| `_get_user_system_role_name(session, user_id, workspace_id)` | Nombre del rol de sistema del usuario en el workspace |
| `_get_user_operational_role_ids(session, user_id, workspace_id)` | Set de IDs de roles operativos asignados al usuario |
| `_get_folder_allowed_operational_role_ids(session, folder_id)` | Set de IDs de roles operativos que pueden acceder a la carpeta (resuelve herencia) |
| `_has_folder_access_by_operational_roles(session, user_id, workspace_id, folder_id)` | True si el usuario tiene al menos un rol operativo que coincide con los de la carpeta |

### 3.2 Helpers públicos

Estas son las funciones que se invocan desde los endpoints:

#### `can_view_folder(session, user_id, workspace_id, folder_id) → bool`

Verifica si el usuario puede **ver/acceder** a documentos en una carpeta.

#### `can_create_in_folder(session, user_id, workspace_id, folder_id) → bool`

Verifica si el usuario puede **crear/editar** documentos en una carpeta.

#### `can_approve_in_folder(session, user_id, workspace_id, folder_id) → bool`

Verifica si el usuario puede **aprobar/rechazar** documentos en una carpeta.

### 3.3 Flujo de resolución (los 3 helpers siguen la misma lógica)

```
1. ¿Es superadmin? → TRUE (bypass total)
2. ¿Es owner o admin del workspace? → TRUE (bypass por rol de sistema)
3. ¿No es miembro del workspace? → FALSE
4. ¿Tiene el permiso de sistema necesario? (documents.view / documents.create / documents.approve)
   No → FALSE
5. Resolver permisos de la carpeta:
   a. Si la carpeta tiene inherits_permissions=false → usar sus folder_permissions
   b. Si hereda → subir al padre, repetir
   c. Si llega a la raíz heredando → sin restricción (cualquier miembro puede acceder)
   d. Detección de ciclos: si se visita un folder_id ya visto → FALSE (protección)
6. Si la carpeta no tiene restricciones (set vacío) → TRUE
7. Si algún rol operativo del usuario está en los permitidos → TRUE
8. Caso contrario → FALSE
```

### 3.4 Reglas de negocio

- **Owner y Admin**: acceso total a todas las carpetas, sin importar roles operativos.
- **Superadmin**: acceso total global (no requiere membership en el workspace específico).
- **Múltiples roles por usuario**: combinación OR (si *alguno* de sus roles tiene acceso → puede acceder).
- **Herencia de carpetas**: si `inherits_permissions = true`, la carpeta usa los permisos del ancestro más cercano que tenga `inherits_permissions = false`.
- **Carpeta raíz sin restricción**: si toda la cadena hereda y la raíz no tiene permisos explícitos, se considera que no hay restricción (todos los miembros tienen acceso).

---

## 4. API Backend

### 4.1 Endpoints nuevos — Roles operativos

Archivo: `api/routes/operational_roles.py`

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/workspaces/{id}/operational-roles` | Listar roles operativos del workspace | JWT (miembro) |
| POST | `/api/v1/workspaces/{id}/operational-roles` | Crear rol operativo | JWT (owner/admin) |
| PUT | `/api/v1/operational-roles/{id}` | Actualizar rol operativo | JWT (owner/admin) |
| DELETE | `/api/v1/operational-roles/{id}` | Eliminar rol operativo | JWT (owner/admin) |
| POST | `/api/v1/workspace-memberships/{id}/operational-roles` | Asignar roles operativos a un miembro | JWT (owner/admin) |
| DELETE | `/api/v1/workspace-memberships/{id}/operational-roles/{role_id}` | Quitar rol operativo de un miembro | JWT (owner/admin) |

### 4.2 Endpoints nuevos — Permisos de carpeta

Archivo: `api/routes/folders.py`

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/folders/{id}/permissions` | Obtener config de permisos de carpeta | JWT (miembro) |
| PUT | `/api/v1/folders/{id}/permissions` | Configurar permisos de carpeta | JWT (owner/admin) |

### 4.3 Endpoint nuevo — Miembros del workspace

Archivo: `api/routes/workspaces.py`

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/workspaces/{id}/members` | Listar miembros con sus roles de sistema y operativos | JWT (miembro) |

### 4.4 Endpoints existentes modificados — Verificación de acceso a carpeta

Todos los endpoints de `api/routes/documents.py` que tienen autenticación JWT ahora verifican adicionalmente el acceso a la carpeta del documento:

| Endpoint | Verificación agregada |
|----------|----------------------|
| `GET /documents` (listar) | Filtra resultados por `can_view_folder` |
| `GET /documents/pending-approval` | Filtra por `can_approve_in_folder` — migrado de query param a JWT |
| `GET /documents/to-review` | Filtra por `can_view_folder` — migrado de query param a JWT |
| `GET /documents/{id}` | `can_view_folder` |
| `PUT /documents/{id}` | `can_view_folder` + `can_create_in_folder` si se cambia carpeta — agregado auth JWT |
| `DELETE /documents/{id}` | `can_view_folder` |
| `GET /documents/{id}/process` | `can_view_folder` — agregado auth JWT |
| `GET /documents/{id}/runs` | `can_view_folder` — agregado auth JWT |
| `POST /documents/{id}/runs` | `can_create_in_folder` |
| `PUT /documents/{id}/content` | `can_create_in_folder` — agregado auth JWT |
| `GET /documents/{id}/editable` | `can_view_folder` |
| `PUT /documents/{id}/editable` | `can_create_in_folder` |
| `POST /documents/{id}/upload-editor-image` | `can_create_in_folder` |
| `POST /documents/{id}/patch` | `can_create_in_folder` |
| `POST /documents/{id}/versions/{vid}/submit` | Migrado `user_id` de body a JWT |

Archivo: `api/routes/validations.py`

| Endpoint | Verificación agregada |
|----------|----------------------|
| `POST /documents/{id}/validate/approve` | `can_approve_in_folder` |
| `POST /documents/{id}/validate/reject` | `can_approve_in_folder` |
| `POST /validations/{id}/approve` | `can_approve_in_folder` |
| `POST /validations/{id}/reject` | `can_approve_in_folder` |

Archivo: `api/routes/process_runs.py`

| Endpoint | Verificación agregada |
|----------|----------------------|
| `POST /process-runs` | `can_create_in_folder` |

### 4.5 Registro del router

Archivo: `api/main.py` — se agregó `app.include_router(operational_roles.router)`.

---

## 5. API Frontend (TypeScript)

Archivo: `ui/lib/api.ts`

### 5.1 Interfaces nuevas

- `OperationalRoleResponse` — respuesta de rol operativo
- `WorkspaceMember` — miembro del workspace con roles de sistema y operativos
- `FolderPermissionsResponse` — permisos de una carpeta (inherits_permissions + lista de role_ids)

### 5.2 Funciones nuevas

| Función | Descripción |
|---------|-------------|
| `listOperationalRoles(workspaceId)` | Listar roles operativos |
| `createOperationalRole(workspaceId, data)` | Crear rol operativo |
| `updateOperationalRole(roleId, data)` | Actualizar rol operativo |
| `deleteOperationalRole(roleId)` | Eliminar rol operativo |
| `getWorkspaceMembers(workspaceId)` | Listar miembros del workspace |
| `assignOperationalRolesToMembership(membershipId, roleIds)` | Asignar roles a miembro |
| `getFolderPermissions(folderId)` | Obtener permisos de carpeta |
| `updateFolderPermissions(folderId, data)` | Configurar permisos de carpeta |

### 5.3 Funciones corregidas (auth mejorada)

Las siguientes funciones fueron actualizadas para enviar `Authorization: Bearer <token>` en vez de pasar `user_id` como query param o no enviar auth:

- `listDocumentsPendingApproval` — migrado de query param a JWT
- `listDocumentsToReview` — migrado de query param a JWT
- `updateDocument` — agregado Authorization header
- `getDocumentRuns` — agregado Authorization header
- `updateDocumentContent` — agregado Authorization header

### 5.4 Interfaz `Folder` actualizada

Se agregó `inherits_permissions?: boolean` a la interfaz `Folder`.

---

## 6. Frontend (UI)

Archivo: `ui/app/workspace/[id]/settings/page.tsx`

### 6.1 Nuevas tabs en configuración del workspace

#### Tab "Roles operativos"

- Lista los roles operativos del workspace.
- Permite crear nuevos roles (nombre + descripción).
- Permite eliminar roles existentes.
- Indica que la asignación a usuarios se hace desde la tab "Users".

#### Tab "Users" (ampliada)

- Sección "Miembros del workspace" que lista cada miembro con su rol de sistema.
- Botón "Asignar roles operativos" por cada miembro.
- Modal con checkboxes para seleccionar qué roles operativos tiene cada miembro.
- Guarda via `assignOperationalRolesToMembership`.

#### Tab "Carpetas"

- Lista todas las carpetas del workspace.
- Botón "Permisos" por cada carpeta.
- Modal de permisos con:
  - Checkbox "Heredar permisos del padre" (`inherits_permissions`).
  - Si no hereda: checkboxes para cada rol operativo habilitado.
- Guarda via `updateFolderPermissions`.

---

## 7. Correcciones de seguridad aplicadas

Durante la revisión se detectaron y corrigieron vulnerabilidades en endpoints que interactuaban con el nuevo sistema de permisos por carpeta:

### 7.1 Endpoints que no verificaban acceso a carpeta (gaps nuestros)

Todos los endpoints de `documents.py` que ya tenían autenticación JWT pero donde no se había agregado la verificación de carpeta al implementar el feature:

- `DELETE /documents/{id}` — agregado `can_view_folder`
- `GET /documents/{id}/editable` — agregado `can_view_folder`
- `PUT /documents/{id}/editable` — agregado `can_create_in_folder`
- `POST /documents/{id}/upload-editor-image` — agregado `can_create_in_folder`
- `POST /documents/{id}/patch` — agregado `can_create_in_folder`
- `POST /documents/{id}/runs` — agregado `can_create_in_folder`
- `POST /validations/{id}/reject` (ruta legacy) — agregado `can_approve_in_folder`

### 7.2 Endpoints con autenticación insegura que anulaban los permisos por carpeta

- `GET /documents/pending-approval` y `GET /documents/to-review` — recibían `user_id` como query param (spoofeable). Se migró a `Depends(get_current_user_id)` (JWT). Frontend actualizado para enviar Authorization header.
- `PUT /documents/{id}` — no tenía autenticación y permitía mover documentos entre carpetas sin verificar permisos. Se agregó auth JWT + `can_view_folder` (carpeta origen) + `can_create_in_folder` (carpeta destino).
- `GET /documents/{id}/process`, `GET /documents/{id}/runs`, `PUT /documents/{id}/content` — no tenían autenticación. Se agregó auth JWT + verificación de carpeta. Frontend actualizado.
- `POST /documents/{id}/versions/{vid}/submit` — recibía `user_id` del body en vez del JWT. Se migró a `Depends(get_current_user_id)`.

### 7.3 Protección contra ciclos

En `_get_folder_allowed_operational_role_ids`: se implementó detección de ciclos usando un set `visited` para prevenir loops infinitos en caso de jerarquías de carpetas circulares.

### 7.4 Bypass de superadmin

Se implementó `_is_superadmin()` como primera verificación en `can_view_folder`, `can_create_in_folder` y `can_approve_in_folder`, garantizando que los superadmins siempre tengan acceso completo sin depender de roles operativos.

---

## 8. Deuda técnica identificada (no corregida)

Los siguientes son problemas **preexistentes** que no se corrigieron para mantener estabilidad, pero que conviene tener en cuenta:

- `POST /documents/{id}/validate` (crear validación) — sin autenticación.
- `GET /documents/{id}/validations` (listar validaciones) — sin autenticación.
- `POST /validations/{id}/approve` — recibe `user_id` del body en vez de JWT.
- Todo el CRUD de `folders.py` (POST, GET, GET/{id}, PUT/{id}, DELETE/{id}) — sin autenticación.
- `GET /documents/{id}/versions`, `GET /documents/{id}/current-version`, `GET /documents/{id}/audit-log` — sin autenticación.
- `POST /process-runs/{id}/generate-pdf` — sin autenticación.
- `POST /documents/{id}/versions/{vid}/cancel`, `POST /documents/{id}/versions/{vid}/clone` — reciben `user_id` del body.

---

## 9. Archivos modificados (resumen)

### Backend

| Archivo | Cambio |
|---------|--------|
| `process_ai_core/db/models.py` | 3 modelos nuevos + campos y relaciones en Folder, Workspace, WorkspaceMembership |
| `process_ai_core/db/permissions.py` | 8 funciones nuevas para autorización por carpeta |
| `process_ai_core/db/helpers.py` | Parámetro `inherits_permissions` en `update_folder` |
| `api/routes/operational_roles.py` | **Nuevo** — 6 endpoints CRUD de roles operativos |
| `api/routes/folders.py` | 2 endpoints nuevos (permisos) + `inherits_permissions` en respuestas |
| `api/routes/workspaces.py` | 1 endpoint nuevo (listar miembros) |
| `api/routes/documents.py` | 15 endpoints modificados con verificación de carpeta y mejoras de auth |
| `api/routes/validations.py` | 4 endpoints con `can_approve_in_folder` |
| `api/routes/process_runs.py` | 1 endpoint con `can_create_in_folder` |
| `api/main.py` | Registro del router `operational_roles` |
| `api/models/requests.py` | Modelos Pydantic nuevos para roles operativos y permisos de carpeta |
| `tools/migrate_add_operational_roles.py` | **Nuevo** — migración de BD |

### Frontend

| Archivo | Cambio |
|---------|--------|
| `ui/lib/api.ts` | 8 funciones nuevas + 5 funciones corregidas + 3 interfaces nuevas |
| `ui/app/workspace/[id]/settings/page.tsx` | 3 tabs nuevas (Roles operativos, Users ampliada, Carpetas) |
| `ui/app/documents/[id]/page.tsx` | Auth header en llamada a `/process` |
