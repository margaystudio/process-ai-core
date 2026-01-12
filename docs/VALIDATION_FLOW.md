# Flujo de Validación y Edición de Documentos

## Objetivo

Implementar un sistema completo de validación/edición que permita:
- Editar metadata sin regenerar contenido
- Rechazar con observaciones y corregir posteriormente
- Tres caminos de corrección: edición manual, patch por IA, regeneración completa
- Trazabilidad total con historial de cambios

## Modelo de Datos

### Nuevas Tablas

#### 1. Validation
Almacena las validaciones realizadas sobre documentos/runs.

```sql
CREATE TABLE validations (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
    run_id VARCHAR(36) REFERENCES runs(id),  -- NULL si es validación del documento en general
    validator_user_id VARCHAR(36) REFERENCES users(id),  -- NULL si no hay auth aún
    status VARCHAR(20) NOT NULL,  -- 'pending' | 'approved' | 'rejected'
    observations TEXT,  -- Comentarios del validador
    checklist_json TEXT,  -- JSON con checklist ISO-friendly
    created_at DATETIME NOT NULL,
    completed_at DATETIME
);
```

#### 2. AuditLog
Registro de todas las acciones realizadas sobre documentos.

```sql
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
    run_id VARCHAR(36) REFERENCES runs(id),  -- NULL si no aplica
    user_id VARCHAR(36) REFERENCES users(id),  -- NULL si no hay auth
    action VARCHAR(50) NOT NULL,  -- 'created' | 'updated' | 'validated' | 'rejected' | 'edited' | 'regenerated'
    entity_type VARCHAR(20),  -- 'document' | 'run' | 'validation'
    entity_id VARCHAR(36),
    changes_json TEXT,  -- JSON con los cambios realizados
    metadata_json TEXT,  -- JSON con metadata adicional
    created_at DATETIME NOT NULL
);
```

#### 3. DocumentVersion
Rastrea versiones aprobadas del documento (solo la última aprobada es la "verdad").

```sql
CREATE TABLE document_versions (
    id VARCHAR(36) PRIMARY KEY,
    document_id VARCHAR(36) NOT NULL REFERENCES documents(id),
    run_id VARCHAR(36) REFERENCES runs(id),  -- NULL si es edición manual
    version_number INTEGER NOT NULL,
    content_type VARCHAR(20) NOT NULL,  -- 'generated' | 'manual_edit' | 'ai_patch'
    content_json TEXT,  -- JSON del documento (ProcessDocument)
    content_markdown TEXT,  -- Markdown del documento
    approved_at DATETIME NOT NULL,
    approved_by VARCHAR(36) REFERENCES users(id),
    validation_id VARCHAR(36) REFERENCES validations(id),
    is_current BOOLEAN DEFAULT FALSE,  -- Solo una versión por documento puede ser TRUE
    created_at DATETIME NOT NULL
);
```

### Extensiones a Tablas Existentes

#### Document
- Agregar `approved_version_id` (FK → document_versions.id)
- Extender `status`: `draft` | `pending_validation` | `approved` | `rejected` | `archived`

#### Run
- Agregar `validation_id` (FK → validations.id, nullable)
- Agregar `is_approved` (BOOLEAN, default FALSE)

## Estados del Documento

```
draft → pending_validation → approved
                              ↓
                           rejected → (corrección) → pending_validation
```

## Flujos de Corrección

### 1. Edición Manual
- Usuario edita directamente el JSON/Markdown del documento
- Se crea un nuevo `DocumentVersion` con `content_type='manual_edit'`
- Se crea un `AuditLog` con `action='edited'`
- El documento vuelve a `pending_validation`

### 2. Patch por IA
- Usuario proporciona observaciones de validación
- Se llama al LLM con:
  - Documento actual (última versión aprobada o último run)
  - Observaciones del validador
  - Instrucciones para aplicar correcciones
- Se genera nuevo contenido corregido
- Se crea un nuevo `Run` con `content_type='ai_patch'`
- Se crea un `DocumentVersion` con `content_type='ai_patch'`
- El documento vuelve a `pending_validation`

### 3. Regeneración Completa
- Usuario sube nuevos insumos o modifica insumos existentes
- Se ejecuta el pipeline completo desde cero
- Se crea un nuevo `Run` normal
- El documento vuelve a `pending_validation`

## API Endpoints

### Validación
- `POST /api/v1/documents/{document_id}/validate` - Crear validación
- `POST /api/v1/validations/{validation_id}/approve` - Aprobar
- `POST /api/v1/validations/{validation_id}/reject` - Rechazar con observaciones
- `GET /api/v1/documents/{document_id}/validations` - Listar validaciones

### Edición
- `PUT /api/v1/documents/{document_id}/content` - Editar contenido manualmente
- `POST /api/v1/documents/{document_id}/patch` - Patch por IA con observaciones
- `GET /api/v1/documents/{document_id}/versions` - Listar versiones
- `GET /api/v1/documents/{document_id}/current-version` - Obtener versión actual aprobada

### Auditoría
- `GET /api/v1/documents/{document_id}/audit-log` - Historial de cambios

## Reglas de Negocio

1. **Solo la última versión aprobada es la "verdad"**:
   - Para RAG, siempre usar `document_versions` donde `is_current=TRUE`
   - Para operarios, mostrar solo versión aprobada

2. **Separación clara**:
   - **Insumos**: RawAssets (video/audio/fotos/texto) → Run
   - **Documento generado**: ProcessDocument (JSON/MD/PDF) → Artifact
   - **Decisiones**: Validation, AuditLog, DocumentVersion

3. **Usuario NO asigna pasos manualmente**:
   - Los pasos se infieren automáticamente por IA
   - La evidencia puede ser "sin paso" (evidencia general)
   - Modelado para futuro: asociación a secciones/bloques

4. **Compatibilidad con perfiles**:
   - Mantener DocumentProfile (Operativo vs Gestión)
   - Las validaciones pueden tener checklist específico por perfil

5. **ISO-friendly**:
   - Checklist de validación estructurado
   - Registro de hallazgos en `observations`
   - Trazabilidad completa en `audit_logs`

## Implementación por Fases

### Fase 1: Modelos y Migración
- Crear modelos SQLAlchemy
- Crear migración de base de datos
- Extender Document.status

### Fase 2: API Backend
- Endpoints de validación
- Endpoints de edición manual
- Endpoint de patch por IA
- Endpoints de auditoría

### Fase 3: UI
- Pantalla de validación
- Editor manual de documentos
- Historial y trazabilidad
- Integración con flujo existente



