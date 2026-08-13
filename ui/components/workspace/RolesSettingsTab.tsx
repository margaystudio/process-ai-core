'use client'

import { useState } from 'react'
import { OperationalRoleAccessLevel, OperationalRoleResponse } from '@/lib/api'
import { ACCESS_LEVEL_BADGE_VARIANT, ACCESS_LEVEL_DESCRIPTION, ACCESS_LEVEL_LABEL } from '@/lib/accessLevels'
import { Badge, Button, OptionSet } from '@/shared/ui/components'

type RolesSettingsTabProps = {
  workspaceId: string
  operationalRoles: OperationalRoleResponse[]
  newRoleName: string
  newRoleDescription: string
  newRoleAccessLevel: OperationalRoleAccessLevel
  onNewRoleNameChange: (value: string) => void
  onNewRoleDescriptionChange: (value: string) => void
  onNewRoleAccessLevelChange: (value: OperationalRoleAccessLevel) => void
  onCreateRole: (e: React.FormEvent) => Promise<void>
  onDeleteRole: (roleId: string) => Promise<void>
  onUpdateRoleAccessLevel: (roleId: string, accessLevel: OperationalRoleAccessLevel) => Promise<void>
  onGoToUsers: () => void
}

const ACCESS_LEVEL_OPTIONS: { value: OperationalRoleAccessLevel; label: string }[] = [
  { value: 'lectura', label: 'Lectura' },
  { value: 'edicion', label: 'Edición' },
  { value: 'aprobacion', label: 'Aprobación' },
]

/** Selector de nivel de acceso: 3 opciones + descripción corta de la elegida. */
function AccessLevelSelector({
  value,
  onChange,
  idPrefix,
}: {
  value: OperationalRoleAccessLevel
  onChange: (value: OperationalRoleAccessLevel) => void
  idPrefix: string
}) {
  return (
    <div>
      <span id={`${idPrefix}-label`} className="mb-1 block text-xs font-medium text-ink-600">
        Nivel de acceso
      </span>
      <div aria-labelledby={`${idPrefix}-label`}>
        <OptionSet
          options={ACCESS_LEVEL_OPTIONS}
          value={value}
          onChange={(v) => onChange(v as OperationalRoleAccessLevel)}
        />
      </div>
      <p className="mt-1.5 text-xs text-ink-500">{ACCESS_LEVEL_DESCRIPTION[value]}</p>
    </div>
  )
}

export default function RolesSettingsTab({
  operationalRoles,
  newRoleName,
  newRoleDescription,
  newRoleAccessLevel,
  onNewRoleNameChange,
  onNewRoleDescriptionChange,
  onNewRoleAccessLevelChange,
  onCreateRole,
  onDeleteRole,
  onUpdateRoleAccessLevel,
  onGoToUsers,
}: RolesSettingsTabProps) {
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null)
  const [editingAccessLevel, setEditingAccessLevel] = useState<OperationalRoleAccessLevel>('edicion')
  const [savingRoleId, setSavingRoleId] = useState<string | null>(null)

  function startEdit(role: OperationalRoleResponse) {
    setEditingRoleId(role.id)
    setEditingAccessLevel(role.access_level)
  }

  async function saveEdit(roleId: string) {
    setSavingRoleId(roleId)
    try {
      await onUpdateRoleAccessLevel(roleId, editingAccessLevel)
      setEditingRoleId(null)
    } finally {
      setSavingRoleId(null)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Roles operativos</h2>
      <p className="text-ink-600 text-sm mb-4">
        Los roles operativos definen en qué carpetas puede actuar cada usuario (ej: Pistero, Cajero) y
        qué nivel de acceso tiene ahí. Creá los roles y asignálos a usuarios y a carpetas.
      </p>
      <form onSubmit={onCreateRole} className="mb-6 space-y-4 rounded-md border border-ink-200 p-4">
        <div className="flex flex-wrap items-end gap-3">
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
        </div>
        <div className="max-w-md">
          <AccessLevelSelector
            value={newRoleAccessLevel}
            onChange={onNewRoleAccessLevelChange}
            idPrefix="new-role-access-level"
          />
        </div>
        <Button type="submit" variant="create" size="sm" disabled={!newRoleName.trim()}>
          Crear rol
        </Button>
      </form>
      <div className="space-y-2">
        {operationalRoles.length === 0 && (
          <p className="text-ink-500">No hay roles operativos. Creá uno arriba.</p>
        )}
        {operationalRoles.map((role) => (
          <div key={role.id} className="rounded-md bg-ink-50 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="font-medium">{role.name}</span>
                {role.description && (
                  <span className="text-ink-500 text-sm">— {role.description}</span>
                )}
                <Badge variant={ACCESS_LEVEL_BADGE_VARIANT[role.access_level]}>
                  {ACCESS_LEVEL_LABEL[role.access_level]}
                </Badge>
              </div>
              <div className="flex items-center gap-3">
                {editingRoleId !== role.id && (
                  <button
                    onClick={() => startEdit(role)}
                    className="text-accent hover:underline text-sm"
                  >
                    Editar
                  </button>
                )}
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
            </div>
            {editingRoleId === role.id && (
              <div className="mt-3 max-w-md border-t border-ink-200 pt-3">
                <AccessLevelSelector
                  value={editingAccessLevel}
                  onChange={setEditingAccessLevel}
                  idPrefix={`edit-role-${role.id}-access-level`}
                />
                <div className="mt-3 flex gap-2">
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={() => saveEdit(role.id)}
                    disabled={savingRoleId === role.id}
                  >
                    {savingRoleId === role.id ? 'Guardando…' : 'Guardar'}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setEditingRoleId(null)}
                    disabled={savingRoleId === role.id}
                  >
                    Cancelar
                  </Button>
                </div>
              </div>
            )}
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
