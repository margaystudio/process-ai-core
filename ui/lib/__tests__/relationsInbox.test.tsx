import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getWorkspaceRelations: vi.fn(),
  listFolders: vi.fn(),
  confirmRelation: vi.fn(),
  rejectRelation: vi.fn(),
  editRelation: vi.fn(),
  mergeKnowledgeObject: vi.fn(),
  searchKnowledgeObjects: vi.fn(),
}))

vi.mock('@/lib/api', () => apiMocks)
vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    selectedWorkspace: { id: 'workspace-1', role: 'admin' },
    platformRoles: [],
    loading: false,
  }),
}))
vi.mock('@/hooks/useHasPermission', () => ({
  useCanApproveDocuments: () => ({ hasPermission: true }),
  useCanRejectDocuments: () => ({ hasPermission: true }),
  useHasPermission: () => ({ hasPermission: true }),
}))

import RelationsInboxPage from '@/app/relations/page'

const inboxResponse = {
  items: [
    {
      id: 'relation-high',
      document: {
        id: 'doc-1',
        name: 'Cierre de caja',
        folder_id: 'folder-ops',
        folder_name: 'Operaciones',
      },
      relation_type: 'usa',
      target: { id: 'ko-1', type: 'sistema', name: 'SAP' },
      confidence: 0.94,
      status: 'candidate',
      evidence_text: 'Registrar el cierre en SAP.',
      created_by_ai: true,
      decided_by: null,
      decided_at: null,
      possible_duplicate_of: null,
    },
    {
      id: 'relation-low',
      document: {
        id: 'doc-2',
        name: 'Alta de proveedor',
        folder_id: 'folder-finance',
        folder_name: 'Finanzas',
      },
      relation_type: 'requiere',
      target: { id: 'ko-2', type: 'rol', name: 'Responsable de compras' },
      confidence: 0.68,
      status: 'candidate',
      evidence_text: null,
      created_by_ai: true,
      decided_by: null,
      decided_at: null,
      possible_duplicate_of: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 25,
  total_pages: 1,
}

describe('RelationsInboxPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getWorkspaceRelations.mockResolvedValue(inboxResponse)
    apiMocks.listFolders.mockResolvedValue([
      { id: 'folder-ops', name: 'Operaciones', path: 'Operaciones' },
      { id: 'folder-finance', name: 'Finanzas', path: 'Finanzas' },
    ])
    apiMocks.confirmRelation.mockResolvedValue({})
    apiMocks.rejectRelation.mockResolvedValue({})
    apiMocks.editRelation.mockResolvedValue({})
    apiMocks.mergeKnowledgeObject.mockResolvedValue({})
    apiMocks.searchKnowledgeObjects.mockResolvedValue([])
  })

  it('renders workspace candidates with source, type and descending confidence', async () => {
    render(<RelationsInboxPage />)

    expect(await screen.findByText('SAP')).toBeInTheDocument()
    expect(screen.getByText('Cierre de caja · Operaciones')).toBeInTheDocument()
    expect(screen.getByText('Responsable de compras')).toBeInTheDocument()
    expect(screen.getByText('94% confianza')).toBeInTheDocument()
    expect(screen.getByText('68% confianza')).toBeInTheDocument()
    expect(screen.getByText('Confianza: mayor a menor')).toBeInTheDocument()
  })

  it('sends relation type and folder filters to the workspace endpoint', async () => {
    const user = userEvent.setup()
    render(<RelationsInboxPage />)
    await screen.findByText('SAP')

    await user.selectOptions(screen.getByLabelText('Tipo de relación'), 'requiere')
    await user.selectOptions(screen.getByLabelText('Carpeta'), 'folder-finance')

    await waitFor(() =>
      expect(apiMocks.getWorkspaceRelations).toHaveBeenLastCalledWith({
        status: 'candidate',
        type: 'requiere',
        folder_id: 'folder-finance',
        page: 1,
        page_size: 25,
      })
    )
  })

  it('confirms selected candidates in bulk and removes them from the inbox', async () => {
    const user = userEvent.setup()
    render(<RelationsInboxPage />)
    await screen.findByText('SAP')

    await user.click(screen.getByLabelText('Seleccionar relación con SAP'))
    await user.click(
      screen.getByLabelText('Seleccionar relación con Responsable de compras')
    )
    await user.click(screen.getByRole('button', { name: 'Confirmar seleccionadas (2)' }))

    await waitFor(() => expect(apiMocks.confirmRelation).toHaveBeenCalledTimes(2))
    expect(apiMocks.confirmRelation).toHaveBeenCalledWith('relation-high')
    expect(apiMocks.confirmRelation).toHaveBeenCalledWith('relation-low')
    expect(screen.queryByText('SAP')).not.toBeInTheDocument()
    expect(screen.getByText('No hay relaciones pendientes')).toBeInTheDocument()
  })

  it('renders an empty state when the workspace has no pending candidates', async () => {
    apiMocks.getWorkspaceRelations.mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 25,
      total_pages: 0,
    })

    render(<RelationsInboxPage />)

    expect(await screen.findByText('No hay relaciones pendientes')).toBeInTheDocument()
  })
})
