/**
 * Copy y estilos compartidos para los dos niveles de acceso del nuevo modelo
 * de permisos: el acceso BASE del workspace (`WorkspaceAccessRole`) y el
 * nivel de un rol operativo (`OperationalRoleAccessLevel`). Vive en `lib/`
 * (no en un componente) porque lo consumen varias pantallas de
 * `components/workspace/*` (RolesSettingsTab, UsersSettingsTab, el visor de
 * acceso efectivo) y deben verse igual en todas.
 */
import type { OperationalRoleAccessLevel, WorkspaceAccessRole } from './api'

import type { BadgeProps } from '@/shared/ui/components'

type BadgeVariant = NonNullable<BadgeProps['variant']>

/** Acceso base del workspace (hub) — ya no son roles de sistema. */
export const WORKSPACE_ACCESS_ROLE_LABEL: Record<WorkspaceAccessRole, string> = {
  admin: 'Administrador',
  member: 'Miembro',
  external: 'Cliente externo',
}

export const WORKSPACE_ACCESS_ROLE_BADGE_VARIANT: Record<WorkspaceAccessRole, BadgeVariant> = {
  admin: 'info',
  member: 'neutral',
  external: 'warning',
}

/** Nivel de un rol operativo. Cumulativo: 'edicion' incluye 'lectura'; 'aprobacion' incluye 'edicion'. */
export const ACCESS_LEVEL_LABEL: Record<OperationalRoleAccessLevel, string> = {
  lectura: 'Lectura',
  edicion: 'Edición',
  aprobacion: 'Aprobación',
}

export const ACCESS_LEVEL_DESCRIPTION: Record<OperationalRoleAccessLevel, string> = {
  lectura: 'Puede ver y exportar documentos',
  edicion: 'Además puede crear y editar',
  aprobacion: 'Además puede aprobar y rechazar',
}

export const ACCESS_LEVEL_BADGE_VARIANT: Record<OperationalRoleAccessLevel, BadgeVariant> = {
  lectura: 'neutral',
  edicion: 'info',
  aprobacion: 'warning',
}
