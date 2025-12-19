/**
 * Cliente API para comunicarse con el backend FastAPI.
 * 
 * Fácil de migrar: solo cambiar NEXT_PUBLIC_API_URL en .env.local
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ProcessRunRequest {
  process_name: string;
  mode: 'operativo' | 'gestion';
  audience?: string;
  detail_level?: string;
  formality?: string;
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

