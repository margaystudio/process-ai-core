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
  domain: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
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
