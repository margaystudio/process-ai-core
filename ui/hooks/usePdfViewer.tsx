'use client'

import { useState } from 'react'
import { Document, getDocumentRuns } from '@/lib/api'
import ArtifactViewerModal from '@/components/processes/ArtifactViewerModal'

interface ViewerModalState {
  isOpen: boolean
  runId: string
  filename: string
  type: 'json' | 'markdown' | 'pdf'
}

interface UsePdfViewerReturn {
  openPdf: (document: Document) => Promise<void>
  openArtifact: (document: Document, artifactType: 'json' | 'markdown' | 'pdf', artifactPath?: string) => Promise<void>
  openArtifactFromRun: (runId: string, filename: string, type: 'json' | 'markdown' | 'pdf') => void
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
        })
      } else {
        alert('No hay PDF disponible para este documento')
      }
    } catch (err) {
      alert('Error al cargar el PDF: ' + (err instanceof Error ? err.message : 'Error desconocido'))
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
      />
    )
  }

  return { 
    openPdf, 
    openArtifact,
    openArtifactFromRun,
    closeModal,
    ModalComponent 
  }
}

