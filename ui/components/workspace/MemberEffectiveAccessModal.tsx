'use client'

import { Check, Minus } from 'lucide-react'
import { useAsync } from '@/hooks/useAsync'
import {
  getMemberEffectiveAccess,
  type MemberEffectiveAccessFolder,
  type MemberEffectiveAccessRole,
  type WorkspaceMember,
} from '@/lib/api'
import {
  ACCESS_LEVEL_BADGE_VARIANT,
  ACCESS_LEVEL_LABEL,
  WORKSPACE_ACCESS_ROLE_BADGE_VARIANT,
  WORKSPACE_ACCESS_ROLE_LABEL,
} from '@/lib/accessLevels'
import { Badge, Dialog } from '@/shared/ui/components'

/** Indicador sí/no del design system para tablas: check verde o guion apagado (sin emojis). */
function AccessMark({ granted, label }: { granted: boolean; label: string }) {
  return (
    <span
      role="img"
      aria-label={`${label}: ${granted ? 'sí' : 'no'}`}
      className="inline-flex items-center justify-center"
    >
      {granted ? (
        <Check className="h-4 w-4 text-success" aria-hidden="true" />
      ) : (
        <Minus className="h-4 w-4 text-ink-300" aria-hidden="true" />
      )}
    </span>
  )
}

/** Profundidad para indentar según `path` (ej. "Pista/Turnos" → 1). */
function folderDepth(path: string): number {
  return Math.max(0, path.split('/').length - 1)
}

function grantedRoleNames(
  folder: MemberEffectiveAccessFolder,
  roles: MemberEffectiveAccessRole[]
): string {
  return folder.granted_by_role_ids
    .map((id) => roles.find((r) => r.id === id)?.name)
    .filter((name): name is string => Boolean(name))
    .join(', ')
}

/** Texto secundario bajo el nombre de la carpeta: solo aplica a carpetas restringidas. */
function FolderAccessNote({
  folder,
  roles,
}: {
  folder: MemberEffectiveAccessFolder
  roles: MemberEffectiveAccessRole[]
}) {
  if (!folder.restricted) return null

  const entra = folder.granted_by_role_ids.length > 0
  if (entra) {
    return (
      <div className="text-xs text-ink-400">
        por «{grantedRoleNames(folder, roles) || '—'}»
      </div>
    )
  }

  const inheritedFromSelf = folder.source_folder_id === folder.id
  return (
    <div className="text-xs text-danger">
      {inheritedFromSelf ? (
        'Restringida en esta carpeta'
      ) : (
        <>Restringida — hereda de «{folder.source_folder_name}»</>
      )}
    </div>
  )
}

/**
 * Visor de acceso efectivo de un miembro: la vista "¿por qué Juan no puede
 * aprobar esta carpeta?" para el admin. Un solo GET
 * (`getMemberEffectiveAccess`, admin-only) resuelve herencia + roles
 * operativos + bypass de admin — el front no recalcula nada de eso acá.
 */
export default function MemberEffectiveAccessModal({
  workspaceId,
  member,
  onClose,
}: {
  workspaceId: string
  /** `null` = cerrado. */
  member: WorkspaceMember | null
  onClose: () => void
}) {
  const { status, data, error, reload } = useAsync(
    () =>
      member
        ? getMemberEffectiveAccess(workspaceId, member.membership_id)
        : Promise.resolve(undefined),
    [workspaceId, member?.membership_id]
  )

  const isLoading = status === 'idle' || status === 'loading'

  // El Dialog se mantiene montado (solo cambia `open`) en vez de desmontarse
  // al cerrar: así corre su propio efecto de restaurar el foco al elemento
  // que lo abrió — el mismo patrón que el resto de los modales de la app
  // (ej. relations/page.tsx). Los datos del cuerpo son opcionales porque en
  // el frame de cierre `member` ya puede ser `null`; Dialog igual no los
  // renderiza (retorna `null` internamente cuando `open` es falso).
  return (
    <Dialog
      open={Boolean(member)}
      onClose={onClose}
      title={member?.name || member?.email || ''}
      maxWidth="max-w-2xl"
    >
      {/* `member` puede ser `null` en el frame de cierre (Dialog no llega a
          renderizar esto porque retorna `null` internamente cuando
          `open` es falso, pero JSX igual evalúa las expresiones de abajo). */}
      {member && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <p className="text-sm text-ink-500">{member.email}</p>
          <Badge variant={WORKSPACE_ACCESS_ROLE_BADGE_VARIANT[member.role]}>
            {WORKSPACE_ACCESS_ROLE_LABEL[member.role]}
          </Badge>
        </div>
      )}

      {isLoading && (
        <div className="space-y-2" aria-busy="true" aria-label="Cargando acceso efectivo">
          <div className="h-5 w-2/3 animate-pulse rounded bg-ink-100" />
          <div className="h-28 animate-pulse rounded bg-ink-100" />
        </div>
      )}

      {status === 'error' && (
        <div className="rounded-md border border-danger-bd bg-danger-bg p-4">
          <p className="mb-2 text-sm text-danger">{error}</p>
          <button
            type="button"
            onClick={reload}
            className="text-sm font-semibold text-danger underline"
          >
            Reintentar
          </button>
        </div>
      )}

      {status === 'success' && data && (
        data.is_admin ? (
          <div className="rounded-md border border-info-bd bg-info-bg p-4 text-sm text-info">
            Acceso total: administra el workspace y ve todas las carpetas.
          </div>
        ) : (
          <>
            <div className="mb-5">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                Roles operativos
              </h3>
              {data.operational_roles.length === 0 ? (
                <p className="text-sm text-ink-400">Sin roles operativos asignados.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {data.operational_roles.map((role) => (
                    <Badge key={role.id} variant={ACCESS_LEVEL_BADGE_VARIANT[role.access_level]}>
                      {role.name} · {ACCESS_LEVEL_LABEL[role.access_level]}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                Acceso por carpeta
              </h3>
              {data.folders.length === 0 ? (
                <p className="text-sm text-ink-400">Este workspace todavía no tiene carpetas.</p>
              ) : (
                <div className="max-h-[360px] overflow-y-auto rounded-md border border-ink-200">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-ink-50 text-xs text-ink-500">
                      <tr>
                        <th scope="col" className="px-3 py-2 text-left font-semibold">
                          Carpeta
                        </th>
                        <th scope="col" className="w-12 px-2 py-2 text-center font-semibold">
                          Ver
                        </th>
                        <th scope="col" className="w-12 px-2 py-2 text-center font-semibold">
                          Crear
                        </th>
                        <th scope="col" className="w-14 px-2 py-2 text-center font-semibold">
                          Aprobar
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {data.folders.map((folder) => (
                        <tr key={folder.id}>
                          <td className="px-3 py-2">
                            <div style={{ paddingLeft: folderDepth(folder.path) * 14 }}>
                              <div className="font-medium text-ink-800">{folder.name}</div>
                              <FolderAccessNote folder={folder} roles={data.operational_roles} />
                            </div>
                          </td>
                          <td className="px-2 py-2 text-center">
                            <AccessMark granted={folder.view} label="Ver" />
                          </td>
                          <td className="px-2 py-2 text-center">
                            <AccessMark granted={folder.create} label="Crear" />
                          </td>
                          <td className="px-2 py-2 text-center">
                            <AccessMark granted={folder.approve} label="Aprobar" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )
      )}
    </Dialog>
  )
}
