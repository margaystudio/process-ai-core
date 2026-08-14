/**
 * Bug reportado: al crear una carpeta raíz ("Clientes") y abrir "Nueva
 * carpeta" para crearle una hija, la carpeta recién creada NO aparecía en el
 * select "Carpeta padre" hasta refrescar la página a mano — aunque sí
 * aparecía en el árbol del sidebar.
 *
 * Causa: `capabilities.folders` (de dónde sale `canCreateInFolder`, fail-closed
 * por diseño ante una carpeta desconocida) se pedía una sola vez al montar y
 * nunca se refrescaba tras crear/mover/borrar carpetas. Este test cubre que,
 * tras crear una carpeta, quede seleccionable como padre SIN recargar.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FoldersPage from '@/app/folders/page'
import {
  createFolder,
  getDocumentTypes,
  getFolderGovernance,
  getFolderStats,
  getMyCapabilities,
  listDocuments,
  listFolders,
  type Folder,
  type MyCapabilities,
} from '@/lib/api'

vi.mock('@/lib/api', () => ({
  createFolder: vi.fn(),
  getDocumentTypes: vi.fn(),
  getFolderActivity: vi.fn(),
  getFolderGovernance: vi.fn(),
  getFolderPermissions: vi.fn(),
  getFolderStats: vi.fn(),
  getMyCapabilities: vi.fn(),
  listDocuments: vi.fn(),
  listFolders: vi.fn(),
  listOperationalRoles: vi.fn(),
  updateFolder: vi.fn(),
  updateFolderPermissions: vi.fn(),
}))

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    selectedWorkspaceId: 'workspace-1',
    selectedWorkspace: { id: 'workspace-1' },
    activeTenantId: 'tenant-1',
    currentUser: { id: 'user-1', email: 'admin@example.com', name: 'Admin' },
  }),
}))

function capabilities(folders: MyCapabilities['folders']): MyCapabilities {
  return {
    user_id: 'user-1',
    workspace_id: 'workspace-1',
    tenant_id: 'tenant-1',
    platform_roles: [],
    tenant_roles: [],
    role: 'admin',
    is_superadmin: false,
    permissions: ['documents.view', 'documents.edit'],
    operational_role_ids: [],
    can_manage_workspace: true,
    can_manage_branding: true,
    folders,
  }
}

const clientesFolder: Folder = {
  id: 'folder-clientes',
  workspace_id: 'workspace-1',
  name: 'Clientes',
  path: 'Clientes',
  sort_order: 0,
  created_at: '2026-08-12T10:00:00Z',
}

describe('app/folders/page.tsx — capabilities frescas tras crear una carpeta', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listDocuments).mockResolvedValue([])
    vi.mocked(getDocumentTypes).mockResolvedValue([])
    vi.mocked(getFolderStats).mockResolvedValue(undefined as never)
    vi.mocked(getFolderGovernance).mockResolvedValue(undefined as never)
    vi.mocked(createFolder).mockResolvedValue(clientesFolder)

    // Sin carpetas todavía → nada que ver en el árbol. Tras crear "Clientes",
    // handleCreate hace `reload()`, que vuelve a pedir el listado.
    vi.mocked(listFolders)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([clientesFolder])

    // Antes de crear "Clientes" no existe en el mapa (no importa: todavía no
    // hay carpetas para elegir). Tras crearla, `refreshCapabilities()` pide
    // capabilities de nuevo y esta vez el backend ya la incluye con acceso.
    vi.mocked(getMyCapabilities)
      .mockResolvedValueOnce(capabilities({}))
      .mockResolvedValueOnce(
        capabilities({ 'folder-clientes': { view: true, create: true, approve: true } })
      )
  })

  it('la carpeta recién creada es seleccionable como padre sin recargar la página', async () => {
    const user = userEvent.setup()
    render(<FoldersPage />)

    await user.click(await screen.findByRole('button', { name: 'Nueva carpeta' }))
    const createDialog = await screen.findByRole('dialog', { name: 'Nueva carpeta' })
    await user.type(within(createDialog).getByLabelText('Nombre'), 'Clientes')
    await user.click(within(createDialog).getByRole('button', { name: 'Crear carpeta' }))

    // El diálogo se cierra apenas el backend confirma la creación.
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Nueva carpeta' })).not.toBeInTheDocument())
    expect(createFolder).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Clientes', parent_id: undefined })
    )

    // Sin el refresh, esto se quedaría esperando para siempre: capabilities
    // solo se pedía una vez al montar la pantalla.
    await waitFor(() => expect(getMyCapabilities).toHaveBeenCalledTimes(2))

    await user.click(await screen.findByRole('button', { name: 'Nueva carpeta' }))
    const secondDialog = await screen.findByRole('dialog', { name: 'Nueva carpeta' })
    const parentSelect = within(secondDialog).getByLabelText('Carpeta padre')

    await waitFor(() => {
      expect(within(parentSelect).getByRole('option', { name: 'Clientes' })).toBeInTheDocument()
    })
  })
})
