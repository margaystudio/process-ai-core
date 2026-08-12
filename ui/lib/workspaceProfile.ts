export const WORKSPACE_PROFILE_BANNER_MESSAGE =
  'Completá el perfil del espacio de trabajo para obtener mejores documentos generados por IA.'

export function isWorkspaceProfileIncomplete(ws: {
  country?: string | null
  language_style?: string | null
}): boolean {
  return !ws.country || !ws.language_style
}

export function workspaceSettingsGeneralUrl(workspaceId: string): string {
  return `/workspace/${workspaceId}/settings?tab=general`
}
