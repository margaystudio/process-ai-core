import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ImportPage from '@/app/import/page'
import {
  approveDocumentValidation,
  getDocumentVersions,
  importDocuments,
  listDocuments,
  listFolders,
  submitVersionForReview,
  type Document,
} from '@/lib/api'

vi.mock('@/lib/api', () => ({
  approveDocumentValidation: vi.fn(),
  getDocumentVersions: vi.fn(),
  importDocuments: vi.fn(),
  listDocuments: vi.fn(),
  listFolders: vi.fn(),
  submitVersionForReview: vi.fn(),
}))

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    selectedWorkspace: { id: 'workspace-1', role: 'admin' },
    selectedWorkspaceId: 'workspace-1',
    platformRoles: [],
    currentUser: { id: 'user-1', email: 'admin@example.com', name: 'Admin' },
  }),
}))

const importedDocument: Document = {
  id: 'document-1',
  workspace_id: 'workspace-1',
  folder_id: 'folder-1',
  domain: 'process',
  document_type: 'procedimiento',
  name: 'Manual operativo',
  description: 'Archivo importado: manual.txt',
  status: 'draft',
  created_at: '2026-07-28T10:00:00Z',
}

describe('ImportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listFolders).mockResolvedValue([
      {
        id: 'folder-1',
        workspace_id: 'workspace-1',
        name: 'Operaciones',
        path: 'Operaciones',
        sort_order: 0,
        created_at: '2026-07-28T10:00:00Z',
      },
    ])
    vi.mocked(listDocuments).mockResolvedValue([])
    vi.mocked(importDocuments).mockResolvedValue([importedDocument])
    vi.mocked(getDocumentVersions).mockResolvedValue([
      {
        id: 'version-1',
        version_number: 1,
        version_status: 'DRAFT',
        content_type: 'imported',
        run_id: null,
        approved_at: null,
        approved_by: null,
        created_at: '2026-07-28T10:00:00Z',
      },
    ])
    vi.mocked(submitVersionForReview).mockResolvedValue({
      message: 'Versión enviada',
      version: {
        id: 'version-1',
        version_number: 1,
        version_status: 'IN_REVIEW',
        validation_id: 'validation-1',
      },
      validation: {
        id: 'validation-1',
        status: 'pending',
        document_id: importedDocument.id,
        created_at: '2026-07-28T10:05:00Z',
        assigned_approver_ids: [],
        submit_comment: 'Importación por lote',
      },
    })
    vi.mocked(approveDocumentValidation).mockResolvedValue({
      version_id: 'version-1',
      version_status: 'APPROVED',
      validation_id: 'validation-1',
      document_status: 'approved',
    })
  })

  it('importa archivos y los envía a aprobación por lote', async () => {
    const user = userEvent.setup()
    render(<ImportPage />)

    await user.selectOptions(await screen.findByLabelText('Carpeta destino'), 'folder-1')
    const file = new File(['contenido'], 'manual.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: 'Importar 1' }))

    expect(await screen.findByText('Importado · Borrador')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Enviar a aprobación (1)' }))

    await waitFor(() => {
      expect(submitVersionForReview).toHaveBeenCalledWith(
        importedDocument.id,
        'version-1',
        'user-1',
        'workspace-1',
        [],
        'Importación por lote'
      )
    })
    expect(await screen.findByText('Pendiente de aprobación')).toBeInTheDocument()
  })

  it('aprueba en lote importaciones pendientes de la carpeta', async () => {
    vi.mocked(listDocuments).mockResolvedValue([
      { ...importedDocument, status: 'pending_validation' },
    ])
    const user = userEvent.setup()
    render(<ImportPage />)

    await user.selectOptions(await screen.findByLabelText('Carpeta destino'), 'folder-1')
    const checkbox = await screen.findByRole('checkbox', {
      name: 'Seleccionar Manual operativo',
    })
    await user.click(checkbox)
    await user.click(screen.getByRole('button', { name: 'Aprobar seleccionados (1)' }))

    await waitFor(() => {
      // El último argumento es `deferFreeze`, y en el lote tiene que ir en true:
      // congelar el PDF dentro de cada request convierte un lote de 50 en varios
      // minutos sin cancelación. El artefacto lo produce después el barrido
      // (tools/freeze_pending_pdfs.py) o la primera apertura.
      expect(approveDocumentValidation).toHaveBeenCalledWith(
        importedDocument.id,
        undefined,
        undefined,
        undefined,
        true
      )
    })
    expect(await screen.findByText('Aprobado')).toBeInTheDocument()
  })

  it('muestra los mensajes de gobernanza del prototipo', async () => {
    render(<ImportPage />)
    expect(screen.getByText('Importado no significa aprobado.')).toBeInTheDocument()
    expect(
      screen.getByText('Tyto no usará estos documentos hasta que sean aprobados.')
    ).toBeInTheDocument()
  })
})
