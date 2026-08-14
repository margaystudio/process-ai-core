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
  getMyCapabilities: vi.fn().mockResolvedValue({
    can_manage_workspace: true,
    can_manage_branding: true,
    is_superadmin: false,
    permissions: [],
    folders: {},
  }),
  importDocuments: vi.fn(),
  listDocuments: vi.fn(),
  listFolders: vi.fn(),
  submitVersionForReview: vi.fn(),
}))

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    selectedWorkspace: { id: 'workspace-1', role: 'admin' },
    selectedWorkspaceId: 'workspace-1',
    activeTenantId: 'tenant-1',
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
        approved_by_name: '',
        rejected_at: null,
        rejected_by: null,
        rejected_by_name: '',
        is_current: false,
        created_by: 'user-1',
        created_by_name: 'Admin',
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
    expect(await screen.findByText('Importado no significa aprobado.')).toBeInTheDocument()
    expect(
      screen.getByText('Tyto no usará estos documentos hasta que sean aprobados.')
    ).toBeInTheDocument()
  })

  it('un item en error se puede reintentar sin duplicar los que ya entraron', async () => {
    vi.mocked(importDocuments)
      .mockRejectedValueOnce(new Error('Falló el servidor'))
      .mockResolvedValueOnce([importedDocument])

    const user = userEvent.setup()
    render(<ImportPage />)

    await user.selectOptions(await screen.findByLabelText('Carpeta destino'), 'folder-1')
    const file = new File(['contenido'], 'manual.txt', { type: 'text/plain' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, file)
    await user.click(screen.getByRole('button', { name: 'Importar 1' }))

    // Falló: queda trabado en 'error' con el botón de reintentar visible —
    // antes de este fix no había forma de recuperarlo sin refrescar la página.
    expect(await screen.findByText('Requiere atención')).toBeInTheDocument()
    expect(screen.getByText('Falló el servidor')).toBeInTheDocument()
    expect(importDocuments).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Importado · Borrador')).toBeInTheDocument()
    expect(importDocuments).toHaveBeenCalledTimes(2)
  })

  it('un documento ya importado nunca se reenvía al reintentar los que fallaron', async () => {
    const okFile = new File(['ok'], 'ok.txt', { type: 'text/plain' })
    const failFile = new File(['fail'], 'fail.txt', { type: 'text/plain' })

    vi.mocked(importDocuments)
      .mockResolvedValueOnce([importedDocument])
      .mockRejectedValueOnce(new Error('Falló el servidor'))
      .mockResolvedValueOnce([{ ...importedDocument, id: 'document-2', name: 'fail.txt' }])

    const user = userEvent.setup()
    render(<ImportPage />)

    await user.selectOptions(await screen.findByLabelText('Carpeta destino'), 'folder-1')
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, [okFile, failFile])
    await user.click(screen.getByRole('button', { name: 'Importar 2' }))

    await screen.findByText('Importado · Borrador')
    await screen.findByText('Requiere atención')
    expect(importDocuments).toHaveBeenCalledTimes(2)

    // El botón principal ahora ofrece reintentar SOLO lo que falló.
    const retryAllButton = await screen.findByRole('button', { name: 'Reintentar 1' })
    await user.click(retryAllButton)

    await waitFor(() => expect(importDocuments).toHaveBeenCalledTimes(3))

    // El tercer llamado (el reintento) tiene que llevar el archivo que había
    // fallado — nunca el que ya había entrado. Reenviar ese es justo lo que
    // causó el duplicado del bug original.
    const thirdCallFormData = vi.mocked(importDocuments).mock.calls[2][0] as FormData
    const resentFile = thirdCallFormData.get('files') as File
    expect(resentFile.name).toBe('fail.txt')

    // "ok.txt" no vuelve a viajar en ningún llamado posterior a su éxito.
    expect(importDocuments).toHaveBeenCalledTimes(3)
  })
})
