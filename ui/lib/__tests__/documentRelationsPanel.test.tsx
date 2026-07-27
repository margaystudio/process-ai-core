import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getDocumentRelations: vi.fn(),
  getDocumentImpact: vi.fn(),
  suggestDocumentRelations: vi.fn(),
  confirmRelation: vi.fn(),
  rejectRelation: vi.fn(),
  editRelation: vi.fn(),
  searchKnowledgeObjects: vi.fn(),
  createKnowledgeObject: vi.fn(),
  mergeKnowledgeObject: vi.fn(),
}))

vi.mock('@/lib/api', () => apiMocks)

import { DocumentRelationsPanel } from '@/components/documents/DocumentRelationsPanel'

const relationsResponse = {
  document_id: 'doc-1',
  groups: [
    {
      relation_type: 'usa',
      items: [
        {
          id: 'rel-high',
          target: { id: 'ko-sap', type: 'sistema', name: 'SAP' },
          confidence: 0.91,
          status: 'candidate',
          evidence_text: 'Registrar la operación en SAP.',
          created_by_ai: true,
          confirmed_by: null,
          confirmed_at: null,
          possible_duplicate_of: {
            id: 'ko-sap-erp',
            type: 'sistema',
            name: 'SAP ERP',
          },
        },
      ],
    },
    {
      relation_type: 'genera',
      items: [
        {
          id: 'rel-low',
          target: { id: 'ko-form', type: 'formulario', name: 'Solicitud de compra' },
          confidence: 0.64,
          status: 'candidate',
          evidence_text: null,
          created_by_ai: true,
          confirmed_by: null,
          confirmed_at: null,
        },
      ],
    },
  ],
}

const impactResponse = {
  document_id: 'doc-1',
  affected_documents: [
    { id: 'doc-2', name: 'Alta de proveedor', status: 'approved', document_type: 'proceso' },
  ],
  affected_entities: [{ id: 'ko-1', type: 'sistema', name: 'ERP central' }],
}

describe('DocumentRelationsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMocks.getDocumentRelations.mockResolvedValue(relationsResponse)
    apiMocks.getDocumentImpact.mockResolvedValue(impactResponse)
    apiMocks.suggestDocumentRelations.mockResolvedValue({})
    apiMocks.confirmRelation.mockResolvedValue({})
    apiMocks.rejectRelation.mockResolvedValue({})
    apiMocks.editRelation.mockResolvedValue({})
    apiMocks.createKnowledgeObject.mockResolvedValue({})
    apiMocks.mergeKnowledgeObject.mockResolvedValue({})
    apiMocks.searchKnowledgeObjects.mockResolvedValue([
      {
        id: 'ko-sap',
        type: 'sistema',
        canonical_name: 'SAP',
        normalized_name: 'sap',
        description: null,
        aliases: [],
      },
      {
        id: 'ko-sap-erp',
        type: 'sistema',
        canonical_name: 'SAP ERP',
        normalized_name: 'sap erp',
        description: null,
        aliases: [],
      },
    ])
  })

  it('groups candidates and renders confidence, duplicate/new tags and impact', async () => {
    render(<DocumentRelationsPanel documentId="doc-1" />)

    expect(await screen.findByText('SAP')).toBeInTheDocument()
    expect(screen.getAllByText('Usa').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Genera').length).toBeGreaterThan(0)
    expect(screen.getByText('91% confianza')).toBeInTheDocument()
    expect(screen.getByText('Posible duplicado')).toBeInTheDocument()
    expect(await screen.findByText('Este documento toca 2 nodos')).toBeInTheDocument()
    expect(screen.getByText('Alta de proveedor')).toBeInTheDocument()
    expect(screen.getByText('ERP central')).toBeInTheDocument()
  })

  it('confirms the correct candidate and removes it from the pending list', async () => {
    const user = userEvent.setup()
    render(<DocumentRelationsPanel documentId="doc-1" />)
    await screen.findByText('SAP')

    await user.click(screen.getAllByRole('button', { name: 'Confirmar' })[0])
    expect(apiMocks.confirmRelation).toHaveBeenCalledWith('rel-high')
    await waitFor(() => expect(screen.queryByText('SAP')).not.toBeInTheDocument())
    expect(screen.getByText('Solicitud de compra')).toBeInTheDocument()
  })

  it('rejects the correct candidate and removes it from the pending list', async () => {
    const user = userEvent.setup()
    render(<DocumentRelationsPanel documentId="doc-1" />)
    await screen.findByText('Solicitud de compra')

    await user.click(screen.getAllByRole('button', { name: 'Rechazar' })[1])
    expect(apiMocks.rejectRelation).toHaveBeenCalledWith('rel-low')
    await waitFor(() =>
      expect(screen.queryByText('Solicitud de compra')).not.toBeInTheDocument()
    )
    expect(screen.getByText('SAP')).toBeInTheDocument()
  })

  it('confirms in bulk only candidates at or above the confidence threshold', async () => {
    const user = userEvent.setup()
    render(<DocumentRelationsPanel documentId="doc-1" />)
    await screen.findByText('SAP')

    await user.click(screen.getByRole('button', { name: 'Confirmar todo (1)' }))
    await waitFor(() => expect(apiMocks.confirmRelation).toHaveBeenCalledTimes(1))
    expect(apiMocks.confirmRelation).toHaveBeenCalledWith('rel-high')
    expect(screen.queryByText('SAP')).not.toBeInTheDocument()
    expect(screen.getByText('Solicitud de compra')).toBeInTheDocument()
  })

  it('runs relation detection for the current document', async () => {
    const user = userEvent.setup()
    render(<DocumentRelationsPanel documentId="doc-1" />)
    await screen.findByText('SAP')

    await user.click(screen.getByRole('button', { name: 'Detectar relaciones' }))
    expect(apiMocks.suggestDocumentRelations).toHaveBeenCalledWith('doc-1')
  })

  it('persists edit, merge and create actions through their dialogs', async () => {
    const user = userEvent.setup()
    render(<DocumentRelationsPanel documentId="doc-1" />)
    await screen.findByText('SAP')

    await user.click(screen.getByRole('button', { name: 'Editar relación con SAP' }))
    const editDialog = screen.getByRole('dialog', { name: 'Editar relación' })
    await user.selectOptions(within(editDialog).getByLabelText('Tipo de relación'), 'requiere')
    await user.selectOptions(within(editDialog).getByLabelText('Entidad destino'), 'ko-sap-erp')
    await user.click(within(editDialog).getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() =>
      expect(apiMocks.editRelation).toHaveBeenCalledWith('rel-high', {
        relation_type: 'requiere',
        target_type: 'sistema',
        target_id: 'ko-sap-erp',
      })
    )
    // Esperar a que el diálogo cierre (los reload() de runAction quedan pendientes
    // y un re-render a mitad del tipeo del paso siguiente deja referencias stale).
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Editar relación' })).not.toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: 'Unir' }))
    const mergeDialog = screen.getByRole('dialog', { name: 'Unir entidades duplicadas' })
    await user.click(within(mergeDialog).getByRole('button', { name: 'Unir entidades' }))
    expect(apiMocks.mergeKnowledgeObject).toHaveBeenCalledWith('ko-sap', {
      into_id: 'ko-sap-erp',
    })
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Unir entidades duplicadas' })
      ).not.toBeInTheDocument()
    )

    await user.click(screen.getByRole('button', { name: 'Crear entidad' }))
    const createDialog = screen.getByRole('dialog', { name: 'Crear entidad' })
    // El Dialog mueve el foco a su primer focusable vía requestAnimationFrame;
    // esperarlo antes de tipear, o roba el foco a mitad del type y el espacio
    // de "Nuevo sistema" activa el botón X (cierra el diálogo).
    await waitFor(() => expect(createDialog.contains(document.activeElement)).toBe(true))
    await user.type(within(createDialog).getByLabelText('Nombre'), 'Nuevo sistema')
    await user.type(within(createDialog).getByLabelText('Descripción opcional'), 'Descripción')
    await user.click(within(createDialog).getByRole('button', { name: 'Crear entidad' }))
    expect(apiMocks.createKnowledgeObject).toHaveBeenCalledWith({
      type: 'sistema',
      canonical_name: 'Nuevo sistema',
      description: 'Descripción',
    })
  })

  it('shows a real empty state when there are no candidates', async () => {
    apiMocks.getDocumentRelations.mockResolvedValueOnce({
      document_id: 'doc-1',
      groups: [],
    })

    render(<DocumentRelationsPanel documentId="doc-1" />)

    expect(await screen.findByText('No hay relaciones candidatas')).toBeInTheDocument()
    expect(screen.getByText(/Podés volver a analizar la versión aprobada/)).toBeInTheDocument()
  })
})
