/**
 * Cliente API para comunicarse con el backend FastAPI.
 * 
 * Fácil de migrar: solo cambiar NEXT_PUBLIC_API_URL en .env.local
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ProcessRunRequest {
  process_name: string;
  mode: 'operativo' | 'gestion';
  detail_level?: string;
}

export interface RecipeRunRequest {
  recipe_name: string;
  mode: 'simple' | 'detallado';
}

export interface RunResponse {
  run_id: string;
  process_name?: string;
  recipe_name?: string;
  status: string;
  artifacts: {
    json?: string;
    markdown?: string;
    pdf?: string;
  };
  document_id?: string;
  error?: string;
}

export interface WorkspaceCreateRequest {
  name: string;
  slug: string;
  country?: string;
  business_type?: string;
  language_style?: string;
  default_audience?: string;
  context_text?: string;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  slug: string;
  workspace_type: string;
  created_at: string;
}

export interface CatalogOption {
  value: string;
  label: string;
  sort_order: number;
}

export interface Folder {
  id: string;
  workspace_id: string;
  name: string;
  path: string;
  parent_id?: string;
  sort_order: number;
  created_at: string;
}

export interface Document {
  id: string;
  workspace_id: string;
  folder_id?: string;
  document_type: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
}

export interface DocumentUpdateRequest {
  name?: string;
  description?: string;
  status?: string;
  folder_id?: string;
  audience?: string;
  detail_level?: string;
  context_text?: string;
  cuisine?: string;
  difficulty?: string;
  servings?: number;
  prep_time?: string;
  cook_time?: string;
}

export interface FolderCreateRequest {
  workspace_id: string;
  name: string;
  path?: string;
  parent_id?: string;
  sort_order?: number;
  metadata?: Record<string, any>;
}

/**
 * Crea una nueva corrida de proceso.
 */
export async function createProcessRun(
  formData: FormData
): Promise<RunResponse> {
  const response = await fetch(`${API_URL}/api/v1/process-runs`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Crea una nueva corrida de receta.
 */
export async function createRecipeRun(
  formData: FormData
): Promise<RunResponse> {
  const response = await fetch(`${API_URL}/api/v1/recipe-runs`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene el estado de una corrida.
 */
export async function getRun(runId: string, domain: 'process' | 'recipe'): Promise<RunResponse> {
  const endpoint = domain === 'process' 
    ? `/api/v1/process-runs/${runId}`
    : `/api/v1/recipe-runs/${runId}`;
  
  const response = await fetch(`${API_URL}${endpoint}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Genera un PDF desde un run existente.
 */
export async function generatePDF(runId: string, domain: 'process' | 'recipe'): Promise<{ pdf_url: string }> {
  const endpoint = domain === 'process'
    ? `/api/v1/process-runs/${runId}/generate-pdf`
    : `/api/v1/recipe-runs/${runId}/generate-pdf`;
  
  const response = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene la URL de un artefacto.
 */
export function getArtifactUrl(runId: string, filename: string): string {
  return `${API_URL}/api/v1/artifacts/${runId}/${filename}`;
}

/**
 * Crea un nuevo workspace (cliente/organización).
 */
export async function createWorkspace(
  request: WorkspaceCreateRequest,
  userId?: string | null
): Promise<WorkspaceResponse> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }

  // Si Supabase no está configurado y tenemos userId, enviarlo en Authorization
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  if (!supabaseUrl || !supabaseKey) {
    // Modo desarrollo sin Supabase: usar userId o generar uno temporal
    let devUserId = userId
    if (!devUserId) {
      // Generar o obtener un userId temporal de localStorage
      devUserId = localStorage.getItem('dev_user_id')
      if (!devUserId) {
        // Generar un UUID v4 temporal
        devUserId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
          const r = Math.random() * 16 | 0
          const v = c === 'x' ? r : (r & 0x3 | 0x8)
          return v.toString(16)
        })
        localStorage.setItem('dev_user_id', devUserId)
      }
    }
    headers['Authorization'] = `Bearer ${devUserId}`
  } else if (supabaseUrl && supabaseKey) {
    // Modo con Supabase: obtener token de Supabase
    try {
      const { createClient } = await import('@/lib/supabase/client')
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`
      }
    } catch (err) {
      console.warn('Error obteniendo token de Supabase:', err)
    }
  }

  const response = await fetch(`${API_URL}/api/v1/workspaces`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista todos los workspaces.
 */
export async function listWorkspaces(): Promise<WorkspaceResponse[]> {
  const response = await fetch(`${API_URL}/api/v1/workspaces`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene los workspaces de un usuario específico.
 */
export async function getUserWorkspaces(userId: string): Promise<WorkspaceResponse[]> {
  const response = await fetch(`${API_URL}/api/v1/users/${userId}/workspaces`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Agrega un usuario a un workspace con un rol específico.
 */
export async function addUserToWorkspace(
  userId: string,
  workspaceId: string,
  roleName: string
): Promise<{ id: string; user_id: string; workspace_id: string; role: string; created_at: string }> {
  const response = await fetch(
    `${API_URL}/api/v1/users/${userId}/workspaces/${workspaceId}/membership?role_name=${encodeURIComponent(roleName)}`,
    {
      method: 'POST',
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene un workspace por ID.
 */
export async function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
  const response = await fetch(`${API_URL}/api/v1/workspaces/${workspaceId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene las opciones del catálogo para un dominio.
 */
export async function getCatalogOptions(domain: string): Promise<CatalogOption[]> {
  const response = await fetch(`${API_URL}/api/v1/catalog/${domain}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export interface CreateCatalogOptionRequest {
  domain: string;
  value?: string;
  label: string;
  prompt_text?: string;
  sort_order?: number;
}

/**
 * Crea una nueva opción de catálogo.
 */
export async function createCatalogOption(
  request: CreateCatalogOptionRequest
): Promise<CatalogOption> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (supabaseUrl && supabaseKey) {
    try {
      const { createClient } = await import('@/lib/supabase/client')
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`
      } else {
        throw new Error('No hay sesión activa. Por favor, inicia sesión.')
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('sesión')) {
        throw err
      }
      console.warn('Error obteniendo token de Supabase:', err)
      throw new Error('Error de autenticación. Por favor, inicia sesión nuevamente.')
    }
  } else {
    // Modo desarrollo sin Supabase: no se puede crear opciones de catálogo sin autenticación
    throw new Error('Supabase no está configurado. No se pueden crear opciones de catálogo.')
  }

  const response = await fetch(`${API_URL}/api/v1/catalog`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    if (response.status === 401) {
      throw new Error('No autorizado. Por favor, inicia sesión nuevamente.')
    }
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Lista todas las carpetas de un workspace.
 */
export async function listFolders(workspaceId: string): Promise<Folder[]> {
  const response = await fetch(`${API_URL}/api/v1/folders?workspace_id=${workspaceId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Crea una nueva carpeta.
 */
export async function createFolder(request: FolderCreateRequest): Promise<Folder> {
  const response = await fetch(`${API_URL}/api/v1/folders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Actualiza una carpeta existente.
 */
export async function updateFolder(folderId: string, request: Partial<FolderCreateRequest>): Promise<Folder> {
  const response = await fetch(`${API_URL}/api/v1/folders/${folderId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Elimina una carpeta.
 */
export async function deleteFolder(folderId: string, moveDocumentsTo?: string): Promise<void> {
  const url = new URL(`${API_URL}/api/v1/folders/${folderId}`);
  if (moveDocumentsTo) {
    url.searchParams.append('move_documents_to', moveDocumentsTo);
  }

  const response = await fetch(url.toString(), {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

/**
 * Lista documentos de un workspace.
 */
export async function listDocuments(workspaceId: string, folderId?: string, documentType: string = 'process'): Promise<Document[]> {
  const url = new URL(`${API_URL}/api/v1/documents`);
  url.searchParams.append('workspace_id', workspaceId);
  url.searchParams.append('document_type', documentType);
  if (folderId) {
    url.searchParams.append('folder_id', folderId);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene los runs de un documento.
 */
export async function getDocumentRuns(documentId: string): Promise<Array<{
  run_id: string;
  created_at: string;
  artifacts: {
    json?: string;
    md?: string;
    pdf?: string;
  };
}>> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/runs`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene un documento por ID.
 */
export async function getDocument(documentId: string): Promise<Document> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Actualiza un documento.
 */
export async function updateDocument(documentId: string, request: DocumentUpdateRequest): Promise<Document> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Crea un nuevo run para un documento existente.
 */
export async function createDocumentRun(
  documentId: string,
  formData: FormData
): Promise<RunResponse> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/runs`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Validation API
// ============================================================

export interface Validation {
  id: string;
  document_id: string;
  run_id: string | null;
  validator_user_id: string | null;
  status: string;
  observations: string;
  checklist_json: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ValidationCreateRequest {
  run_id?: string;
  observations?: string;
  checklist_json?: string;
}

export interface ValidationRejectRequest {
  observations: string;
}

export interface ValidationApproveRequest {
  checklist_json?: string;
}

/**
 * Crea una nueva validación para un documento.
 */
export async function createValidation(
  documentId: string,
  request: ValidationCreateRequest
): Promise<Validation> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Aprueba una validación.
 */
export async function approveValidation(
  validationId: string,
  request?: ValidationApproveRequest
): Promise<{ message: string; version_id: string }> {
  const response = await fetch(`${API_URL}/api/v1/validations/${validationId}/approve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Rechaza una validación con observaciones.
 */
export async function rejectValidation(
  validationId: string,
  request: ValidationRejectRequest
): Promise<Validation> {
  // Obtener token de autenticación
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({
    'Content-Type': 'application/json',
  })

  const response = await fetch(`${API_URL}/api/v1/validations/${validationId}/reject`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista todas las validaciones de un documento.
 */
export async function listValidations(documentId: string): Promise<Validation[]> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/validations`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Respuesta de decisión de validación (one-shot).
 */
export interface ValidationDecisionResponse {
  version_id: string;
  version_status: string;
  validation_id: string;
  document_status: string;
}

/**
 * Aprueba directamente una versión IN_REVIEW del documento (one-shot validation).
 * No requiere crear validación primero.
 */
export async function approveDocumentValidation(
  documentId: string,
  observations?: string
): Promise<ValidationDecisionResponse> {
  // Obtener token de autenticación
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({
    'Content-Type': 'application/json',
  })

  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/validate/approve`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ observations: observations || '' }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Rechaza directamente una versión IN_REVIEW del documento (one-shot validation).
 * Las observaciones son obligatorias.
 */
export async function rejectDocumentValidation(
  documentId: string,
  observations: string
): Promise<ValidationDecisionResponse> {
  if (!observations || !observations.trim()) {
    throw new Error('Las observaciones son obligatorias para rechazar un documento');
  }

  // Obtener token de autenticación
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({
    'Content-Type': 'application/json',
  })

  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/validate/reject`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ observations }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Document Versions API
// ============================================================

export interface DocumentVersion {
  id: string;
  version_number: number;
  version_status: string; // DRAFT | IN_REVIEW | APPROVED | REJECTED | OBSOLETE
  content_type: string;
  run_id: string | null;
  approved_at: string | null;
  approved_by: string | null;
  rejected_at: string | null;
  rejected_by: string | null;
  is_current: boolean;
  created_at: string;
}

/**
 * Obtiene todas las versiones de un documento.
 */
export async function getDocumentVersions(documentId: string): Promise<DocumentVersion[]> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/versions`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene la versión actual aprobada del documento.
 */
export async function getCurrentDocumentVersion(documentId: string): Promise<{
  id: string;
  version_number: number;
  content_type: string;
  run_id: string | null;
  content_json: string;
  content_markdown: string;
  approved_at: string;
  approved_by: string | null;
  created_at: string;
}> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/current-version`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Audit Log API
// ============================================================

export interface AuditLogEntry {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  run_id: string | null;
  user_id: string | null;
  changes_json: string | null;
  metadata_json: string | null;
  created_at: string;
}

/**
 * Obtiene el historial completo de cambios (audit log) de un documento.
 */
export async function getDocumentAuditLog(documentId: string): Promise<AuditLogEntry[]> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/audit-log`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Document Content Editing API
// ============================================================

/**
 * Edita manualmente el contenido de un documento.
 */
export async function updateDocumentContent(
  documentId: string,
  contentJson: string
): Promise<{
  version_id: string;
  version_number: number;
  content_type: string;
  created_at: string;
}> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/content`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content_json: contentJson }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Aplica un patch por IA usando observaciones de validación.
 */
export async function patchDocumentWithAI(
  documentId: string,
  observations: string,
  runId?: string
): Promise<RunResponse> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/patch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ observations, run_id: runId }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// User & Role API
// ============================================================

/**
 * Obtiene el rol de un usuario en un workspace.
 */
export async function syncUser(userData: {
  supabase_user_id: string
  email: string
  name: string
  auth_provider?: string
  metadata?: Record<string, any>
}): Promise<{ user_id: string; email: string; name: string; created: boolean }> {
  const response = await fetch(`${API_URL}/api/v1/auth/sync-user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      supabase_user_id: userData.supabase_user_id,
      email: userData.email,
      name: userData.name,
      auth_provider: userData.auth_provider || 'supabase',
      metadata: userData.metadata || {},
    }),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function getUserRole(
  userId: string,
  workspaceId: string
): Promise<{ role: string | null }> {
  const response = await fetch(
    `${API_URL}/api/v1/users/${userId}/role/${workspaceId}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Verifica si un usuario tiene un permiso específico en un workspace.
 */
export async function checkPermission(
  userId: string,
  workspaceId: string,
  permissionName: string
): Promise<{ has_permission: boolean }> {
  const response = await fetch(
    `${API_URL}/api/v1/users/${userId}/permission/${workspaceId}/${encodeURIComponent(permissionName)}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Documents by Status API
// ============================================================

/**
 * Lista documentos pendientes de aprobación (para aprobadores).
 */
export async function listDocumentsPendingApproval(
  workspaceId: string,
  userId: string
): Promise<Document[]> {
  const response = await fetch(
    `${API_URL}/api/v1/documents/pending-approval?workspace_id=${workspaceId}&user_id=${userId}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista documentos rechazados a revisar (para creadores).
 */
export async function listDocumentsToReview(
  workspaceId: string,
  userId: string
): Promise<Document[]> {
  const response = await fetch(
    `${API_URL}/api/v1/documents/to-review?workspace_id=${workspaceId}&user_id=${userId}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista documentos aprobados (para viewers).
 */
export async function listApprovedDocuments(
  workspaceId: string,
  folderId?: string
): Promise<Document[]> {
  const params = new URLSearchParams({
    workspace_id: workspaceId,
    document_type: 'process',
  });
  if (folderId) {
    params.append('folder_id', folderId);
  }

  const response = await fetch(
    `${API_URL}/api/v1/documents?${params.toString()}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const allDocs = await response.json();
  // Filtrar solo aprobados
  return allDocs.filter((doc: Document) => doc.status === 'approved');
}

// ============================================================
// Approval/Rejection API (Simplified)
// ============================================================

/**
 * Aprueba un documento directamente.
 */
export async function approveDocument(
  documentId: string,
  userId: string,
  workspaceId: string
): Promise<{ message: string; validation_id: string; version_id: string | null }> {
  const response = await fetch(
    `${API_URL}/api/v1/documents/${documentId}/approve`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        workspace_id: workspaceId,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Elimina un documento.
 */
export async function deleteDocument(documentId: string): Promise<{ message: string; deleted_runs: number }> {
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Rechaza un documento directamente con observaciones.
 */
export async function rejectDocument(
  documentId: string,
  observations: string,
  userId: string,
  workspaceId: string
): Promise<{ message: string; validation_id: string }> {
  const response = await fetch(
    `${API_URL}/api/v1/documents/${documentId}/reject`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        observations,
        user_id: userId,
        workspace_id: workspaceId,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// SUPERADMIN
// ============================================================================

export interface CreateB2BWorkspaceRequest {
  name: string;
  slug: string;
  country?: string;
  business_type?: string;
  language_style?: string;
  default_audience?: string;
  context_text?: string;
  plan_name?: string;
  admin_email: string;
  message?: string;
}

/**
 * Crea un workspace B2B (solo superadmin).
 */
export async function createB2BWorkspace(
  request: CreateB2BWorkspaceRequest,
  token: string
): Promise<WorkspaceResponse> {
  const response = await fetch(`${API_URL}/api/v1/superadmin/workspaces`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      name: request.name,
      slug: request.slug,
      country: request.country || 'UY',
      business_type: request.business_type,
      language_style: request.language_style || 'es_uy_formal',
      default_audience: request.default_audience || 'operativo',
      context_text: request.context_text,
      plan_name: request.plan_name || 'b2b_trial',
      admin_email: request.admin_email,
      message: request.message,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista todos los workspaces (solo superadmin).
 */
export async function listAllWorkspaces(
  workspaceType?: string,
  token?: string
): Promise<WorkspaceResponse[]> {
  const url = new URL(`${API_URL}/api/v1/superadmin/workspaces`);
  if (workspaceType) {
    url.searchParams.append('workspace_type', workspaceType);
  }

  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url.toString(), {
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// INVITACIONES
// ============================================================================

export interface InvitationResponse {
  id: string;
  workspace_id: string;
  invited_by_user_id: string;
  email: string;
  role_id: string;
  role_name: string;
  status: string;
  expires_at: string;
  accepted_at?: string;
  message?: string;
  created_at: string;
  invitation_url?: string; // URL para aceptar la invitación
  token?: string; // Token de la invitación (para uso directo)
}

/**
 * Lista invitaciones de un workspace.
 */
export async function listWorkspaceInvitations(
  workspaceId: string,
  status?: string,
  token?: string
): Promise<InvitationResponse[]> {
  const url = new URL(`${API_URL}/api/v1/workspaces/${workspaceId}/invitations`);
  if (status) {
    url.searchParams.append('status', status);
  }

  const headers: HeadersInit = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url.toString(), {
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Crea una invitación para unirse a un workspace.
 */
export async function createWorkspaceInvitation(
  workspaceId: string,
  request: {
    email: string;
    role_id?: string;
    role_name?: string;
    message?: string;
    expires_in_days?: number;
  },
  token: string
): Promise<InvitationResponse> {
  const response = await fetch(
    `${API_URL}/api/v1/workspaces/${workspaceId}/invitations`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        email: request.email,
        role_id: request.role_id,
        role_name: request.role_name,
        message: request.message,
        expires_in_days: request.expires_in_days || 7,
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene información de una invitación por token (público, sin autenticación).
 */
export async function getInvitationByToken(
  token: string
): Promise<InvitationResponse> {
  const response = await fetch(
    `${API_URL}/api/v1/invitations/token/${token}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene invitaciones pendientes por email (público, sin autenticación).
 */
export async function getPendingInvitationsByEmail(
  email: string
): Promise<InvitationResponse[]> {
  const response = await fetch(
    `${API_URL}/api/v1/invitations/pending/${encodeURIComponent(email)}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Acepta una invitación por token (público).
 */
export interface AcceptInvitationResponse {
  message: string
  status: 'accepted' | 'already_accepted' | 'already_member'
  user_id: string
  workspace_id: string
  membership_id: string
  role: string | null
}

export async function acceptInvitationByToken(
  token: string,
  userId?: string | null,
  authToken?: string | null
): Promise<AcceptInvitationResponse> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  
  // Incluir token de autenticación si está disponible
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const response = await fetch(
    `${API_URL}/api/v1/invitations/token/${token}/accept`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        user_id: userId || null,  // Enviar null si no hay userId (el backend lo creará)
      }),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================================================
// SUSCRIPCIONES
// ============================================================================

export interface SubscriptionPlanResponse {
  id: string;
  name: string;
  display_name: string;
  description: string;
  plan_type: string;
  price_monthly: number;
  price_yearly: number;
  max_users?: number;
  max_documents?: number;
  max_documents_per_month?: number;
  max_storage_gb?: number;
  features_json: string;
  is_active: boolean;
  sort_order: number;
}

export interface WorkspaceSubscriptionResponse {
  id: string;
  workspace_id: string;
  plan_id: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  current_users_count: number;
  current_documents_count: number;
  current_documents_this_month: number;
  current_storage_gb: number;
  plan: SubscriptionPlanResponse;
}

export interface WorkspaceLimitsResponse {
  workspace_id: string;
  plan_name: string;
  plan_display_name: string;
  limits: {
    max_users?: number;
    max_documents?: number;
    max_documents_per_month?: number;
    max_storage_gb?: number;
  };
  current_usage: {
    current_users_count: number;
    current_documents_count: number;
    current_documents_this_month: number;
    current_storage_gb: number;
  };
  can_create_users: boolean;
  can_create_documents: boolean;
  can_create_documents_this_month: boolean;
}

/**
 * Lista planes de suscripción disponibles.
 */
export async function listSubscriptionPlans(
  planType?: string
): Promise<SubscriptionPlanResponse[]> {
  const url = new URL(`${API_URL}/api/v1/subscription-plans`);
  if (planType) {
    url.searchParams.append('plan_type', planType);
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene la suscripción de un workspace.
 */
export async function getWorkspaceSubscription(
  workspaceId: string
): Promise<WorkspaceSubscriptionResponse> {
  const response = await fetch(`${API_URL}/api/v1/workspaces/${workspaceId}/subscription`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene los límites y uso actual de un workspace.
 */
export async function getWorkspaceLimits(
  workspaceId: string
): Promise<WorkspaceLimitsResponse> {
  const response = await fetch(`${API_URL}/api/v1/workspaces/${workspaceId}/limits`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}
