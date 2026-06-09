'use client'

import { useState, useEffect } from 'react'
import { listFolders, Folder } from '@/lib/api'

interface FolderSelectorProps {
  workspaceId: string
  value: string
  onChange: (value: string) => void
  required?: boolean
}

export default function FolderSelector({ workspaceId, value, onChange, required = false }: FolderSelectorProps) {
  const [folders, setFolders] = useState<Folder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) {
      setLoading(false)
      return
    }

    async function loadFolders() {
      try {
        setLoading(true)
        setError(null)
        const data = await listFolders(workspaceId)
        setFolders(data)
      } catch (err) {
        console.error('Error cargando carpetas:', err)
        setError(err instanceof Error ? err.message : 'Error desconocido')
      } finally {
        setLoading(false)
      }
    }

    loadFolders()
  }, [workspaceId])

  return (
    <div>
      <label htmlFor="folder" className="block text-sm font-medium text-ink-700 mb-2">
        Ubicación (Carpeta) {required && '*'}
      </label>
      {loading ? (
        <div className="w-full px-4 py-2 border border-ink-300 rounded-md bg-ink-100 animate-pulse">
          Cargando carpetas...
        </div>
      ) : error ? (
        <div className="w-full px-4 py-2 border border-danger-bd rounded-md bg-danger-bg text-danger text-sm">
          Error: {error}
        </div>
      ) : folders.length === 0 ? (
        <div className="w-full px-4 py-2 border border-ink-300 rounded-md bg-ink-50 text-ink-500 text-sm">
          No hay carpetas disponibles. Crea una carpeta primero.
        </div>
      ) : (
        <select
          id="folder"
          name="folder"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          className="w-full px-4 py-2 border border-ink-300 rounded-md focus:ring-2 focus:ring-action-ring focus:border-accent"
        >
          <option value="">Seleccionar carpeta...</option>
          {folders.map((folder) => (
            <option key={folder.id} value={folder.id}>
              {folder.path || folder.name}
            </option>
          ))}
        </select>
      )}
      <p className="mt-1 text-sm text-ink-500">
        La ubicación del proceso ayuda a inferir el contexto y tipo de proceso.
      </p>
    </div>
  )
}



