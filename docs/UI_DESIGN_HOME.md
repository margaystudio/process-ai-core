# Diseño de Pantallas de Inicio según Rol

## Resumen

Cada usuario verá una pantalla de inicio diferente según su rol en el workspace seleccionado. La pantalla se determina automáticamente al cargar la aplicación.

## Flujo de Determinación de Rol

1. Usuario selecciona un workspace (en el header)
2. Sistema obtiene el rol del usuario en ese workspace (`GET /api/v1/users/{user_id}/role/{workspace_id}`)
3. Según el rol, se muestra la pantalla correspondiente

## Pantallas por Rol

### 1. Pantalla para Aprobadores (owner, admin, approver)

**Ruta:** `/dashboard/approval-queue` o `/` (si es aprobador)

**Componentes:**
- **Header**: "Cola de Aprobación" o "Documentos Pendientes"
- **Filtros** (opcional):
  - Por fecha
  - Por carpeta
- **Lista de documentos pendientes**:
  - Card por documento con:
    - Nombre del documento
    - Carpeta donde está ubicado
    - Fecha de creación
    - Última versión generada
    - Botón "Ver Detalles" → abre modal o navega a página de detalle
  - Orden: más antiguos primero (FIFO)
- **Acciones en cada card**:
  - Botón "Aprobar" (verde) → confirma y aprueba
  - Botón "Rechazar" (rojo) → abre modal con:
    - Textarea para observaciones (requerido)
    - Botón "Enviar a Revisión"
- **Modal de Detalle** (al hacer clic en "Ver Detalles"):
  - Preview del PDF (iframe o link)
  - Información del documento
  - Botones de acción (Aprobar/Rechazar) también aquí

**Estados:**
- Vacío: "No hay documentos pendientes de aprobación"
- Cargando: Skeleton loaders
- Error: Mensaje de error con botón de reintentar

---

### 2. Pantalla para Creadores (creator)

**Ruta:** `/dashboard/to-review` o `/` (si es creador)

**Componentes:**
- **Header**: "Documentos a Revisar" o "Correcciones Pendientes"
- **Filtros** (opcional):
  - Por fecha de rechazo
- **Lista de documentos rechazados**:
  - Card por documento con:
    - Nombre del documento
    - Carpeta
    - Fecha de rechazo
    - Última observación (preview, truncada)
    - Botón "Corregir" → navega a página de corrección
  - Orden: más recientes primero
- **Acciones en cada card**:
  - Botón "Corregir" → navega a página de corrección
- **Página de Corrección** (`/documents/{id}/correct`):
  - **Sección de Observaciones**:
    - Muestra las observaciones del rechazo
    - Fecha y usuario que rechazó
  - **Sección de Acciones de Corrección**:
    - **Opción 1: Patch por IA**
      - Textarea para observaciones adicionales (opcional)
      - Botón "Aplicar Patch por IA"
      - Loading state mientras procesa
    - **Opción 2: Edición Manual**
      - Editor JSON (con syntax highlighting)
      - Botón "Guardar Cambios"
      - Preview del Markdown generado
    - **Opción 3: Regenerar con Nuevos Archivos**
      - Formulario de carga de archivos
      - Campo para notas de revisión
      - Botón "Regenerar Documento"
  - **Sección de Preview**:
    - Vista del documento actual (PDF o Markdown)
    - Versiones anteriores (si hay)

**Estados:**
- Vacío: "No hay documentos a revisar"
- Cargando: Skeleton loaders
- Error: Mensaje de error

---

### 3. Pantalla para Viewers (viewer)

**Ruta:** `/dashboard/view` o `/` (si es viewer)

**Componentes:**
- **Header**: "Documentos Aprobados"
- **Filtros**:
  - Por tipo de documento
  - Por carpeta
  - Buscador por nombre
- **Lista de documentos aprobados**:
  - Card por documento con:
    - Nombre
    - Tipo
    - Carpeta
    - Fecha de aprobación
    - Versión actual
    - Botón "Ver" → abre PDF en nueva pestaña o modal
  - Orden: más recientes primero
- **Sin acciones de edición**: Solo lectura

**Estados:**
- Vacío: "No hay documentos aprobados"
- Cargando: Skeleton loaders

---

## Componentes Compartidos

### 1. DocumentCard
Componente reutilizable para mostrar un documento en una lista.

**Props:**
- `document`: Document object
- `onView`: Callback al hacer clic en "Ver"
- `onApprove`: Callback para aprobar (solo aprobadores)
- `onReject`: Callback para rechazar (solo aprobadores)
- `onCorrect`: Callback para corregir (solo creadores)
- `showActions`: boolean para mostrar/ocultar acciones

### 2. RejectModal
Modal para rechazar un documento con observaciones.

**Props:**
- `documentId`: ID del documento
- `onReject`: Callback con observaciones
- `onClose`: Callback para cerrar

### 3. ApprovalQueue
Componente principal para la cola de aprobación.

### 4. ToReviewList
Componente principal para la lista de documentos a revisar.

### 5. ApprovedDocumentsList
Componente principal para la lista de documentos aprobados.

---

## Navegación

### Estructura de Rutas

```
/ (home)
  ├─ /dashboard (redirige según rol)
  │   ├─ /approval-queue (aprobadores)
  │   ├─ /to-review (creadores)
  │   └─ /view (viewers)
  ├─ /documents/[id] (detalle/edición)
  ├─ /documents/[id]/correct (corrección)
  └─ /workspace (gestión de workspace)
```

### Lógica de Redirección

```typescript
// En el componente principal o layout
useEffect(() => {
  const role = userRole; // obtenido del contexto
  if (role === 'owner' || role === 'admin' || role === 'approver') {
    router.push('/dashboard/approval-queue');
  } else if (role === 'creator') {
    router.push('/dashboard/to-review');
  } else if (role === 'viewer') {
    router.push('/dashboard/view');
  }
}, [userRole]);
```

---

## Estados y Loading

### Estados de la Aplicación

1. **Determinando rol**: Loading spinner mientras se obtiene el rol
2. **Cargando documentos**: Skeleton loaders en las cards
3. **Vacío**: Mensaje amigable sin documentos
4. **Error**: Mensaje de error con opción de reintentar
5. **Éxito**: Lista de documentos renderizada

### Estados de Acciones

- **Aprobar**: Loading en el botón mientras se procesa
- **Rechazar**: Modal con loading al enviar
- **Patch por IA**: Loading con mensaje "Procesando con IA..."
- **Edición Manual**: Guardado con loading

---

## Consideraciones de UX

1. **Feedback inmediato**: Todas las acciones muestran loading states
2. **Confirmaciones**: Acciones destructivas (rechazar) requieren confirmación
3. **Notificaciones**: Toast notifications para acciones exitosas/fallidas
4. **Navegación intuitiva**: Breadcrumbs y botones de "Volver"
5. **Responsive**: Las cards se adaptan a móvil (stack vertical)
6. **Accesibilidad**: Labels, ARIA, keyboard navigation

---

## Integración con API

### Endpoints Necesarios

1. `GET /api/v1/users/{user_id}/role/{workspace_id}` - Obtener rol
2. `GET /api/v1/documents/pending-approval` - Lista para aprobadores
3. `GET /api/v1/documents/to-review` - Lista para creadores
4. `GET /api/v1/documents?status=approved` - Lista para viewers
5. `POST /api/v1/validations/documents/{id}/approve` - Aprobar
6. `POST /api/v1/validations/documents/{id}/reject` - Rechazar
7. `POST /api/v1/documents/{id}/patch` - Patch por IA
8. `PUT /api/v1/documents/{id}/content` - Edición manual

---

## Próximos Pasos

1. Crear componentes base (DocumentCard, RejectModal)
2. Implementar ApprovalQueue
3. Implementar ToReviewList
4. Implementar ApprovedDocumentsList
5. Crear página de corrección
6. Integrar con API
7. Agregar estados de loading y error
8. Testing y refinamiento

