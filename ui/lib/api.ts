/**
 * Cliente API para comunicarse con el backend FastAPI.
 * 
 * Fácil de migrar: solo cambiar NEXT_PUBLIC_API_URL en .env.local
 */

import { authFetch } from '@/lib/api-auth'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Evita fetches duplicados en paralelo (React Strict Mode, varios hooks). */
const _inFlight = new Map<string, Promise<unknown>>()

function dedupeInFlight<T>(key: string, fetcher: () => Promise<T>): Promise<T> {
  const existing = _inFlight.get(key)
  if (existing) return existing as Promise<T>
  const promise = fetcher().finally(() => {
    _inFlight.delete(key)
  })
  _inFlight.set(key, promise)
  return promise
}

function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg?: string }).msg ?? '')
        }
        return ''
      })
      .filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  return fallback
}

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

export interface WorkspaceResponse {
  id: string;
  tenant_id?: string | null;
  name: string;
  slug: string;
  workspace_type: string;
  /** Acceso base del usuario en este workspace. Ver `WorkspaceAccessRole`. */
  role?: WorkspaceAccessRole | null;
  is_active?: boolean;
  country?: string | null;
  business_type?: string | null;
  language_style?: string | null;
  default_audience?: string | null;
  default_detail_level?: string | null;
  context_text?: string | null;
  description?: string | null;
  branding_icon_url?: string | null;
  branding_primary_color?: string | null;
  branding_secondary_color?: string | null;
  created_at: string;
}

export interface WorkspaceSettingsUpdateRequest {
  country?: string;
  business_type?: string;
  language_style?: string;
  default_audience?: string;
  default_detail_level?: string;
  context_text?: string;
  description?: string;
}

function normalizeWorkspaceResponse(workspace: WorkspaceResponse): WorkspaceResponse {
  return {
    ...workspace,
    branding_icon_url: workspace.branding_icon_url
      ? (workspace.branding_icon_url.startsWith('http')
        ? workspace.branding_icon_url
        : `${API_URL}${workspace.branding_icon_url}`)
      : null,
  }
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
  inherits_permissions?: boolean;
  color?: string;
  icon?: string | null;
  default_document_type?: string | null;
  tyto_enabled?: boolean | null;
  allow_document_override?: boolean;
  metadata?: { description?: string } | null;
  created_at: string;
}

export interface FolderStats {
  documentos: number;
  aprobados: number;
  borradores: number;
  pendientes: number;
  archivados: number;
  relaciones_nuevas: number;
  confianza_prom: number | null;
}

export interface FolderActivityItem {
  id: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  document: { id: string; name: string } | null;
  // Sin email a propósito: es el usuario de login (ver `_nombre_visible`
  // en api/routes/folders.py). El backend ya resuelve el nombre a mostrar.
  actor: { id: string; name: string } | null;
  created_at: string;
}

export interface FolderActivityResponse {
  items: FolderActivityItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type FolderGovernanceOrigin = 'base' | 'heredado' | 'personalizado';

export interface FolderGovernanceValue<T> {
  value: T | null;
  origin: FolderGovernanceOrigin;
  from?: string | null;
}

export interface FolderGovernance {
  default_document_type: FolderGovernanceValue<string>;
  tyto_enabled: FolderGovernanceValue<boolean>;
  allow_document_override: {
    value: boolean;
    origin: 'personalizado';
  };
}

/** Cumulativos: 'edicion' incluye lo de 'lectura'; 'aprobacion' incluye lo de 'edicion'. */
export type OperationalRoleAccessLevel = 'lectura' | 'edicion' | 'aprobacion';

export interface OperationalRoleResponse {
  id: string;
  workspace_id: string;
  name: string;
  slug: string;
  description: string;
  access_level: OperationalRoleAccessLevel;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  membership_id: string;
  user_id: string;
  email: string;
  name: string;
  role: WorkspaceAccessRole;
  operational_role_ids: string[];
}

export interface FolderPermissionsResponse {
  folder_id: string;
  inherits_permissions: boolean;
  operational_role_ids: string[];
  operational_roles: { id: string; name: string; slug: string }[];
  origin: 'heredado' | 'personalizado';
  from: string | null;
}

export interface DocumentMetadata {
  preguntas_abiertas?: string;
}

export interface Document {
  /** Codificación documental estable (ej. PR-0042). No cambia nunca — ADR-019. */
  code?: string | null;
  id: string;
  workspace_id: string;
  folder_id?: string;
  domain: string;
  document_type?: string;
  name: string;
  description: string;
  status: string;
  /** Número de la versión aprobada actual (null si no hay versión aprobada aún). */
  version_number?: number | null;
  metadata?: DocumentMetadata;
  created_at: string;
}

export interface DocumentUpdateRequest {
  name?: string;
  description?: string;
  status?: string;
  folder_id?: string;
  document_type?: string;
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
  name: string;
  path?: string;
  parent_id?: string;
  sort_order?: number;
  color?: string;
  icon?: string | null;
  default_document_type?: string | null;
  tyto_enabled?: boolean | null;
  allow_document_override?: boolean;
  metadata?: Record<string, any>;
}

/**
 * Crea una nueva corrida de proceso.
 */
export async function createProcessRun(
  formData: FormData
): Promise<RunResponse> {
  // Obtener token de autenticación
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()
  
  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // No establecer Content-Type para FormData, el navegador lo hace automáticamente
  
  const response = await authFetch(`${API_URL}/api/v1/process-runs`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export interface ProcessEvidenceResponse {
  status: 'done' | 'error' | 'no_text';
  extracted_text: string;
  metadata: {
    language?: string;
    duration_seconds?: number;
    pages?: number;
    used_ocr?: boolean;
  };
  error: string | null;
}

/**
 * Procesa un archivo de evidencia (transcripción, OCR, extracción de texto).
 * Usado por el wizard al agregar evidencias para mostrar badges reales.
 */
export async function processEvidenceFile(
  file: File,
  kind: import('@/lib/fileUploadValidation').FileType,
): Promise<ProcessEvidenceResponse> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const formData = new FormData();
  formData.append('file', file);
  formData.append('kind', kind);

  const headers = new Headers(await getAuthHeaders());
  // FormData necesita que el navegador genere el Content-Type junto con su
  // boundary. getAuthHeaders usa application/json por defecto para el resto
  // del cliente, así que lo quitamos únicamente para este upload.
  headers.delete('Content-Type');
  const response = await authFetch(`${API_URL}/api/v1/evidence/process`, {
    method: 'POST',
    headers,
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
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()
  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const response = await authFetch(`${API_URL}/api/v1/recipe-runs`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Importa archivos como documentos en una carpeta.
 */
export async function importDocuments(formData: FormData): Promise<Document[]> {
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await authFetch(`${API_URL}/api/v1/documents/import`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Obtiene el estado de una corrida.
 */
export async function getRun(runId: string, domain: 'process' | 'recipe'): Promise<RunResponse> {
  const endpoint = domain === 'process'
    ? `/api/v1/process-runs/${runId}`
    : `/api/v1/recipe-runs/${runId}`;

  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(`${API_URL}${endpoint}`, { headers: await getAuthHeaders() });

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
  
  const response = await authFetch(`${API_URL}${endpoint}`, {
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

// ============================================================
// Artifacts: fetch autenticado + blob URL
// ============================================================
//
// PRINCIPIO: "Nada que el navegador pida por su cuenta lleva una credencial en
// la dirección." Un archivo suelto que el usuario abre a propósito (un PDF de
// run, un JSON, un Markdown) nunca se referencia con un `<a href>`, un
// `<iframe src>` ni un `window.open` directo a la API: esas cargas las dispara
// el NAVEGADOR por su cuenta y no pueden llevar el header `Authorization`. La
// única forma de que "funcionen solo con la URL" sería poner el token en la
// URL misma — y eso la vuelve un bearer token portador (cualquiera con el
// enlace entra, sin importar a quién le revocaron el acceso después).
//
// El patrón correcto es siempre: `fetch` autenticado -> `blob` ->
// `URL.createObjectURL` -> usar ESE blob URL en el `<iframe>`/`<a>`/
// `window.open`, y `URL.revokeObjectURL` cuando ya no se necesita (unmount o
// cambio de artifact). `downloadVersionPdf` (arriba) y `ArtifactViewerModal`
// ya siguen este patrón; `fetchArtifact`/`fetchArtifactBlobUrl` son el atajo
// para la próxima pantalla que necesite mostrar un archivo.
//
// (El otro caso — una imagen EMBEBIDA en contenido editable, ej. el editor
// manual — es distinto: ahí es el navegador el que dispara el `<img>` solo, sin
// JS de por medio, y ese caso lo resuelve el proxy del front
// `ui/app/api/doc-assets/`, no este helper.)

/** true si `url` apunta a nuestra propia API: relativa, o absoluta a NEXT_PUBLIC_API_URL. */
function isOwnApiUrl(url: string): boolean {
  return !/^https?:\/\//i.test(url) || url.startsWith(API_URL);
}

/**
 * fetch autenticado de un artifact de nuestra API (PDF/JSON/Markdown/imagen).
 * Agrega el header Authorization SOLO si la URL es de nuestra propia API (ver
 * `isOwnApiUrl`): nunca a una URL de otro origen (ej. un signed URL de storage
 * de terceros), porque le rompería el CORS.
 */
export async function fetchArtifact(url: string, init?: RequestInit): Promise<Response> {
  const absoluteUrl = url.startsWith('http') ? url : `${API_URL}${url}`;
  let headers = init?.headers;
  if (isOwnApiUrl(absoluteUrl)) {
    const { getAuthHeaders } = await import('@/lib/api-auth');
    headers = { ...(await getAuthHeaders({})), ...(headers as Record<string, string> | undefined) };
  }
  return authFetch(absoluteUrl, { ...init, headers });
}

/**
 * Trae un artifact y lo expone como blob URL (`URL.createObjectURL`), para usar
 * en `<iframe src>`, `<a href>` o `window.open`. Quien la use es responsable de
 * revocarla (`URL.revokeObjectURL`) cuando deje de necesitarla.
 */
export async function fetchArtifactBlobUrl(url: string, init?: RequestInit): Promise<string> {
  const response = await fetchArtifact(url, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(detail || `Error ${response.status} al cargar el archivo`);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

/**
 * Descarga un artifact de run (PDF/JSON/Markdown) como archivo. Mismo patrón
 * que `downloadVersionPdf`: fetch autenticado -> blob -> `<a download>`.
 */
export async function downloadArtifact(url: string, fallbackName: string): Promise<void> {
  const response = await fetchArtifact(url);
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(detail || `No se pudo descargar el archivo (HTTP ${response.status})`);
  }
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] || fallbackName;

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

export interface CurrentUserResponse {
  user: {
    id: string
    email: string
    name: string | null
  }
  active_tenant: {
    id: string
    name: string
    slug: string
  }
  platform_roles: string[]
  tenant_roles: string[]
  workspaces: WorkspaceResponse[]
}

let _currentUserCache: { data: CurrentUserResponse; ts: number } | null = null
const CURRENT_USER_CACHE_MS = 5000

export function invalidateCurrentUserCache(): void {
  _currentUserCache = null
}

/**
 * Perfil + tenants desde margay-workspace (vía backend).
 * Respeta active_tenant_id en localStorage (header X-Active-Tenant-Id).
 */
export async function getCurrentUser(options?: { force?: boolean }): Promise<CurrentUserResponse> {
  if (options?.force) {
    invalidateCurrentUserCache()
  } else if (_currentUserCache && Date.now() - _currentUserCache.ts < CURRENT_USER_CACHE_MS) {
    return _currentUserCache.data
  }

  return dedupeInFlight('users/me', async () => {
    const { getAuthHeaders } = await import('@/lib/api-auth')
    const headers = await getAuthHeaders({})
    const response = await authFetch(`${API_URL}/api/v1/users/me`, { headers })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    const data = await response.json()
    const result: CurrentUserResponse = {
      user: data.user,
      active_tenant: data.active_tenant,
      platform_roles: data.platform_roles ?? [],
      tenant_roles: data.tenant_roles ?? [],
      workspaces: (data.workspaces ?? []).map(normalizeWorkspaceResponse),
    }
    _currentUserCache = { data: result, ts: Date.now() }
    return result
  })
}

/** Acceso efectivo a una carpeta puntual (herencia + bypass ya resueltos por el backend). */
export interface FolderCapabilities {
  view: boolean;
  create: boolean;
  approve: boolean;
}

/**
 * Acceso base del usuario en el workspace (derivado del rol del tenant en el
 * hub). Ya NO son roles de sistema (owner/admin/approver/creator/viewer):
 * - 'admin' → gestiona todo el workspace (equivale al "can_manage_workspace").
 * - 'member' → nivel "edición" en carpetas sin restricción explícita.
 * - 'external' → solo lectura siempre.
 * Lo que puede hacer cada usuario en el día a día lo definen los PERMISOS
 * efectivos (`permissions`) y el acceso por carpeta (`folders`), no este campo.
 */
export type WorkspaceAccessRole = 'admin' | 'member' | 'external';

/**
 * Capacidades efectivas del usuario actual en el tenant activo: la MISMA
 * decisión que el backend va a aplicar al autorizar cada request (incluye el
 * bypass de superadmin/admin y la herencia de permisos por carpeta).
 * Reemplaza la matriz de permisos que antes vivía hardcodeada en el front.
 */
export interface MyCapabilities {
  user_id: string;
  workspace_id: string;
  tenant_id: string;
  platform_roles: string[];
  tenant_roles: string[];
  role: WorkspaceAccessRole | null;
  is_superadmin: boolean;
  /** Permisos efectivos (ej. 'documents.view', 'documents.create', …). */
  permissions: string[];
  operational_role_ids: string[];
  can_manage_workspace: boolean;
  can_manage_branding: boolean;
  /** Acceso por carpeta, ya resuelto. Clave = folder_id. */
  folders: Record<string, FolderCapabilities>;
}

let _myCapabilitiesCache: { data: MyCapabilities; ts: number } | null = null
const MY_CAPABILITIES_CACHE_MS = 5000

export function invalidateMyCapabilitiesCache(): void {
  _myCapabilitiesCache = null
}

/**
 * Capacidades efectivas del usuario en el tenant activo (GET /users/me/capabilities).
 * Respeta active_tenant_id en localStorage (header X-Active-Tenant-Id), igual que getCurrentUser.
 */
export async function getMyCapabilities(options?: { force?: boolean }): Promise<MyCapabilities> {
  if (options?.force) {
    invalidateMyCapabilitiesCache()
  } else if (_myCapabilitiesCache && Date.now() - _myCapabilitiesCache.ts < MY_CAPABILITIES_CACHE_MS) {
    return _myCapabilitiesCache.data
  }

  return dedupeInFlight('users/me/capabilities', async () => {
    const { getAuthHeaders } = await import('@/lib/api-auth')
    const headers = await getAuthHeaders({})
    const response = await authFetch(`${API_URL}/api/v1/users/me/capabilities`, { headers })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    const data = await response.json()
    const result: MyCapabilities = {
      user_id: data.user_id,
      workspace_id: data.workspace_id,
      tenant_id: data.tenant_id,
      platform_roles: data.platform_roles ?? [],
      tenant_roles: data.tenant_roles ?? [],
      role: data.role ?? null,
      is_superadmin: Boolean(data.is_superadmin),
      permissions: data.permissions ?? [],
      operational_role_ids: data.operational_role_ids ?? [],
      can_manage_workspace: Boolean(data.can_manage_workspace),
      can_manage_branding: Boolean(data.can_manage_branding),
      folders: data.folders ?? {},
    }
    _myCapabilitiesCache = { data: result, ts: Date.now() }
    return result
  })
}

export async function uploadWorkspaceBrandingIcon(
  workspaceId: string,
  file: File
): Promise<{ icon_url: string | null }> {
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()
  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const formData = new FormData()
  formData.append('file', file)

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/branding/icon`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error al subir el icono' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const data = await response.json()
  return {
    icon_url: data.icon_url
      ? (data.icon_url.startsWith('http') ? data.icon_url : `${API_URL}${data.icon_url}`)
      : null,
  }
}

export async function deleteWorkspaceBrandingIcon(
  workspaceId: string
): Promise<{ icon_url: string | null }> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/branding/icon`, {
    method: 'DELETE',
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error al eliminar el icono' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

export async function updateWorkspaceBranding(
  workspaceId: string,
  branding: { primary_color: string; secondary_color: string }
): Promise<{ primary_color: string; secondary_color: string }> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/branding`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(branding),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error al guardar los colores' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/** Perfil de usuario (incluye teléfono y verificación). */
export interface UserProfile {
  id: string;
  email: string;
  name: string | null;
  phone_e164?: string | null;
  phone_verified?: boolean;
  phone_verified_at?: string | null;
}

/**
 * Obtiene un usuario por ID (nombre, email, teléfono, etc. para mostrar en UI).
 */
export async function getUser(userId: string): Promise<UserProfile> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/users/${userId}`, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  const data = await response.json();
  return {
    id: data.id,
    email: data.email ?? '',
    name: data.name ?? null,
    phone_e164: data.phone_e164 ?? null,
    phone_verified: data.phone_verified ?? false,
    phone_verified_at: data.phone_verified_at ?? null,
  };
}

/**
 * Actualiza el perfil del usuario actual (nombre y/o teléfono). Requiere autenticación.
 */
export async function updateMyProfile(
  userId: string,
  data: { name?: string; phone_e164?: string | null }
): Promise<UserProfile> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/users/${userId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  const res = await response.json();
  return {
    id: res.id,
    email: res.email ?? '',
    name: res.name ?? null,
    phone_e164: res.phone_e164 ?? null,
    phone_verified: res.phone_verified ?? false,
    phone_verified_at: res.phone_verified_at ?? null,
  };
}

/**
 * Obtiene un workspace por ID.
 */
export async function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders()

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}`, { headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const data = await response.json()
  return normalizeWorkspaceResponse(data)
}

export async function updateWorkspaceSettings(
  workspaceId: string,
  settings: WorkspaceSettingsUpdateRequest
): Promise<WorkspaceResponse> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/settings`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(settings),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error al guardar la configuración' }))
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`))
  }

  const data = await response.json()
  return normalizeWorkspaceResponse(data)
}

/**
 * Obtiene las opciones del catálogo para un dominio.
 */
export async function getCatalogOptions(domain: string): Promise<CatalogOption[]> {
  const response = await authFetch(`${API_URL}/api/v1/catalog/${domain}`);

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
    // Token vía el puente server-side (getAccessToken lee la cookie HttpOnly en el
    // server; el getSession() del browser no la ve).
    const { getAccessToken } = await import('@/lib/api-auth')
    const token = await getAccessToken()
    if (!token) {
      throw new Error('No hay sesión activa. Por favor, inicia sesión.')
    }
    headers['Authorization'] = `Bearer ${token}`
  } else {
    // Modo desarrollo sin Supabase: no se puede crear opciones de catálogo sin autenticación
    throw new Error('Supabase no está configurado. No se pueden crear opciones de catálogo.')
  }

  const response = await authFetch(`${API_URL}/api/v1/catalog`, {
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
 * Lista todas las carpetas del workspace activo (derivado del contexto de sesión).
 */
export async function listFolders(workspaceId?: string): Promise<Folder[]> {
  const cacheKey = `folders:${workspaceId ?? 'active'}`
  return dedupeInFlight(cacheKey, async () => {
    const { getAuthHeaders } = await import('@/lib/api-auth')
    const headers = await getAuthHeaders({})

    const response = await authFetch(`${API_URL}/api/v1/folders`, { headers })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  })
}

/**
 * Obtiene metricas agregadas de una carpeta.
 */
export async function getFolderStats(folderId: string): Promise<FolderStats> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})

  const response = await authFetch(`${API_URL}/api/v1/folders/${folderId}/stats`, { headers })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Obtiene la actividad auditada reciente de una carpeta.
 */
export async function getFolderActivity(
  folderId: string,
  page = 1,
  pageSize = 20
): Promise<FolderActivityResponse> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  const response = await authFetch(
    `${API_URL}/api/v1/folders/${folderId}/activity?${params.toString()}`,
    { headers }
  )

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Obtiene la configuracion efectiva de gobierno de una carpeta.
 */
export async function getFolderGovernance(folderId: string): Promise<FolderGovernance> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})

  const response = await authFetch(`${API_URL}/api/v1/folders/${folderId}/governance`, { headers })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Crea una nueva carpeta.
 */
export async function createFolder(request: FolderCreateRequest): Promise<Folder> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/folders`, {
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
 * Actualiza una carpeta existente.
 */
export async function updateFolder(folderId: string, request: Partial<FolderCreateRequest>): Promise<Folder> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/folders/${folderId}`, {
    method: 'PUT',
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
 * Elimina una carpeta.
 */
export async function deleteFolder(folderId: string, moveDocumentsTo?: string): Promise<void> {
  const url = new URL(`${API_URL}/api/v1/folders/${folderId}`);
  if (moveDocumentsTo) {
    url.searchParams.append('move_documents_to', moveDocumentsTo);
  }

  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})

  const response = await authFetch(url.toString(), {
    method: 'DELETE',
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

/**
 * Obtiene los permisos de una carpeta (roles operativos con acceso).
 */
export async function getFolderPermissions(folderId: string): Promise<FolderPermissionsResponse> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/folders/${folderId}/permissions`, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Actualiza los permisos de una carpeta.
 */
export async function updateFolderPermissions(
  folderId: string,
  body: { inherits_permissions?: boolean; operational_role_ids?: string[] }
): Promise<{ message: string; folder_id: string }> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/folders/${folderId}/permissions`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Lista roles operativos del workspace.
 */
export async function listOperationalRoles(workspaceId: string): Promise<OperationalRoleResponse[]> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/operational-roles`, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Crea un rol operativo.
 */
export async function createOperationalRole(
  workspaceId: string,
  body: { name: string; slug?: string; description?: string; access_level?: OperationalRoleAccessLevel }
): Promise<OperationalRoleResponse> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/operational-roles`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Actualiza un rol operativo.
 */
export async function updateOperationalRole(
  roleId: string,
  body: { name?: string; description?: string; is_active?: boolean; access_level?: OperationalRoleAccessLevel }
): Promise<OperationalRoleResponse> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/operational-roles/${roleId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Elimina un rol operativo.
 */
export async function deleteOperationalRole(roleId: string): Promise<void> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/operational-roles/${roleId}`, {
    method: 'DELETE',
    headers,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
}

/**
 * Lista miembros del workspace (con roles operativos).
 */
export async function getWorkspaceMembers(workspaceId: string): Promise<{ workspace_id: string; members: WorkspaceMember[] }> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/members`, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Asigna roles operativos a un usuario (membership).
 */
export async function assignOperationalRolesToMembership(
  membershipId: string,
  operationalRoleIds: string[]
): Promise<{ message: string; membership_id: string }> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await authFetch(`${API_URL}/api/v1/workspace-memberships/${membershipId}/operational-roles`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ operational_role_ids: operationalRoleIds }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Lista documentos del workspace activo (derivado del contexto de sesión).
 * Requiere autenticación. El backend filtra por rol (viewers solo ven aprobados).
 */
export async function listDocuments(workspaceId?: string, folderId?: string, documentType: string = 'process', status?: string): Promise<Document[]> {
  const cacheKey = `documents:${workspaceId ?? 'active'}:${folderId ?? ''}:${documentType}:${status ?? ''}`
  return dedupeInFlight(cacheKey, async () => {
    const { getAuthHeaders } = await import('@/lib/api-auth')
    const headers = await getAuthHeaders({})

    const url = new URL(`${API_URL}/api/v1/documents`)
    url.searchParams.append('domain', documentType)
    if (folderId) {
      url.searchParams.append('folder_id', folderId)
    }
    if (status) {
      url.searchParams.append('status', status)
    }

    const response = await authFetch(url.toString(), { headers })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  })
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
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/runs`, { headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene un documento por ID.
 * Requiere autenticación y permiso documents.view en el workspace.
 */
export async function getDocument(documentId: string): Promise<Document> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}`, { headers });

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
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}`, {
    method: 'PUT',
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
 * Crea un nuevo run para un documento existente.
 */
export async function createDocumentRun(
  documentId: string,
  formData: FormData
): Promise<RunResponse> {
  // Obtener token de autenticación
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()
  
  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // No establecer Content-Type para FormData, el navegador lo hace automáticamente
  
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/runs`, {
    method: 'POST',
    headers,
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
  validator_user_name: string;
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
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/validate`, {
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
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' });
  const response = await authFetch(`${API_URL}/api/v1/validations/${validationId}/approve`, {
    method: 'POST',
    headers,
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

  const response = await authFetch(`${API_URL}/api/v1/validations/${validationId}/reject`, {
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
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/validations`, {
    headers: await getAuthHeaders(),
  });

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
  observations?: string,
  /**
   * Vigencia comprometida en ESTE acto de aprobación. Queda congelada en el acta
   * del PDF. `undefined` ⇒ el backend usa el default del workspace;
   * `sinVencimiento` ⇒ se aprueba sin comprometer fecha.
   */
  validityUntil?: string | null,
  sinVencimiento?: boolean,
  /**
   * No congelar el PDF dentro de este request. Para aprobación por lote: el
   * freeze cuesta un render + una subida, y en un lote secuencial eso son
   * minutos. El artefacto lo produce después el barrido
   * (tools/freeze_pending_pdfs.py) o la primera apertura del PDF, lo que pase
   * antes. Es seguro porque el acta está congelada en la versión: congelar más
   * tarde da el mismo documento.
   */
  deferFreeze?: boolean
): Promise<ValidationDecisionResponse> {
  // Obtener token de autenticación
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({
    'Content-Type': 'application/json',
  })

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/validate/approve`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      observations: observations || '',
      validity_until: validityUntil || null,
      sin_vencimiento: Boolean(sinVencimiento),
      defer_freeze: Boolean(deferFreeze),
    }),
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

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/validate/reject`, {
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

/**
 * Cancela el envío a revisión y vuelve la versión a borrador.
 * Solo el creador de la versión puede cancelar.
 */
export async function cancelDocumentSubmission(
  documentId: string,
  versionId: string,
  userId?: string,
  workspaceId?: string
): Promise<{ message: string; version: { id: string; version_number: number; version_status: string } }> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' });
  const response = await authFetch(
    `${API_URL}/api/v1/documents/${documentId}/versions/${versionId}/cancel-submission`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({}),
    }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Envía una versión DRAFT a revisión (cambia a IN_REVIEW).
 */
export async function submitVersionForReview(
  documentId: string,
  versionId: string,
  userId?: string,
  workspaceId?: string,
  /** Aprobadores sugeridos (user_id). Semántica sugerencia+notificación: no restringe quién aprueba. */
  approverIds: string[] = [],
  /** Comentario opcional del autor para los aprobadores. */
  comment: string = ''
): Promise<{ message: string; version: { id: string; version_number: number; version_status: string; validation_id: string }; validation: { id: string; status: string; document_id: string; created_at: string; assigned_approver_ids: string[]; submit_comment: string } }> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' });
  const response = await authFetch(
    `${API_URL}/api/v1/documents/${documentId}/versions/${versionId}/submit`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ approver_ids: approverIds, comment }),
    }
  );
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
  validation_id?: string | null; // Validación asociada (cuando está IN_REVIEW)
  approved_at: string | null;
  approved_by: string | null;
  approved_by_name: string;
  rejected_at: string | null;
  rejected_by: string | null;
  rejected_by_name: string;
  is_current: boolean;
  /** Hasta cuándo se comprometió la vigencia de esta aprobación (fijada al aprobar). */
  validity_until?: string | null;
  created_by: string | null; // Usuario que creó la versión
  created_by_name: string;
  created_at: string;
}

/**
 * URL del PDF REGENERADO de una versión editable (DRAFT / IN_REVIEW / REJECTED):
 * se renderiza en cada request desde content_html (si existe) o content_markdown.
 * No modifica artefactos del run.
 *
 * Para versiones APPROVED usar getVersionFrozenPdfUrl: este endpoint redirige
 * (307) a ese, porque regenerar rompería el hash registrado del artefacto.
 */
export function getVersionPreviewPdfUrl(documentId: string, versionId: string): string {
  return `${API_URL}/api/v1/documents/${documentId}/versions/${versionId}/preview-pdf`;
}

/**
 * URL del PDF CONGELADO de una versión aprobada: los bytes exactos que se
 * subieron a storage al aprobarla, con su SHA-256 registrado como ETag.
 *
 * El backend responde `private, no-cache`: el navegador lo cachea pero revalida
 * en cada apertura (304 sin cuerpo). Es a propósito — el artefacto no cambia,
 * pero el permiso para verlo sí, y así se re-verifica en cada apertura. Por eso
 * esta URL NO debe llevar cache-buster.
 */
export function getVersionFrozenPdfUrl(documentId: string, versionId: string): string {
  return `${API_URL}/api/v1/documents/${documentId}/versions/${versionId}/pdf`;
}

/**
 * True si el PDF de una versión con este estado es un artefacto inmutable.
 *
 * Solo APPROVED: OBSOLETE puede tener PDF congelado (si en su momento se
 * aprobó) o no, y el backend resuelve ese caso redirigiendo desde preview-pdf.
 * Pedirle el congelado directo daría 404 en las que nunca se congelaron.
 */
export function isFrozenVersionStatus(versionStatus?: string | null): boolean {
  return versionStatus === 'APPROVED';
}

/**
 * URL del PDF correcto para una versión según su estado: el artefacto congelado
 * si está aprobada, el preview regenerado si sigue siendo editable.
 */
export function getVersionPdfUrl(
  documentId: string,
  versionId: string,
  versionStatus?: string | null,
): string {
  return isFrozenVersionStatus(versionStatus)
    ? getVersionFrozenPdfUrl(documentId, versionId)
    : getVersionPreviewPdfUrl(documentId, versionId);
}

/**
 * Descarga el PDF de una versión como archivo (Content-Disposition: attachment).
 *
 * Va por `fetch` y no por un `<a href>` porque el endpoint exige el header
 * Authorization: un link pelado devolvería "Missing Authorization header".
 *
 * Importante: pasa por el MISMO endpoint que la vista, así que una versión
 * superada se descarga CON el sello "VERSIÓN SUPERADA". Es el caso donde más
 * importa, porque el archivo descargado es el que circula por fuera del sistema.
 */
export async function downloadVersionPdf(
  documentId: string,
  versionId: string,
  versionStatus?: string | null,
  fallbackName = 'documento.pdf',
): Promise<void> {
  const base = getVersionPdfUrl(documentId, versionId, versionStatus);
  const url = `${base}${base.includes('?') ? '&' : '?'}download=1`;
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(url, {
    credentials: 'include',
    headers: await getAuthHeaders(),
  });

  if (!response.ok) {
    const detalle = await response.text().catch(() => '');
    throw new Error(detalle || `No se pudo descargar el PDF (HTTP ${response.status})`);
  }

  // El nombre lo decide el backend (conserva el del archivo original en los
  // documentos importados); el fallback es solo por si el header no viaja.
  const disposition = response.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] || fallbackName;

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(blobUrl);
  }
}

/**
 * Obtiene todas las versiones de un documento.
 */
export async function getDocumentVersions(documentId: string): Promise<DocumentVersion[]> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/versions`, {
    headers: await getAuthHeaders(),
  });

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
  approved_by_name: string;
  created_at: string;
}> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/current-version`, {
    headers: await getAuthHeaders(),
  });

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
  user_name: string;
  changes_json: string | null;
  metadata_json: string | null;
  created_at: string;
}

/**
 * Obtiene el historial completo de cambios (audit log) de un documento.
 */
export async function getDocumentAuditLog(documentId: string): Promise<AuditLogEntry[]> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/audit-log`, {
    headers: await getAuthHeaders(),
  });

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
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/content`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ content_json: contentJson }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Obtiene el contenido editable (HTML) de la versión DRAFT para edición manual Tiptap.
 */
export async function getEditableContent(documentId: string): Promise<{
  version_id: string;
  version_number: number;
  html: string;
  updated_at: string;
}> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/editable`, { method: 'GET', headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Guarda el HTML del editor manual (borrador).
 */
export async function saveEditableContent(
  documentId: string,
  contentHtml: string
): Promise<{ version_id: string; version_number: number; updated_at: string }> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/editable`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ content_html: contentHtml }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * Sube una imagen para el editor manual. Devuelve la URL para insertar en el
 * `<img>` del editor (Tiptap): es del PROXY del front (`/api/doc-assets/...`,
 * ver `ui/app/api/doc-assets/`), no de la API — el `<img>` la pide el navegador
 * solo, sin poder mandarle el header Authorization, así que NO hay que
 * prefijarla con `NEXT_PUBLIC_API_URL` (eso apuntaría al host de la API, donde
 * esa ruta no existe). Se usa tal cual la devuelve el backend.
 */
export async function uploadEditorImage(documentId: string, file: File): Promise<{ url: string }> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const formData = new FormData();
  formData.append('file', file);

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/upload-editor-image`, {
    method: 'POST',
    headers,
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error al subir la imagen' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  const data = await response.json();
  return { url: data.url };
}

/**
 * Aplica un patch por IA usando observaciones de validación.
 */
export async function patchDocumentWithAI(
  documentId: string,
  observations: string,
  runId?: string
): Promise<RunResponse> {
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}/patch`, {
    method: 'POST',
    headers,
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
 * Verifica si un usuario tiene un permiso específico en un workspace.
 */
export async function checkPermission(
  userId: string,
  workspaceId: string,
  permissionName: string
): Promise<{ has_permission: boolean }> {
  // Obtener token de autenticación
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})
  
  const response = await authFetch(
    `${API_URL}/api/v1/users/${userId}/permission/${workspaceId}/${encodeURIComponent(permissionName)}`,
    {
      headers,
    }
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
 * Lista documentos pendientes de aprobación del workspace activo (para aprobadores).
 */
export async function listDocumentsPendingApproval(
  workspaceId?: string,
  _userId?: string
): Promise<Document[]> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(
    `${API_URL}/api/v1/documents/pending-approval`,
    { headers }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista documentos rechazados a revisar del workspace activo (para creadores).
 */
export async function listDocumentsToReview(
  workspaceId?: string,
  _userId?: string
): Promise<Document[]> {
  const { getAccessToken } = await import('@/lib/api-auth');
  const token = await getAccessToken();
  const headers: HeadersInit = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await authFetch(
    `${API_URL}/api/v1/documents/to-review`,
    { headers }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Lista documentos aprobados (para viewers).
 * Filtra en el servidor con status=approved.
 */
export async function listApprovedDocuments(
  workspaceId?: string,
  folderId?: string
): Promise<Document[]> {
  return listDocuments(workspaceId, folderId, 'process', 'approved');
}

// ============================================================
// Approval/Rejection API (Simplified)
// ============================================================

/**
 * Elimina un documento.
 * Requiere permiso documents.delete en el workspace del documento.
 */
export async function deleteDocument(documentId: string): Promise<{ message: string; deleted_runs: number }> {
  const { getAccessToken } = await import('@/lib/api-auth')
  const token = await getAccessToken()
  const headers: HeadersInit = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await authFetch(`${API_URL}/api/v1/documents/${documentId}`, {
    method: 'DELETE',
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// ============================================================
// Document Types API (entidad por-tenant)
// ============================================================

export interface DocumentTypeBehaviors {
  versionado?: boolean;
  aprobacion?: boolean;
  tyto?: boolean;
  relaciones?: boolean;
  metadatos?: boolean;
}

export interface DocumentType {
  id: string;
  key: string;
  label: string;
  prompt_text: string | null;
  behaviors: DocumentTypeBehaviors;
  is_active: boolean;
  sort_order: number;
  /** 'default' = tipo de sistema; 'custom' = creado por el tenant. */
  origin: 'default' | 'custom';
  icon: string | null;
  color: string | null;
}

export interface DocumentTypePatch {
  label?: string;
  prompt_text?: string;
  behaviors?: DocumentTypeBehaviors;
  is_active?: boolean;
  sort_order?: number;
  icon?: string | null;
  color?: string | null;
}

export interface DocumentTypeCreateRequest {
  key?: string;
  label: string;
  prompt_text?: string;
  behaviors?: DocumentTypeBehaviors;
  icon?: string | null;
  color?: string | null;
  sort_order?: number;
}

/**
 * Lista tipos documentales del tenant activo.
 * Por defecto solo retorna los activos; pasá include_inactive=true para todos.
 */
export async function getDocumentTypes(
  includeInactive = false
): Promise<DocumentType[]> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({})

  const url = new URL(`${API_URL}/api/v1/document-types`)
  if (includeInactive) {
    url.searchParams.set('include_inactive', 'true')
  }

  const response = await authFetch(url.toString(), { headers })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * Actualiza parcialmente un tipo documental.
 * Solo los campos presentes en el patch se modifican.
 */
export async function updateDocumentType(
  id: string,
  patch: DocumentTypePatch
): Promise<DocumentType> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/document-types/${id}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(patch),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`))
  }

  return response.json()
}

/**
 * Crea un tipo documental custom para el tenant activo.
 */
export async function createDocumentType(
  body: DocumentTypeCreateRequest
): Promise<DocumentType> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' })

  const response = await authFetch(`${API_URL}/api/v1/document-types`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`))
  }

  return response.json()
}

// SUPERADMIN (createB2BWorkspace y listAllWorkspaces eliminados — endpoints removidos)

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

  const response = await authFetch(url.toString());

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
): Promise<WorkspaceSubscriptionResponse | null> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders()

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/subscription`, {
    headers,
  });

  if (response.status === 404) return null

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`));
  }

  const data = await response.json()
  return data ?? null
}

/**
 * Obtiene los límites y uso actual de un workspace.
 */
export async function getWorkspaceLimits(
  workspaceId: string
): Promise<WorkspaceLimitsResponse | null> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders()

  const response = await authFetch(`${API_URL}/api/v1/workspaces/${workspaceId}/limits`, {
    headers,
  });

  if (response.status === 404) return null

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`));
  }

  return response.json();
}

// ─── Tyto (Fase B — streaming) ──────────────────────────────────────────────
// Contrato: api/routes/tyto.py · POST /api/v1/tyto/query/stream (SSE por POST,
// por eso no usamos EventSource: leemos el body a mano con getReader()).

/** Nivel de confianza de una fuente/segmento citado por Tyto. */
export type TytoTier = 'aprobado' | 'referencia' | 'inferido';

export interface TytoSegment {
  text: string;
  source_ids: string[];
  tier: string;
}

export interface TytoSource {
  source_id: string;
  document_id: string;
  document_name: string;
  version: number | null;
  approved_at: string | null;
  tier: string;
}

export interface TytoQueryResult {
  answered: boolean;
  answer: string;
  segments: TytoSegment[];
  sources: TytoSource[];
  refusal_reason?: string | null;
  /**
   * La búsqueda corrió sin embeddings (solo coincidencia de palabras). Acompaña
   * tanto a las respuestas como a los rechazos: cambia lo que el resultado puede
   * afirmar, no solo cómo se obtuvo.
   */
  search_degraded?: boolean;
}

export type TytoStreamEvent =
  /**
   * Llega PRIMERO, antes de cualquier token: el id de la conversación a la que
   * el servidor asoció esta pregunta. Va al principio y no en el `result` final
   * a propósito — si el stream muere a mitad, el cliente igual se queda con el
   * id y la próxima pregunta sigue el mismo hilo en vez de abrir otro.
   */
  | { type: 'session'; sessionId: string }
  | { type: 'token'; text: string }
  | { type: 'result'; data: TytoQueryResult }
  | { type: 'error'; detail: string };

/** Parsea un bloque SSE (`event: <tipo>\ndata: <json>`) al contrato de Tyto. */
function parseTytoSseBlock(block: string): TytoStreamEvent | null {
  let eventName = 'message';
  const dataLines: string[] = [];

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim());
    }
  }
  if (!dataLines.length) return null;

  const data = JSON.parse(dataLines.join('\n'));
  if (eventName === 'session') return { type: 'session', sessionId: data.session_id };
  if (eventName === 'token') return { type: 'token', text: data.text };
  if (eventName === 'result') return { type: 'result', data };
  if (eventName === 'error') return { type: 'error', detail: data.detail };
  return null;
}

/**
 * Consulta a Tyto vía streaming SSE. Emite eventos incrementales por `onEvent`
 * a medida que llegan: el streaming es solo percepción de velocidad — los
 * niveles de confianza (tier) y las fuentes SOLO llegan en el evento `result`
 * final, nunca en los `token` (ver api/routes/tyto.py).
 */
export async function streamTytoQuery(
  question: string,
  onEvent: (event: TytoStreamEvent) => void,
  signal?: AbortSignal,
  /** Conversación en curso. `null` en la primera pregunta: el servidor la crea. */
  sessionId?: string | null
): Promise<void> {
  const { getAuthHeaders } = await import('@/lib/api-auth');
  const headers = await getAuthHeaders({ 'Content-Type': 'application/json' });

  const response = await authFetch(`${API_URL}/api/v1/tyto/query/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ question, session_id: sessionId ?? null }),
    signal,
  });

  if (!response.ok || !response.body) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const parsed = parseTytoSseBlock(rawEvent);
      if (parsed) onEvent(parsed);
    }
  }
}

// ============================================================================
// Relaciones semánticas y objetos de conocimiento
// ============================================================================

export type RelationStatus = 'candidate' | 'confirmed' | 'rejected' | 'obsolete'

export type RelationType =
  | 'usa'
  | 'requiere'
  | 'genera'
  | 'relacionado_con'
  | 'describe'
  | 'aplica_a'
  | 'depende_de'
  | 'reemplaza_a'
  | 'ejecutado_por'
  | 'aprobado_por'
  | 'ubicado_en'

export type KnowledgeObjectType =
  | 'sistema'
  | 'rol'
  | 'area'
  | 'equipo'
  | 'formulario'
  | 'proceso'
  | 'ubicacion'
  | 'normativa'

export interface RelationTarget {
  id: string
  type: string
  name: string
}

export interface DocumentRelationItem {
  id: string
  target: RelationTarget
  confidence: number | null
  status: RelationStatus
  evidence_text: string | null
  created_by_ai: boolean
  /** Quién DECIDIÓ sobre la relación: se llena al confirmar Y al rechazar.
   *  `null` con `status: 'confirmed'` significa que la confirmó el sistema,
   *  sin intervención humana. Se llamaba `confirmed_by` y mentía en las
   *  rechazadas. */
  decided_by: string | null
  decided_at: string | null
  possible_duplicate_of: RelationTarget | null
}

export interface DocumentRelationGroup {
  relation_type: RelationType | string
  items: DocumentRelationItem[]
}

export interface DocumentRelationsResponse {
  document_id: string
  groups: DocumentRelationGroup[]
}

export interface WorkspaceRelationDocument {
  id: string
  name: string
  folder_id: string
  folder_name: string
}

export interface WorkspaceRelationItem extends DocumentRelationItem {
  document: WorkspaceRelationDocument
  relation_type: RelationType | string
}

export interface WorkspaceRelationsResponse {
  items: WorkspaceRelationItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface WorkspaceRelationsParams {
  status?: RelationStatus
  type?: RelationType | string
  folder_id?: string
  page?: number
  page_size?: number
}

export interface SuggestDocumentRelationsResponse {
  document_id: string
  version_id: string
  candidates_created: number
  chunks_indexed: number
}

export interface RelationPatch {
  relation_type?: RelationType
  target_type?: string
  target_id?: string
}

export interface KnowledgeObject {
  id: string
  type: KnowledgeObjectType | string
  canonical_name: string
  normalized_name: string
  description: string | null
  aliases: string[]
}

export interface KnowledgeObjectCreateRequest {
  type: KnowledgeObjectType
  canonical_name: string
  description?: string
}

export interface KnowledgeObjectSearchParams {
  type?: KnowledgeObjectType | string
  q?: string
}

export interface DocumentImpactItem {
  id: string
  name: string
}

export interface DocumentImpactDocument extends DocumentImpactItem {
  status: string
  document_type: string
}

export interface DocumentImpactEntity extends DocumentImpactItem {
  type: string
}

export interface DocumentImpactResponse {
  document_id: string
  affected_documents: DocumentImpactDocument[]
  affected_entities: DocumentImpactEntity[]
}

async function semanticRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const { getAuthHeaders } = await import('@/lib/api-auth')
  const headers = await getAuthHeaders(
    Object.fromEntries(new Headers(init.headers).entries())
  )
  const response = await authFetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }))
    throw new Error(formatApiErrorDetail(error.detail, `HTTP ${response.status}`))
  }

  return response.json()
}

/**
 * El backend devuelve candidate + confirmed por defecto. Como semantic.py no
 * expone un query param status, el filtro opcional se aplica sobre la respuesta.
 */
export async function getDocumentRelations(
  documentId: string,
  status?: Extract<RelationStatus, 'candidate' | 'confirmed'>
): Promise<DocumentRelationsResponse> {
  const result = await semanticRequest<DocumentRelationsResponse>(
    `/documents/${encodeURIComponent(documentId)}/relations`
  )
  if (!status) return result

  return {
    ...result,
    groups: result.groups
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => item.status === status),
      }))
      .filter((group) => group.items.length > 0),
  }
}

export function getWorkspaceRelations(
  params: WorkspaceRelationsParams = {}
): Promise<WorkspaceRelationsResponse> {
  const query = new URLSearchParams({
    status: params.status ?? 'candidate',
    page: String(params.page ?? 1),
    page_size: String(params.page_size ?? 25),
  })
  if (params.type) query.set('type', params.type)
  if (params.folder_id) query.set('folder_id', params.folder_id)
  return semanticRequest(`/relations?${query.toString()}`)
}

export function suggestDocumentRelations(
  documentId: string
): Promise<SuggestDocumentRelationsResponse> {
  return semanticRequest(`/documents/${encodeURIComponent(documentId)}/relations/suggest`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function confirmRelation(relationId: string): Promise<DocumentRelationItem> {
  return semanticRequest(`/relations/${encodeURIComponent(relationId)}/confirm`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function rejectRelation(relationId: string): Promise<DocumentRelationItem> {
  return semanticRequest(`/relations/${encodeURIComponent(relationId)}/reject`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function editRelation(
  relationId: string,
  patch: RelationPatch
): Promise<DocumentRelationItem> {
  return semanticRequest(`/relations/${encodeURIComponent(relationId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function searchKnowledgeObjects(
  params: KnowledgeObjectSearchParams = {}
): Promise<KnowledgeObject[]> {
  const query = new URLSearchParams()
  if (params.type) query.set('type', params.type)
  if (params.q?.trim()) query.set('q', params.q.trim())
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return semanticRequest(`/knowledge-objects${suffix}`)
}

export function createKnowledgeObject(
  body: KnowledgeObjectCreateRequest
): Promise<KnowledgeObject> {
  return semanticRequest('/knowledge-objects', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function mergeKnowledgeObject(
  knowledgeObjectId: string,
  body: { into_id: string }
): Promise<KnowledgeObject> {
  return semanticRequest(
    `/knowledge-objects/${encodeURIComponent(knowledgeObjectId)}/merge`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    }
  )
}

export function getDocumentImpact(documentId: string): Promise<DocumentImpactResponse> {
  return semanticRequest(`/documents/${encodeURIComponent(documentId)}/impact`)
}
