# Arquitectura de Workspaces, Suscripciones y Flujos B2B/B2C

## Resumen Ejecutivo

El sistema necesita soportar dos modelos de negocio distintos:
- **B2B (Organizaciones)**: Para documentación de procesos empresariales
- **B2C (Usuarios individuales)**: Para recetas personales y contenido individual

Cada modelo requiere flujos de alta, gestión y límites diferentes basados en suscripciones.

## Modelo de Datos

### 1. Subscription Plan (Nuevo)

```python
class SubscriptionPlan(Base):
    """
    Plan de suscripción disponible en el sistema.
    """
    id: str
    name: str  # "free", "starter", "professional", "enterprise"
    plan_type: str  # "b2b" | "b2c"
    price_monthly: float
    price_yearly: float
    
    # Límites del plan
    max_users: int | None  # None = ilimitado (solo B2B)
    max_documents: int | None  # None = ilimitado
    max_documents_per_month: int | None
    max_storage_gb: int | None
    features_json: str  # JSON con features habilitadas
    
    is_active: bool
    created_at: datetime
```

### 2. Workspace Subscription (Nuevo)

```python
class WorkspaceSubscription(Base):
    """
    Suscripción activa de un workspace.
    """
    id: str
    workspace_id: str  # FK a Workspace
    plan_id: str  # FK a SubscriptionPlan
    
    status: str  # "active" | "trial" | "expired" | "cancelled"
    current_period_start: datetime
    current_period_end: datetime
    
    # Contadores actuales (para validar límites)
    current_users_count: int
    current_documents_count: int
    current_documents_this_month: int
    current_storage_gb: float
    
    # Metadata
    payment_provider: str | None  # "stripe", "paypal", etc.
    payment_provider_subscription_id: str | None
    
    created_at: datetime
    updated_at: datetime
```

### 3. Workspace Invitation (Nuevo)

```python
class WorkspaceInvitation(Base):
    """
    Invitación para unirse a un workspace (B2B).
    """
    id: str
    workspace_id: str  # FK a Workspace
    invited_by_user_id: str  # FK a User (quien invita)
    
    email: str
    role_id: str  # FK a Role (rol que tendrá al aceptar)
    token: str  # Token único para aceptar invitación
    
    status: str  # "pending" | "accepted" | "expired" | "cancelled"
    expires_at: datetime
    
    accepted_at: datetime | None
    accepted_by_user_id: str | None  # FK a User (quien aceptó)
    
    created_at: datetime
```

### 4. Workspace (Actualizado)

```python
class Workspace(Base):
    # ... campos existentes ...
    
    # Nuevos campos
    subscription_id: str | None  # FK a WorkspaceSubscription (actual)
    owner_user_id: str | None  # FK a User (owner/creador del workspace)
    
    # Metadata adicional
    settings_json: str  # Configuraciones del workspace (B2B: branding, defaults, etc.)
```

## Flujos de Alta

### Flujo B2B (Organizaciones)

```
1. Superadmin crea workspace
   ├─ Tipo: "organization"
   ├─ Asigna plan de suscripción (trial o pagado)
   ├─ Crea WorkspaceSubscription
   └─ Asigna owner_user_id (admin de la organización)

2. Superadmin invita al admin de la organización
   ├─ Crea WorkspaceInvitation
   ├─ Envía email con link de invitación
   └─ Token único con expiración

3. Admin acepta invitación
   ├─ Valida token
   ├─ Crea/actualiza User si no existe
   ├─ Crea WorkspaceMembership con rol "owner" o "admin"
   └─ Redirige a panel de configuración

4. Admin configura workspace
   ├─ Panel de configuración del workspace
   ├─ Invita usuarios adicionales (según límites del plan)
   ├─ Configura defaults (audiencia, idioma, etc.)
   └─ Branding (logo, colores, etc.)

5. Admin gestiona usuarios
   ├─ Lista usuarios del workspace
   ├─ Invita nuevos usuarios
   ├─ Asigna roles
   └─ Valida límites de usuarios según plan
```

### Flujo B2C (Usuarios individuales)

```
1. Usuario se registra
   ├─ Crea cuenta en Supabase
   ├─ Sincroniza con DB local (crea User)
   └─ Redirige a onboarding B2C

2. Onboarding B2C
   ├─ Selecciona plan de suscripción (free, premium, etc.)
   ├─ Crea Workspace de tipo "user"
   ├─ Crea WorkspaceSubscription (trial o pagado)
   ├─ Asocia usuario como owner
   └─ Redirige a configuración personal

3. Configuración personal
   ├─ Preferencias de recetas (cuisine, diet, etc.)
   ├─ Configuración de privacidad
   └─ Listo para usar
```

## Sistema de Límites

### Validación de Límites

```python
def check_workspace_limit(
    session: Session,
    workspace_id: str,
    limit_type: str,  # "users" | "documents" | "storage" | "documents_per_month"
) -> tuple[bool, str | None]:
    """
    Verifica si el workspace puede realizar una acción según su plan.
    
    Returns:
        (allowed: bool, error_message: str | None)
    """
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return False, "Workspace sin suscripción activa"
    
    plan = subscription.plan
    
    if limit_type == "users":
        if plan.max_users and subscription.current_users_count >= plan.max_users:
            return False, f"Límite de usuarios alcanzado ({plan.max_users})"
    
    if limit_type == "documents":
        if plan.max_documents and subscription.current_documents_count >= plan.max_documents:
            return False, f"Límite de documentos alcanzado ({plan.max_documents})"
    
    # ... otros límites ...
    
    return True, None
```

### Actualización de Contadores

```python
def increment_workspace_counter(
    session: Session,
    workspace_id: str,
    counter_type: str,  # "users" | "documents" | "storage"
    amount: int = 1,
):
    """Incrementa un contador del workspace."""
    subscription = get_active_subscription(session, workspace_id)
    if not subscription:
        return
    
    if counter_type == "users":
        subscription.current_users_count += amount
    elif counter_type == "documents":
        subscription.current_documents_count += amount
        # También incrementar contador mensual
        subscription.current_documents_this_month += amount
    # ... otros contadores ...
    
    session.commit()
```

## Roles y Permisos

### Roles del Sistema

1. **superadmin** (sistema)
   - Crear workspaces B2B
   - Asignar planes
   - Invitar admins
   - Ver todos los workspaces

2. **owner** (workspace B2B)
   - Configurar workspace
   - Invitar usuarios
   - Gestionar roles
   - Cambiar plan (según permisos)

3. **admin** (workspace B2B)
   - Similar a owner, pero no puede cambiar plan

4. **creator** (workspace)
   - Crear documentos
   - Editar sus documentos

5. **approver** (workspace)
   - Aprobar/rechazar documentos

6. **viewer** (workspace)
   - Solo lectura

### Permisos Específicos

- `workspaces.create` - Crear workspace (solo superadmin para B2B)
- `workspaces.configure` - Configurar workspace
- `workspaces.invite_users` - Invitar usuarios
- `workspaces.manage_subscription` - Cambiar plan
- `workspaces.view_analytics` - Ver analytics

## Endpoints Propuestos

### Workspaces

- `POST /api/v1/workspaces` - Crear workspace (B2B: solo superadmin, B2C: usuario autenticado)
- `GET /api/v1/workspaces/{workspace_id}` - Obtener workspace
- `PUT /api/v1/workspaces/{workspace_id}` - Actualizar configuración (solo owner/admin)
- `GET /api/v1/workspaces/{workspace_id}/settings` - Obtener configuración
- `PUT /api/v1/workspaces/{workspace_id}/settings` - Actualizar configuración

### Invitaciones (B2B)

- `POST /api/v1/workspaces/{workspace_id}/invitations` - Crear invitación
- `GET /api/v1/workspaces/{workspace_id}/invitations` - Listar invitaciones
- `POST /api/v1/invitations/{invitation_id}/accept` - Aceptar invitación
- `DELETE /api/v1/invitations/{invitation_id}` - Cancelar invitación

### Suscripciones

- `GET /api/v1/subscription-plans` - Listar planes disponibles
- `GET /api/v1/workspaces/{workspace_id}/subscription` - Obtener suscripción actual
- `POST /api/v1/workspaces/{workspace_id}/subscription` - Cambiar plan
- `GET /api/v1/workspaces/{workspace_id}/limits` - Obtener límites y uso actual

### Usuarios del Workspace (B2B)

- `GET /api/v1/workspaces/{workspace_id}/users` - Listar usuarios
- `POST /api/v1/workspaces/{workspace_id}/users/{user_id}` - Agregar usuario (via invitación)
- `PUT /api/v1/workspaces/{workspace_id}/users/{user_id}/role` - Cambiar rol
- `DELETE /api/v1/workspaces/{workspace_id}/users/{user_id}` - Remover usuario

## UI Propuesta

### Panel de Superadmin (B2B)

- Lista de workspaces
- Crear nuevo workspace B2B
- Asignar plan
- Invitar admin
- Ver estadísticas

### Panel de Configuración del Workspace (B2B - Owner/Admin)

- Información general
- Configuración de defaults (audiencia, idioma, etc.)
- Branding (logo, colores)
- Gestión de usuarios (invitar, roles)
- Suscripción (ver plan, cambiar plan)
- Límites y uso actual

### Onboarding B2C

- Registro/Login
- Selección de plan
- Configuración de preferencias
- Listo para usar

## Implementación por Fases

### Fase 1: Modelo de Datos y Backend Básico
1. Crear modelos: SubscriptionPlan, WorkspaceSubscription, WorkspaceInvitation
2. Migración de base de datos
3. Endpoints básicos de suscripciones
4. Sistema de límites básico

### Fase 2: Flujo B2B
1. Panel de superadmin
2. Sistema de invitaciones
3. Panel de configuración de workspace
4. Gestión de usuarios del workspace

### Fase 3: Flujo B2C
1. Onboarding B2C
2. Auto-creación de workspace
3. Configuración personal

### Fase 4: Integración de Pagos
1. Integración con Stripe/PayPal
2. Webhooks de pago
3. Gestión de facturación

## Consideraciones

1. **Seguridad**: Validar permisos en todos los endpoints
2. **Escalabilidad**: Los contadores deben actualizarse eficientemente
3. **Flexibilidad**: El modelo de límites debe ser extensible
4. **UX**: Flujos claros y simples para cada tipo de usuario


