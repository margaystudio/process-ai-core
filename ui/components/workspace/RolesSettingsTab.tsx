'use client'

import { OperationalRoleResponse, deleteOperationalRole } from '@/lib/api'

type RolesSettingsTabProps = {
  workspaceId: string
  operationalRoles: OperationalRoleResponse[]
  newRoleName: string
  newRoleDescription: string
  onNewRoleNameChange: (value: string) => void
  onNewRoleDescriptionChange: (value: string) => void
  onCreateRole: (e: React.FormEvent) => Promise<void>
  onDeleteRole: (roleId: string) => Promise<void>
  onGoToUsers: () => void
}

export default function RolesSettingsTab({
  operationalRoles,
  newRoleName,
  newRoleDescription,
  onNewRoleNameChange,
  onNewRoleDescriptionChange,
  onCreateRole,
  onDeleteRole,
  onGoToUsers,
}: RolesSettingsTabProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Roles operativos</h2>
      <p className="text-ink-600 text-sm mb-4">
        Los roles operativos definen en qué carpetas puede actuar cada usuario (ej: Pistero, Cajero). Creá los roles y asignálos a usuarios y a carpetas.
      </p>
      <form onSubmit={onCreateRole} className="flex flex-wrap gap-3 items-end mb-6">
        <div>
          <label className="block text-xs font-medium text-ink-600 mb-1">Nombre del rol</label>
          <input
            type="text"
            value={newRoleName}
            onChange={(e) => onNewRoleNameChange(e.target.value)}
            placeholder="ej: Pistero"
            className="px-3 py-2 border border-ink-300 rounded-md text-sm w-48"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-ink-600 mb-1">Descripción (opcional)</label>
          <input
            type="text"
            value={newRoleDescription}
            onChange={(e) => onNewRoleDescriptionChange(e.target.value)}
            placeholder="Breve descripción"
            className="px-3 py-2 border border-ink-300 rounded-md text-sm w-56"
          />
        </div>
        <button
          type="submit"
          disabled={!newRoleName.trim()}
          className="px-4 py-2 bg-action hover:bg-action-hover disabled:opacity-50 text-white text-sm font-medium rounded-md"
        >
          Crear rol
        </button>
      </form>
      <div className="space-y-2">
        {operationalRoles.length === 0 && (
          <p className="text-ink-500">No hay roles operativos. Creá uno arriba.</p>
        )}
        {operationalRoles.map((role) => (
          <div
            key={role.id}
            className="flex items-center justify-between py-2 px-3 bg-ink-50 rounded-md"
          >
            <div>
              <span className="font-medium">{role.name}</span>
              {role.description && (
                <span className="text-ink-500 text-sm ml-2">— {role.description}</span>
              )}
            </div>
            <button
              onClick={async () => {
                if (!confirm('¿Eliminar este rol operativo? Se quitará de todos los usuarios y carpetas.')) return
                await onDeleteRole(role.id)
              }}
              className="text-danger hover:text-danger text-sm"
            >
              Eliminar
            </button>
          </div>
        ))}
      </div>
      <p className="mt-6 text-sm text-ink-500">
        Para asignar estos roles a usuarios, andá a la pestaña{' '}
        <button
          type="button"
          onClick={onGoToUsers}
          className="text-accent hover:underline"
        >
          Usuarios
        </button>{' '}
        y usá &quot;Asignar roles operativos&quot; en cada miembro.
      </p>
    </div>
  )
}
