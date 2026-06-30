'use client'

/**
 * Formulario de edición de metadatos del documento (nombre, descripción, estado,
 * campos process-específicos: audiencia, nivel de detalle, contexto).
 * Se muestra cuando isEditing=true en la vista de detalle.
 */

import { Button } from '@/shared/ui/components/button'
import FolderTree from '@/components/processes/FolderTree'
import type { CatalogOption, Document } from '@/lib/api'

interface DocumentMetadataFormProps {
  document: Document
  workspaceId: string | null
  // valores del form
  name: string
  onNameChange: (v: string) => void
  description: string
  onDescriptionChange: (v: string) => void
  status: string
  onStatusChange: (v: string) => void
  folderId: string
  onFolderIdChange: (v: string) => void
  // campos process-específicos
  audience: string
  onAudienceChange: (v: string) => void
  detailLevel: string
  onDetailLevelChange: (v: string) => void
  contextText: string
  onContextTextChange: (v: string) => void
  audienceOptions: CatalogOption[]
  detailLevelOptions: CatalogOption[]
  // acciones
  isSaving: boolean
  onSave: () => void
  onCancel: () => void
}

export function DocumentMetadataForm({
  document,
  workspaceId,
  name,
  onNameChange,
  description,
  onDescriptionChange,
  status,
  onStatusChange,
  folderId,
  onFolderIdChange,
  audience,
  onAudienceChange,
  detailLevel,
  onDetailLevelChange,
  contextText,
  onContextTextChange,
  audienceOptions,
  detailLevelOptions,
  isSaving,
  onSave,
  onCancel,
}: DocumentMetadataFormProps) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* Árbol de carpetas */}
      {workspaceId && (
        <div className="lg:col-span-1">
          <p className="mb-2 text-sm font-medium text-ink-700">Carpeta</p>
          <FolderTree
            workspaceId={workspaceId}
            selectedFolderId={folderId}
            onSelectFolder={(id) => onFolderIdChange(id || '')}
            showSelectable={true}
            showCrud={false}
          />
        </div>
      )}

      {/* Formulario */}
      <div className={workspaceId ? 'lg:col-span-2' : 'lg:col-span-3'}>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            onSave()
          }}
          className="space-y-5"
        >
          <div>
            <label htmlFor="doc-name" className="mb-1.5 block text-sm font-medium text-ink-700">
              Nombre <span className="text-danger" aria-hidden="true">*</span>
            </label>
            <input
              id="doc-name"
              type="text"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              required
              className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
            />
          </div>

          <div>
            <label
              htmlFor="doc-description"
              className="mb-1.5 block text-sm font-medium text-ink-700"
            >
              Descripción
            </label>
            <textarea
              id="doc-description"
              value={description}
              onChange={(e) => onDescriptionChange(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
            />
          </div>

          <div>
            <label
              htmlFor="doc-status"
              className="mb-1.5 block text-sm font-medium text-ink-700"
            >
              Estado
            </label>
            <select
              id="doc-status"
              value={status}
              onChange={(e) => onStatusChange(e.target.value)}
              className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
            >
              <option value="draft">Borrador</option>
              <option value="pending_validation">Pendiente de validación</option>
              <option value="approved">Aprobado</option>
              <option value="rejected">Rechazado</option>
              <option value="archived">Archivado</option>
            </select>
          </div>

          {document.domain === 'process' && (
            <>
              <div>
                <label
                  htmlFor="doc-audience"
                  className="mb-1.5 block text-sm font-medium text-ink-700"
                >
                  Audiencia
                </label>
                <select
                  id="doc-audience"
                  value={audience}
                  onChange={(e) => onAudienceChange(e.target.value)}
                  className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
                >
                  <option value="">Seleccionar…</option>
                  {audienceOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="doc-detail-level"
                  className="mb-1.5 block text-sm font-medium text-ink-700"
                >
                  Nivel de detalle
                </label>
                <select
                  id="doc-detail-level"
                  value={detailLevel}
                  onChange={(e) => onDetailLevelChange(e.target.value)}
                  className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
                >
                  <option value="">Seleccionar…</option>
                  {detailLevelOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="doc-context"
                  className="mb-1.5 block text-sm font-medium text-ink-700"
                >
                  Contexto
                </label>
                <textarea
                  id="doc-context"
                  value={contextText}
                  onChange={(e) => onContextTextChange(e.target.value)}
                  rows={4}
                  placeholder="Contexto adicional del proceso…"
                  className="w-full rounded-md border border-line-input px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-action-ring"
                />
              </div>
            </>
          )}

          <div className="flex gap-3 border-t border-ink-200 pt-5">
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={isSaving || !name.trim()}
            >
              {isSaving ? 'Guardando…' : 'Guardar'}
            </Button>
            <Button type="button" variant="secondary" size="md" onClick={onCancel}>
              Cancelar
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
