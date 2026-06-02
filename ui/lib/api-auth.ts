/**
 * Utilidades para agregar autenticación a las requests de la API.
 */

import { createClient } from '@/lib/supabase/client'

export const ACTIVE_TENANT_STORAGE_KEY = 'active_tenant_id'

/**
 * Tenant activo elegido en el selector (margay-workspace tenant id).
 */
export function getActiveTenantId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(ACTIVE_TENANT_STORAGE_KEY)
}

export function setActiveTenantId(tenantId: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(ACTIVE_TENANT_STORAGE_KEY, tenantId)
}

export async function getAccessToken(): Promise<string | null> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token || null
}

export async function getAuthHeaders(
  additionalHeaders: Record<string, string> = {}
): Promise<HeadersInit> {
  const token = await getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...additionalHeaders,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const activeTenantId = getActiveTenantId()
  if (activeTenantId) {
    headers['X-Active-Tenant-Id'] = activeTenantId
  }

  return headers
}
