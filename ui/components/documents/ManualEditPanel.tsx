'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { X } from 'lucide-react'
import { getEditableContent, saveEditableContent, submitVersionForReview } from '@/lib/api'
import ManualEditorTiptap, { type ManualEditorTiptapRef } from './ManualEditorTiptap'

function formatSavedAt(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Guardado hace un momento'
    if (diffMins < 60) return `Guardado hace ${diffMins} min`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `Guardado hace ${diffHours} h`
    const diffDays = Math.floor(diffHours / 24)
    return `Guardado hace ${diffDays} día(s)`
  } catch {
    return 'Guardado'
  }
}

interface ManualEditPanelProps {
  documentId: string
  workspaceId: string
  userId: string | null
  onCancel: () => void
  onSaved?: () => void
  onSubmitForReview?: () => void
}

export default function ManualEditPanel({
  documentId,
  workspaceId,
  userId,
  onCancel,
  onSaved,
  onSubmitForReview,
}: ManualEditPanelProps) {
  const [html, setHtml] = useState<string>('')
  const [versionId, setVersionId] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [justSaved, setJustSaved] = useState(false)
  const editorRef = useRef<ManualEditorTiptapRef | null>(null)

  const loadContent = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getEditableContent(documentId)
      setHtml(data.html)
      setVersionId(data.version_id)
      setSavedAt(data.updated_at)
      setDirty(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al cargar contenido')
    } finally {
      setLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadContent()
  }, [loadContent])

  const handleSave = useCallback(
    async (newHtml: string) => {
      setSaving(true)
      setError(null)
      try {
        const res = await saveEditableContent(documentId, newHtml)
        setHtml(newHtml)
        setSavedAt(res.updated_at)
        setDirty(false)
        setJustSaved(true)
        onSaved?.()
        setTimeout(() => setJustSaved(false), 3000)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Error al guardar')
      } finally {
        setSaving(false)
      }
    },
    [documentId, onSaved]
  )

  const handleSubmitForReview = useCallback(async () => {
    if (!versionId || !userId || !workspaceId) {
      setError('Falta usuario o workspace para enviar a validación.')
      return
    }
    const currentHtml = editorRef.current?.getHtml() ?? html
    setSubmitting(true)
    setError(null)
    try {
      await saveEditableContent(documentId, currentHtml)
      await submitVersionForReview(documentId, versionId, userId, workspaceId)
      setDirty(false)
      onSubmitForReview?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al enviar a validación')
    } finally {
      setSubmitting(false)
    }
  }, [documentId, versionId, userId, workspaceId, html, onSubmitForReview])

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault()
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  if (loading) {
    return (
      <div className="bg-white border-2 border-ink-200 rounded-lg p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-ink-200 rounded w-1/3" />
          <div className="h-4 bg-ink-100 rounded w-full" />
          <div className="h-4 bg-ink-100 rounded w-full" />
          <div className="h-64 bg-ink-100 rounded" />
        </div>
        <p className="text-sm text-ink-500 mt-4 text-center">Cargando contenido editable...</p>
      </div>
    )
  }

  if (error && !html) {
    return (
      <div className="bg-white border-2 border-danger-bd rounded-lg p-6">
        <p className="text-danger mb-4">{error}</p>
        <div className="flex gap-3">
          <button type="button" onClick={() => loadContent()} className="px-4 py-2 bg-ink-200 rounded-lg hover:bg-ink-300">
            Reintentar
          </button>
          <button type="button" onClick={onCancel} className="px-4 py-2 border border-ink-300 rounded-lg hover:bg-ink-50">
            Cancelar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white border-2 border-ink-200 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 className="text-h2 text-ink-900">Edición Manual</h3>
        <button
          type="button"
          onClick={() => {
            if (dirty && !window.confirm('Hay cambios sin guardar. ¿Salir de todos modos?')) return
            onCancel()
          }}
          disabled={saving || submitting}
          className="text-ink-400 hover:text-ink-600 p-1"
          aria-label="Cerrar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {(savedAt || justSaved) && (
        <p className={`text-sm mb-2 ${justSaved ? 'text-success font-medium' : 'text-ink-500'}`}>
          {justSaved ? 'Guardado correctamente' : formatSavedAt(savedAt!)}
        </p>
      )}

      {error && (
        <div className="mb-4 p-3 bg-danger-bg border border-danger-bd rounded-lg text-danger text-sm" role="alert">
          {error}
        </div>
      )}

      <ManualEditorTiptap
        documentId={documentId}
        initialHtml={html}
        onSave={handleSave}
        onDirtyChange={setDirty}
        saving={saving}
        editorRef={editorRef}
      />

      <div className="mt-4 flex items-center gap-3 flex-wrap">
        <button
          type="button"
          onClick={handleSubmitForReview}
          disabled={submitting || saving || !userId || !workspaceId || !versionId}
          className="px-4 py-2 bg-create text-white rounded-lg hover:bg-create-hover disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {submitting ? 'Enviando...' : 'Enviar a validación'}
        </button>
        <button
          type="button"
          onClick={() => {
            if (dirty && !window.confirm('Hay cambios sin guardar. ¿Salir de todos modos?')) return
            onCancel()
          }}
          disabled={saving || submitting}
          className="px-4 py-2 border border-ink-300 rounded-lg hover:bg-ink-50 font-medium"
        >
          Cancelar
        </button>
        {dirty && (
          <span className="text-sm text-warning">Hay cambios sin guardar</span>
        )}
      </div>
    </div>
  )
}
