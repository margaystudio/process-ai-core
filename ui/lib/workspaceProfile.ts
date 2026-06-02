import type { WorkspaceResponse } from '@/lib/api'

export const WORKSPACE_PROFILE_BANNER_MESSAGE =
  'Completá el perfil del espacio de trabajo para obtener mejores documentos generados por IA.'

export function isWorkspaceProfileIncomplete(ws: {
  country?: string | null
  language_style?: string | null
}): boolean {
  return !ws.country || !ws.language_style
}

/** Roles que deben ver el aviso de perfil incompleto en la UI principal. */
export function shouldPromptWorkspaceProfile(
  role: string | null,
  platformRoles: string[] = []
): boolean {
  if (platformRoles.includes('superadmin')) return true
  return role === 'admin' || role === 'owner' || role === 'creator'
}

export function workspaceSettingsGeneralUrl(workspaceId: string): string {
  return `/workspace/${workspaceId}/settings?tab=general`
}
