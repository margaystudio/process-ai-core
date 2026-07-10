'use client'

import { Folder, FolderPermissionsResponse, OperationalRoleResponse } from '@/lib/api'
import FolderCrud, { DEFAULT_FOLDER_COLOR } from '@/components/processes/FolderCrud'

type FolderPermissionsModal = {
  folder: Folder
  perms: FolderPermissionsResponse
}

type FoldersSettingsTabProps = {
  workspaceId: string
  folders: Folder[]
  operationalRoles: OperationalRoleResponse[]
  folderPermissionsModal: FolderPermissionsModal | null
  folderPermsInherit: boolean
  folderPermsRoleIds: string[]
  onFoldersChange: () => Promise<void>
  onOpenFolderPermissions: (folder: Folder) => Promise<void>
  onFolderPermsInheritChange: (value: boolean) => void
  onFolderPermsRoleIdsChange: (ids: string[]) => void
  onSaveFolderPermissions: () => Promise<void>
  onCloseFolderPermissionsModal: () => void
}

export default function FoldersSettingsTab({
  workspaceId,
  folders,
  operationalRoles,
  folderPermissionsModal,
  folderPermsInherit,
  folderPermsRoleIds,
  onFoldersChange,
  onOpenFolderPermissions,
  onFolderPermsInheritChange,
  onFolderPermsRoleIdsChange,
  onSaveFolderPermissions,
  onCloseFolderPermissionsModal,
}: FoldersSettingsTabProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold mb-2">Gestionar carpetas</h2>
      <p className="text-ink-600 text-sm mb-4">
        Creá, editá o eliminá carpetas y elegí un color para identificarlas en la Biblioteca.
      </p>
      <FolderCrud
        workspaceId={workspaceId}
        folders={folders}
        onFoldersChange={onFoldersChange}
      />

      <hr className="my-8 border-ink-200" />

      <h2 className="text-xl font-semibold mb-4">Acceso por carpeta</h2>
      <p className="text-ink-600 text-sm mb-4">
        Definí qué roles operativos pueden acceder a cada carpeta. Si una carpeta hereda del padre, usa los mismos permisos que la carpeta padre.
      </p>
      {folders.length === 0 ? (
        <p className="text-ink-500">No hay carpetas en este workspace.</p>
      ) : (
        <ul className="space-y-2">
          {folders.map((folder) => (
            <li
              key={folder.id}
              className="flex items-center justify-between py-2 px-3 bg-ink-50 rounded-md"
            >
              <span className="flex items-center gap-2 font-medium min-w-0">
                <span
                  className="h-3 w-3 flex-shrink-0 rounded-full"
                  style={{ backgroundColor: folder.color || DEFAULT_FOLDER_COLOR }}
                  aria-hidden
                />
                <span className="truncate">{folder.name}</span>
              </span>
              <button
                onClick={() => onOpenFolderPermissions(folder)}
                className="px-3 py-1.5 text-sm bg-accent-tint hover:bg-accent-tint text-accent-ink rounded-md flex-shrink-0 ml-2"
              >
                Permisos
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Modal permisos de carpeta */}
      {folderPermissionsModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h3 className="text-lg font-semibold mb-2">
              Permisos: {folderPermissionsModal.folder.name}
            </h3>
            <label className="flex items-center gap-2 mb-4">
              <input
                type="checkbox"
                checked={folderPermsInherit}
                onChange={(e) => onFolderPermsInheritChange(e.target.checked)}
                className="rounded border-ink-300"
              />
              <span className="text-sm">Heredar permisos del padre</span>
            </label>
            {!folderPermsInherit && (
              <div className="mb-4">
                <p className="text-sm font-medium text-ink-700 mb-2">
                  Roles con acceso a esta carpeta
                </p>
                <div className="flex flex-wrap gap-2">
                  {operationalRoles.filter((r) => r.is_active).map((role) => (
                    <label key={role.id} className="inline-flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={folderPermsRoleIds.includes(role.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            onFolderPermsRoleIdsChange([...folderPermsRoleIds, role.id])
                          } else {
                            onFolderPermsRoleIdsChange(
                              folderPermsRoleIds.filter((id) => id !== role.id)
                            )
                          }
                        }}
                        className="rounded border-ink-300"
                      />
                      <span className="text-sm">{role.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={onCloseFolderPermissionsModal}
                className="px-4 py-2 bg-ink-200 hover:bg-ink-300 rounded-md text-sm"
              >
                Cerrar
              </button>
              <button
                onClick={onSaveFolderPermissions}
                className="px-4 py-2 bg-action hover:bg-action-hover text-white rounded-md text-sm"
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
