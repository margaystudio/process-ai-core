'use client'

import { useState } from 'react'
import { Document, getDocumentRuns, getDocumentVersions } from '@/lib/api'
import ArtifactViewerModal from '@/components/processes/ArtifactViewerModal'

interface ViewerModalState {
  isOpen: boolean
  runId: string
  filename: string
  type: 'json' | 'markdown' | 'pdf'
  versionPreviewPdf: { documentId: string; versionId: string } | null
}

interface UsePdfViewerReturn {
  openPdf: (document: Document) => Promise<void>
  /** Abre el PDF más actualizado del documento: usa preview-pdf si hay versión IN_REVIEW o DRAFT con edición manual, si no usa el artifact original. */
  openLatestPdf: (document: Document) => Promise<void>
  openArtifact: (document: Document, artifactType: 'json' | 'markdown' | 'pdf', artifactPath?: string) => Promise<void>
  openArtifactFromRun: (runId: string, filename: string, type: 'json' | 'markdown' | 'pdf') => void
  /** Abre el PDF del borrador actual (incluye edición manual). Usa el mismo modal; la petición va con cookies. */
  openVersionPreviewPdf: (documentId: string, versionId: string) => void
  closeModal: () => void
  ModalComponent: () => JSX.Element
}

/**
 * Hook para manejar la visualización de PDFs y otros artifacts en un modal.
 * 
 * @returns Objeto con función para abrir PDF y componente del modal
 */
export function usePdfViewer(): UsePdfViewerReturn {
  const [viewerModal, setViewerModal] = useState<ViewerModalState>({
    isOpen: false,
    runId: '',
    filename: '',
    type: 'pdf',
    versionPreviewPdf: null,
  })

  const openPdf = async (document: Document) => {
    try {
      const runs = await getDocumentRuns(document.id)
      if (runs.length > 0 && runs[0].artifacts.pdf) {
        const filename = runs[0].artifacts.pdf.split('/').pop() || 'process.pdf'
        setViewerModal({
          isOpen: true,
          runId: runs[0].run_id,
          filename,
          type: 'pdf',
          versionPreviewPdf: null,
        })
      } else {
        alert('No hay PDF disponible para este documento')
      }
    } catch (err) {
      alert('Error al cargar el PDF: ' + (err instanceof Error ? err.message : 'Error desconocido'))
    }
  }

  /**
   * Abre el PDF más actualizado:
   * - Si hay versión IN_REVIEW o DRAFT con edición manual → usa preview-pdf (tiene el contenido editado)
   * - Si no → fallback al process.pdf del run original
   */
  const openLatestPdf = async (document: Document) => {
    try {
      const versions = await getDocumentVersions(document.id)
      // Prioridad: APPROVED > IN_REVIEW > DRAFT (la versión más "final" con posibles ediciones manuales)
      const relevant =
        versions.find((v) => v.version_status === 'APPROVED') ||
        versions.find((v) => v.version_status === 'IN_REVIEW') ||
        versions.find((v) => v.version_status === 'DRAFT')
      if (relevant) {
        setViewerModal({
          isOpen: true,
          runId: '',
          filename: 'preview.pdf',
          type: 'pdf',
          versionPreviewPdf: { documentId: document.id, versionId: relevant.id },
        })
      } else {
        await openPdf(document)
      }
    } catch {
      await openPdf(document)
    }
  }

  const openArtifact = async (
    document: Document,
    artifactType: 'json' | 'markdown' | 'pdf',
    artifactPath?: string
  ) => {
    try {
      const runs = await getDocumentRuns(document.id)
      if (runs.length === 0) {
        alert('No hay versiones generadas para este documento')
        return
      }

      const run = runs[0]
      let filename = ''
      let artifactUrl = ''

      switch (artifactType) {
        case 'pdf':
          artifactUrl = run.artifacts.pdf || ''
          break
        case 'markdown':
          artifactUrl = run.artifacts.md || ''
          break
        case 'json':
          artifactUrl = run.artifacts.json || ''
          break
      }

      if (!artifactUrl && !artifactPath) {
        alert(`No hay ${artifactType.toUpperCase()} disponible para este documento`)
        return
      }

      filename = artifactPath 
        ? artifactPath.split('/').pop() || `process.${artifactType === 'json' ? 'json' : artifactType === 'markdown' ? 'md' : 'pdf'}`
        : artifactUrl.split('/').pop() || `process.${artifactType === 'json' ? 'json' : artifactType === 'markdown' ? 'md' : 'pdf'}`

      setViewerModal({
        isOpen: true,
        runId: run.run_id,
        filename,
        type: artifactType,
        versionPreviewPdf: null,
      })
    } catch (err) {
      alert('Error al cargar el artifact: ' + (err instanceof Error ? err.message : 'Error desconocido'))
    }
  }

  const closeModal = () => {
    setViewerModal((prev) => ({ ...prev, isOpen: false }))
  }

  /**
   * Abre un artifact directamente desde un run conocido.
   * Útil cuando ya tienes el runId y filename.
   */
  const openArtifactFromRun = (
    runId: string,
    filename: string,
    type: 'json' | 'markdown' | 'pdf'
  ) => {
    setViewerModal({
      isOpen: true,
      runId,
      filename,
      type,
      versionPreviewPdf: null,
    })
  }

  /** Abre el PDF de la versión actual (borrador con edición manual) en el mismo modal. */
  const openVersionPreviewPdf = (documentId: string, versionId: string) => {
    setViewerModal({
      isOpen: true,
      runId: '',
      filename: 'preview.pdf',
      type: 'pdf',
      versionPreviewPdf: { documentId, versionId },
    })
  }

  const ModalComponent = () => {
    return (
      <ArtifactViewerModal
        isOpen={viewerModal.isOpen}
        onClose={closeModal}
        runId={viewerModal.runId}
        filename={viewerModal.filename}
        type={viewerModal.type}
        versionPreviewPdf={viewerModal.versionPreviewPdf}
      />
    )
  }

  return { 
    openPdf,
    openLatestPdf,
    openArtifact,
    openArtifactFromRun,
    openVersionPreviewPdf,
    closeModal,
    ModalComponent 
  }
}

