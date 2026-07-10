'use client'

import { OperationalRoleResponse, WorkspaceMember } from '@/lib/api'

type UsersSettingsTabProps = {
  members: WorkspaceMember[]
  operationalRoles: OperationalRoleResponse[]
  canManageUsers: boolean
  editingMemberId: string | null
  memberRoleIds: string[]
  onOpenMemberEdit: (member: WorkspaceMember) => void
  onMemberRoleIdsChange: (ids: string[]) => void
  onSaveMemberRoles: () => Promise<void>
  onCancelEdit: () => void
}

export default function UsersSettingsTab({
  members,
  operationalRoles,
  canManageUsers,
  editingMemberId,
  memberRoleIds,
  onOpenMemberEdit,
  onMemberRoleIdsChange,
  onSaveMemberRoles,
  onCancelEdit,
}: UsersSettingsTabProps) {
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-4">Usuarios</h2>
        <p className="text-sm text-slate-500 mb-4">
          Las invitaciones se gestionan desde el hub de administración.
        </p>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-medium">Miembros del workspace</h3>
        {members.length === 0 ? (
          <p className="text-ink-500">Cargando miembros...</p>
        ) : (
          <div className="divide-y divide-gray-200">
            {members.map((member) => (
              <div key={member.membership_id} className="py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium">{member.name || member.email}</p>
                  <p className="text-sm text-ink-500">
                    {member.email} • Rol: {member.role}
                    {member.operational_role_ids?.length
                      ? ` • Roles operativos: ${member.operational_role_ids.length}`
                      : ''}
                  </p>
                </div>
                {canManageUsers && (
                  <button
                    onClick={() => onOpenMemberEdit(member)}
                    className="px-3 py-1.5 text-sm bg-ink-100 hover:bg-ink-200 rounded-md"
                  >
                    {editingMemberId === member.membership_id ? 'Editando...' : 'Asignar roles operativos'}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {editingMemberId && (
          <div className="mt-4 p-4 bg-ink-50 rounded-lg border border-ink-200">
            <p className="text-sm font-medium mb-3">Seleccionar roles operativos para este usuario</p>
            <div className="flex flex-wrap gap-3">
              {operationalRoles.filter((r) => r.is_active).map((role) => (
                <label key={role.id} className="inline-flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={memberRoleIds.includes(role.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        onMemberRoleIdsChange([...memberRoleIds, role.id])
                      } else {
                        onMemberRoleIdsChange(memberRoleIds.filter((id) => id !== role.id))
                      }
                    }}
                    className="rounded border-ink-300"
                  />
                  <span className="text-sm">{role.name}</span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={onSaveMemberRoles}
                className="px-4 py-2 bg-action hover:bg-action-hover text-white text-sm font-medium rounded-md"
              >
                Guardar
              </button>
              <button
                onClick={onCancelEdit}
                className="px-4 py-2 bg-ink-200 hover:bg-ink-300 text-sm rounded-md"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
