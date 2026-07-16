'use client'

/**
 * Hook canónico de mutaciones de carpetas.
 *
 * Centraliza TODA la lógica de creación, actualización y borrado para que
 * FolderCrud y FolderTree compartan las mismas reglas. Tras cada mutación
 * exitosa invalida la cache de `useFolders` (via `invalidateFoldersCache`)
 * para que todos los consumidores de lectura queden sincronizados.
 *
 * Uso:
 *   const { createFolder, renameFolder, recolorFolder, updateFolder,
 *           deleteFolder, reparentFolder, saving, error, clearError } = useFolderCrud(workspaceId)
 *
 * Cada función lanza si el backend responde con error; el componente captura
 * y decide cómo mostrar el error al usuario.
 */

import { useCallback, useState } from 'react'
import {
  createFolder as apiCreateFolder,
  updateFolder as apiUpdateFolder,
  deleteFolder as apiDeleteFolder,
  type Folder,
  type FolderCreateRequest,
} from '@/lib/api'
import { invalidateFoldersCache } from '@/hooks/useFolders'

// ── Tipos públicos ────────────────────────────────────────────────────────────

export interface CreateFolderInput {
  name: string
  parentId?: string | null
  /** Color hex del picker; si se omite el backend asigna el default. */
  color?: string
  /**
   * Opcional: path explícito. Si no se provee, se calcula a partir del
   * nombre y del path del padre (si hay).
   */
  path?: string
  /**
   * Posición en la lista de hermanos (0-based). Si se omite, va al final.
   */
  sortOrder?: number
  /**
   * Carpetas del workspace; necesario para calcular el path automático
   * cuando hay parentId y no se provee path explícito.
   */
  allFolders?: Folder[]
}

export interface DeleteFolderOptions {
  /** ID de la carpeta destino a la que mover los documentos antes de borrar. */
  moveDocumentsTo?: string
}

export interface UseFolderCrudResult {
  /**
   * true mientras cualquier mutación está en vuelo.
   * Útil para deshabilitar botones y mostrar estados de carga.
   */
  saving: boolean
  /**
   * Último error de mutación (string listo para mostrar al usuario).
   * Se limpia automáticamente al iniciar la siguiente operación.
   */
  error: string | null
  /**
   * Limpia el error manualmente (útil al cerrar un formulario).
   */
  clearError: () => void

  /**
   * Crea una carpeta nueva.
   * Invalida la cache de carpetas tras éxito.
   * @returns La carpeta creada por el backend.
   */
  createFolder: (input: CreateFolderInput) => Promise<Folder>

  /**
   * Renombra una carpeta. Solo actualiza `name`, sin tocar `path` (mismo
   * comportamiento que el árbol de biblioteca). Ojo: el backend NO recalcula el
   * path desde el name, así que si necesitás actualizar el path usá
   * `updateFolder(id, { name, path })`. Invalida la cache tras éxito.
   * @returns La carpeta actualizada.
   */
  renameFolder: (id: string, name: string) => Promise<Folder>

  /**
   * Cambia el color de una carpeta.
   * Previsto para soporte futuro de ícono: se puede extender con `icon?: string`.
   * Invalida la cache de carpetas tras éxito.
   * @returns La carpeta actualizada.
   */
  recolorFolder: (id: string, color: string) => Promise<Folder>

  /**
   * Renombra y/o recolorea en una sola llamada.
   * Útil para el formulario de edición de FolderCrud donde ambos campos se guardan juntos.
   * Invalida la cache de carpetas tras éxito.
   * @returns La carpeta actualizada.
   */
  updateFolder: (
    id: string,
    fields: {
      name?: string
      color?: string
      path?: string
      icon?: string | null
      default_document_type?: string | null
      tyto_enabled?: boolean | null
      allow_document_override?: boolean
      metadata?: Record<string, any>
    }
  ) => Promise<Folder>

  /**
   * Elimina una carpeta.
   * Si `options.moveDocumentsTo` está presente, el backend mueve los
   * documentos antes de borrar (el backend valida que la carpeta destino exista).
   * Invalida la cache de carpetas tras éxito.
   */
  deleteFolder: (id: string, options?: DeleteFolderOptions) => Promise<void>

  /**
   * Mueve una carpeta a otro padre (o la promueve a raíz con newParentId=null).
   * El backend valida que no se genere un ciclo.
   * Invalida la cache de carpetas tras éxito.
   * @returns La carpeta actualizada.
   */
  reparentFolder: (id: string, newParentId: string | null) => Promise<Folder>
}

// ── Helpers internos ──────────────────────────────────────────────────────────

function buildPath(name: string, parentId: string | null | undefined, allFolders: Folder[]): string {
  if (!parentId) return name
  const parent = allFolders.find((f) => f.id === parentId)
  if (!parent) return name
  const parentPath = parent.path || parent.name
  return `${parentPath}/${name}`
}

function normalizeError(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useFolderCrud(workspaceId: string): UseFolderCrudResult {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clearError = useCallback(() => setError(null), [])

  const invalidate = useCallback(() => {
    invalidateFoldersCache(workspaceId)
  }, [workspaceId])

  const createFolder = useCallback(
    async (input: CreateFolderInput): Promise<Folder> => {
      if (!input.name.trim()) throw new Error('El nombre es requerido')
      setError(null)
      setSaving(true)
      try {
        const path =
          input.path?.trim() ||
          buildPath(input.name.trim(), input.parentId ?? null, input.allFolders ?? [])

        const folder = await apiCreateFolder({
          name: input.name.trim(),
          path,
          parent_id: input.parentId ?? undefined,
          sort_order: input.sortOrder,
          color: input.color,
        })
        invalidate()
        return folder
      } catch (err) {
        const msg = normalizeError(err, 'Error al crear carpeta')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  const renameFolder = useCallback(
    async (id: string, name: string): Promise<Folder> => {
      if (!name.trim()) throw new Error('El nombre es requerido')
      setError(null)
      setSaving(true)
      try {
        const folder = await apiUpdateFolder(id, { name: name.trim() })
        invalidate()
        return folder
      } catch (err) {
        const msg = normalizeError(err, 'Error al renombrar carpeta')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  const recolorFolder = useCallback(
    async (id: string, color: string): Promise<Folder> => {
      setError(null)
      setSaving(true)
      try {
        const folder = await apiUpdateFolder(id, { color })
        invalidate()
        return folder
      } catch (err) {
        const msg = normalizeError(err, 'Error al cambiar el color')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  const updateFolder = useCallback(
    async (
      id: string,
      fields: {
        name?: string
        color?: string
        path?: string
        icon?: string | null
        default_document_type?: string | null
        tyto_enabled?: boolean | null
        allow_document_override?: boolean
        metadata?: Record<string, any>
      }
    ): Promise<Folder> => {
      if (fields.name !== undefined && !fields.name.trim()) {
        throw new Error('El nombre es requerido')
      }
      setError(null)
      setSaving(true)
      try {
        const payload: Partial<FolderCreateRequest> = {}
        if (fields.name !== undefined) payload.name = fields.name.trim()
        if (fields.color !== undefined) payload.color = fields.color
        if (fields.icon !== undefined) payload.icon = fields.icon
        if (fields.default_document_type !== undefined) payload.default_document_type = fields.default_document_type
        if (fields.tyto_enabled !== undefined) payload.tyto_enabled = fields.tyto_enabled
        if (fields.allow_document_override !== undefined) payload.allow_document_override = fields.allow_document_override
        // El backend NO recalcula el path desde el name: si no se envía, queda
        // stale al renombrar. Preservamos el envío explícito del path.
        if (fields.path !== undefined) payload.path = fields.path
        if (fields.metadata !== undefined) payload.metadata = fields.metadata
        const folder = await apiUpdateFolder(id, payload)
        invalidate()
        return folder
      } catch (err) {
        const msg = normalizeError(err, 'Error al actualizar carpeta')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  const deleteFolder = useCallback(
    async (id: string, options?: DeleteFolderOptions): Promise<void> => {
      setError(null)
      setSaving(true)
      try {
        await apiDeleteFolder(id, options?.moveDocumentsTo)
        invalidate()
      } catch (err) {
        const msg = normalizeError(err, 'Error al eliminar carpeta')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  const reparentFolder = useCallback(
    async (id: string, newParentId: string | null): Promise<Folder> => {
      setError(null)
      setSaving(true)
      try {
        const folder = await apiUpdateFolder(id, {
          parent_id: newParentId ?? undefined,
        })
        invalidate()
        return folder
      } catch (err) {
        const msg = normalizeError(err, 'Error al mover carpeta')
        setError(msg)
        throw err
      } finally {
        setSaving(false)
      }
    },
    [invalidate],
  )

  return {
    saving,
    error,
    clearError,
    createFolder,
    renameFolder,
    recolorFolder,
    updateFolder,
    deleteFolder,
    reparentFolder,
  }
}
