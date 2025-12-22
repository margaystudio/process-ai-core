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
  request: WorkspaceCreateRequest
): Promise<WorkspaceResponse> {
  const response = await fetch(`${API_URL}/api/v1/workspaces`, {
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
  const response = await fetch(`${API_URL}/api/v1/validations/${validationId}/reject`, {
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

// ============================================================
// Document Versions API
// ============================================================

export interface DocumentVersion {
  id: string;
  version_number: number;
  content_type: string;
  run_id: string | null;
  approved_at: string;
  approved_by: string | null;
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
    `${API_URL}/api/v1/validations/documents/${documentId}/approve`,
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
    `${API_URL}/api/v1/validations/documents/${documentId}/reject`,
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
