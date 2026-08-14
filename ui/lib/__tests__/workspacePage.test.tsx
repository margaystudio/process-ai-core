/**
 * Menú contextual (⋮) de la Biblioteca — antes tenía botones muertos
 * ("a.action?.()" sin action). Estos tests cubren que:
 *  - Eliminar llama al endpoint real y refresca la lista.
 *  - El menú gatea por permiso efectivo: sin documents.delete no aparece
 *    "Eliminar" (nunca mostramos algo que el backend va a rechazar con 403).
 *  - "Archivar" usa el status CRUDO del documento, no la etiqueta en español
 *    — un documento "rechazado" se muestra como "Borrador" pero el backend
 *    solo permite la transición manual archived ↔ draft.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspacePage from '@/app/workspace/page'
import {
  deleteDocument,
  getDocumentTypes,
  getMyCapabilities,
  listDocuments,
  updateDocument,
  type Document,
  type MyCapabilities,
} from '@/lib/api'

const pushMock = vi.fn()
const replaceMock = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}))

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    selectedWorkspaceId: 'workspace-1',
    selectedWorkspace: { id: 'workspace-1' },
    activeTenantId: 'tenant-1',
  }),
}))

vi.mock('@/hooks/useWorkspaceProfileIncomplete', () => ({
  useWorkspaceProfileIncomplete: () => ({ incomplete: false, loading: false }),
}))

vi.mock('@/hooks/usePdfViewer', () => ({
  usePdfViewer: () => ({
    modalProps: { open: false, onClose: vi.fn() },
    openArtifactFromRun: vi.fn(),
    openVersionPreviewPdf: vi.fn(),
  }),
}))

vi.mock('@/components/processes/ArtifactViewerModal', () => ({
  default: () => null,
}))

vi.mock('@/components/biblioteca/BibliotecaFolderTree', () => ({
  default: () => null,
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return {
    ...actual,
    getMyCapabilities: vi.fn(),
    listDocuments: vi.fn(),
    getDocumentTypes: vi.fn(),
    deleteDocument: vi.fn(),
    updateDocument: vi.fn(),
  }
})

function capabilities(permissions: string[]): MyCapabilities {
  return {
    user_id: 'user-1',
    workspace_id: 'workspace-1',
    tenant_id: 'tenant-1',
    platform_roles: [],
    tenant_roles: [],
    role: 'member',
    is_superadmin: false,
    permissions,
    operational_role_ids: [],
    can_manage_workspace: false,
    can_manage_branding: false,
    folders: {},
  }
}

const draftDoc: Document = {
  id: 'doc-1',
  workspace_id: 'workspace-1',
  domain: 'process',
  document_type: 'procedimiento',
  name: 'Manual operativo',
  description: '',
  status: 'draft',
  version_number: null,
  created_at: '2026-08-01T10:00:00Z',
}

const writeTextMock = vi.fn().mockResolvedValue(undefined)

describe('WorkspacePage — menú contextual de la Biblioteca', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    writeTextMock.mockClear()
    vi.mocked(listDocuments).mockResolvedValue([draftDoc])
    vi.mocked(getDocumentTypes).mockResolvedValue([])
  })

  it('Eliminar llama al endpoint y refresca la lista', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(
      capabilities(['documents.edit', 'documents.delete'])
    )
    vi.mocked(deleteDocument).mockResolvedValue({ message: 'ok', deleted_runs: 0 })

    const user = userEvent.setup()
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Eliminar' }))

    const dialog = await screen.findByRole('dialog', { name: 'Eliminar documento' })
    expect(listDocuments).toHaveBeenCalledTimes(1)
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar' }))

    await waitFor(() => expect(deleteDocument).toHaveBeenCalledWith('doc-1'))
    await waitFor(() => expect(listDocuments).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('muestra el error de Eliminar dentro del diálogo sin perder la confirmación', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(
      capabilities(['documents.edit', 'documents.delete'])
    )
    vi.mocked(deleteDocument).mockRejectedValue(new Error('No autorizado'))

    const user = userEvent.setup()
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Eliminar' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar documento' })
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar' }))

    expect(await within(dialog).findByText('No autorizado')).toBeInTheDocument()
    // La lista NO se recarga si la eliminación falló.
    expect(listDocuments).toHaveBeenCalledTimes(1)
  })

  it('el menú no muestra "Eliminar" sin el permiso documents.delete, ni acciones sin implementar', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities(['documents.edit']))

    const user = userEvent.setup()
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await screen.findByRole('menuitem', { name: 'Abrir documento' })

    expect(screen.queryByRole('menuitem', { name: 'Eliminar' })).not.toBeInTheDocument()
    // "Mover" y "Crear nueva versión" no tienen UI implementada — se sacaron
    // del menú en vez de dejarlas muertas.
    expect(screen.queryByRole('menuitem', { name: 'Mover' })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Crear nueva versión' })).not.toBeInTheDocument()
  })

  it('no ofrece "Archivar" en un documento rechazado aunque se muestre como Borrador', async () => {
    // status crudo "rejected" se etiquetea como "Borrador" (ESTADO_LABEL), pero
    // el backend solo permite la transición manual archived ↔ draft: mostrar
    // "Archivar" acá hubiera disparado un 400.
    vi.mocked(getMyCapabilities).mockResolvedValue(
      capabilities(['documents.edit', 'documents.delete'])
    )
    vi.mocked(listDocuments).mockResolvedValue([{ ...draftDoc, status: 'rejected' }])

    const user = userEvent.setup()
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await screen.findByRole('menuitem', { name: 'Abrir documento' })

    expect(screen.queryByRole('menuitem', { name: 'Archivar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Desarchivar' })).not.toBeInTheDocument()
    // Eliminar sí se sigue ofreciendo: esa regla usa la etiqueta y no cambió.
    expect(screen.getByRole('menuitem', { name: 'Eliminar' })).toBeInTheDocument()
  })

  it('Archivar llama a updateDocument con status "archived" para un borrador', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities(['documents.edit']))
    vi.mocked(updateDocument).mockResolvedValue({ ...draftDoc, status: 'archived' })

    const user = userEvent.setup()
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Archivar' }))

    await waitFor(() =>
      expect(updateDocument).toHaveBeenCalledWith('doc-1', { status: 'archived' })
    )
    expect(await screen.findByText('Documento archivado.')).toBeInTheDocument()
    await waitFor(() => expect(listDocuments).toHaveBeenCalledTimes(2))
  })

  it('Copiar enlace copia la URL del documento y muestra confirmación', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities(['documents.edit']))

    const user = userEvent.setup()
    // `userEvent.setup()` instala su propio stub de navigator.clipboard (con un
    // getter propio) — hay que pisarlo DESPUÉS de setup(), si no gana el suyo.
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      configurable: true,
    })
    render(<WorkspacePage />)

    await user.click(await screen.findByRole('button', { name: 'Más opciones' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Copiar enlace' }))

    await waitFor(() =>
      expect(writeTextMock).toHaveBeenCalledWith(`${window.location.origin}/documents/doc-1`)
    )
    expect(await screen.findByText('Enlace copiado al portapapeles.')).toBeInTheDocument()
  })
})
