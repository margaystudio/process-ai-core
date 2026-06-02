'use client'

import { useState } from 'react'
import { Document, getDocumentRuns, getDocumentVersions } from '@/lib/api'
import ArtifactViewerModal from '@/components/processes/ArtifactViewerModal'

interface ViewerModalState {
  isOpen: boolean
  /** URL ya firmada del artifact (viene del backend). */
  artifactUrl: string
  type: 'json' | 'markdown' | 'pdf'
  versionPreviewPdf: { documentId: string; versionId: string } | null
}

interface UsePdfViewerReturn {
  openPdf: (document: Document) => Promise<void>
  /** Abre el PDF más actualizado del documento: usa preview-pdf si hay versión IN_REVIEW o DRAFT con edición manual, si no usa el artifact original. */
  openLatestPdf: (document: Document) => Promise<void>
  openArtifact: (document: Document, artifactType: 'json' | 'markdown' | 'pdf', artifactPath?: string) => Promise<void>
  /** Abre un artifact directamente desde una URL ya firmada que viene del backend. */
  openArtifactFromRun: (artifactUrl: string, type: 'json' | 'markdown' | 'pdf') => void
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
    artifactUrl: '',
    type: 'pdf',
    versionPreviewPdf: null,
  })

  const openPdf = async (document: Document) => {
    try {
      const runs = await getDocumentRuns(document.id)
      if (runs.length > 0 && runs[0].artifacts.pdf) {
        setViewerModal({
          isOpen: true,
          artifactUrl: runs[0].artifacts.pdf,
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
   * - Si hay DRAFT con edición manual → usa preview-pdf (tiene el contenido editado)
   * - Si no, IN_REVIEW/APPROVED → usa preview-pdf de esa versión
   * - Si no hay versiones → fallback al process.pdf del run original
   */
  const openLatestPdf = async (document: Document) => {
    try {
      const versions = await getDocumentVersions(document.id)
      // Prioridad: DRAFT manual_edit > IN_REVIEW > APPROVED.
      const relevant =
        versions.find((v) => v.version_status === 'DRAFT' && v.content_type === 'manual_edit') ||
        versions.find((v) => v.version_status === 'IN_REVIEW') ||
        versions.find((v) => v.version_status === 'APPROVED') ||
        versions.find((v) => v.version_status === 'DRAFT')
      if (relevant) {
        setViewerModal({
          isOpen: true,
          artifactUrl: '',
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
      let signedUrl = ''

      switch (artifactType) {
        case 'pdf':
          signedUrl = run.artifacts.pdf || ''
          break
        case 'markdown':
          signedUrl = run.artifacts.md || ''
          break
        case 'json':
          signedUrl = run.artifacts.json || ''
          break
      }

      // artifactPath es un fallback legacy; la URL firmada del backend tiene prioridad.
      const resolvedUrl = signedUrl || artifactPath || ''

      if (!resolvedUrl) {
        alert(`No hay ${artifactType.toUpperCase()} disponible para este documento`)
        return
      }

      setViewerModal({
        isOpen: true,
        artifactUrl: resolvedUrl,
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
   * Abre un artifact directamente desde su URL firmada (viene del backend).
   */
  const openArtifactFromRun = (
    artifactUrl: string,
    type: 'json' | 'markdown' | 'pdf'
  ) => {
    setViewerModal({
      isOpen: true,
      artifactUrl,
      type,
      versionPreviewPdf: null,
    })
  }

  /** Abre el PDF de la versión actual (borrador con edición manual) en el mismo modal. */
  const openVersionPreviewPdf = (documentId: string, versionId: string) => {
    setViewerModal({
      isOpen: true,
      artifactUrl: '',
      type: 'pdf',
      versionPreviewPdf: { documentId, versionId },
    })
  }

  const ModalComponent = () => {
    return (
      <ArtifactViewerModal
        isOpen={viewerModal.isOpen}
        onClose={closeModal}
        artifactUrl={viewerModal.artifactUrl}
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

