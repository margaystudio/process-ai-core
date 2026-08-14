'use client'

import Link from 'next/link'
import { Lock } from 'lucide-react'
import { Folder } from '@/lib/api'
import { Badge } from '@/shared/ui/components'
import FolderCrud, { DEFAULT_FOLDER_COLOR } from '@/components/processes/FolderCrud'

type FoldersSettingsTabProps = {
  workspaceId: string
  folders: Folder[]
  onFoldersChange: () => Promise<void>
}

/**
 * Indicador discreto de si la carpeta tiene lista de roles (propia o
 * heredada) o está abierta a todos los miembros. La regla de producto que
 * comunica: en las abiertas, cada miembro actúa según su nivel de acceso
 * máximo; para controlar quién hace qué en una carpeta puntual, hay que
 * restringirla.
 */
function FolderAccessIndicator({ restricted }: { restricted: boolean }) {
  if (restricted) {
    return (
      <Badge variant="warning" dot={false} title="Solo entran los roles operativos con acceso a esta carpeta.">
        <Lock className="h-3 w-3" aria-hidden="true" />
        Restringida
      </Badge>
    )
  }
  return (
    <span
      className="flex-shrink-0 text-xs text-ink-400"
      title="Carpeta abierta: cada miembro actúa según su nivel de acceso máximo. Para controlar quién hace qué acá, restringila."
    >
      Todos
    </span>
  )
}

export default function FoldersSettingsTab({
  workspaceId,
  folders,
  onFoldersChange,
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
        Qué roles operativos pueden acceder a cada carpeta se define desde Carpetas, donde también
        se ve el árbol completo y de dónde viene la herencia. Desde acá solo podés revisar el
        estado y saltar directo a esa pestaña.
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
                <FolderAccessIndicator restricted={Boolean(folder.permissions_restricted)} />
              </span>
              <Link
                href={`/folders?folder=${folder.id}&tab=permisos`}
                className="px-3 py-1.5 text-sm bg-accent-tint hover:bg-accent-tint text-accent-ink rounded-md flex-shrink-0 ml-2"
              >
                Permisos
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
