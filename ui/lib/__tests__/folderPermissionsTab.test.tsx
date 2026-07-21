import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FoldersPage from '@/app/folders/page'
import {
  getDocumentTypes,
  getFolderGovernance,
  getFolderPermissions,
  getFolderStats,
  listDocuments,
  listFolders,
  listOperationalRoles,
  updateFolderPermissions,
  type Folder,
} from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getDocumentTypes: vi.fn(),
  getFolderGovernance: vi.fn(),
  getFolderPermissions: vi.fn(),
  getFolderStats: vi.fn(),
  listDocuments: vi.fn(),
  listFolders: vi.fn(),
  listOperationalRoles: vi.fn(),
  updateFolderPermissions: vi.fn(),
}))

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({ selectedWorkspaceId: 'workspace-1' }),
}))

vi.mock('@/hooks/useFolderCrud', () => ({
  useFolderCrud: () => ({
    saving: false,
    error: null,
    createFolder: vi.fn(),
    updateFolder: vi.fn(),
    reparentFolder: vi.fn(),
  }),
}))

const folder: Folder = {
  id: 'folder-1',
  workspace_id: 'workspace-1',
  name: 'Liquidaciones',
  path: 'RRHH/Liquidaciones',
  parent_id: 'folder-parent',
  sort_order: 0,
  created_at: '2026-07-20T00:00:00Z',
}

const roles = [
  {
    id: 'r1',
    workspace_id: 'workspace-1',
    name: 'Gerente',
    slug: 'gerente',
    description: 'Responsable del área',
    is_active: true,
    created_at: '2026-07-20T00:00:00Z',
    updated_at: '2026-07-20T00:00:00Z',
  },
  {
    id: 'r2',
    workspace_id: 'workspace-1',
    name: 'Encargado',
    slug: 'encargado',
    description: 'Supervisa la operación',
    is_active: true,
    created_at: '2026-07-20T00:00:00Z',
    updated_at: '2026-07-20T00:00:00Z',
  },
]

describe('PermissionsTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listFolders).mockResolvedValue([folder])
    vi.mocked(listDocuments).mockResolvedValue([])
    vi.mocked(getFolderStats).mockResolvedValue({
      documentos: 0,
      aprobados: 0,
      borradores: 0,
      pendientes: 0,
      archivados: 0,
      relaciones_nuevas: 0,
      confianza_prom: null,
    })
    vi.mocked(getFolderGovernance).mockResolvedValue({
      default_document_type: { value: null, origin: 'base', from: null },
      tyto_enabled: { value: null, origin: 'base', from: null },
      allow_document_override: { value: true, origin: 'personalizado' },
    })
    vi.mocked(getDocumentTypes).mockResolvedValue([])
    vi.mocked(listOperationalRoles).mockResolvedValue(roles)
    vi.mocked(updateFolderPermissions).mockResolvedValue({
      message: 'Permisos actualizados',
      folder_id: folder.id,
    })
  })

  async function renderPermissionsTab() {
    const user = userEvent.setup()
    render(<FoldersPage />)
    await screen.findAllByText('Liquidaciones')
    await user.click(screen.getByRole('tab', { name: 'Permisos' }))
    return user
  }

  it('muestra los roles heredados en lectura y el origen', async () => {
    vi.mocked(getFolderPermissions).mockResolvedValue({
      folder_id: folder.id,
      inherits_permissions: true,
      operational_role_ids: ['r1'],
      operational_roles: [{ id: 'r1', name: 'Gerente', slug: 'gerente' }],
      origin: 'heredado',
      from: 'RRHH',
    })

    await renderPermissionsTab()

    expect(await screen.findByText('Gerente')).toBeInTheDocument()
    expect(screen.getByText('Heredado de RRHH')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Acceso del rol Gerente' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Acceso del rol Gerente' })).toBeDisabled()
  })

  it('guarda la lista de roles marcada cuando no hereda', async () => {
    vi.mocked(getFolderPermissions).mockResolvedValue({
      folder_id: folder.id,
      inherits_permissions: false,
      operational_role_ids: [],
      operational_roles: [],
      origin: 'personalizado',
      from: null,
    })

    const user = await renderPermissionsTab()

    const roleCheckbox = await screen.findByRole('checkbox', { name: 'Acceso del rol Encargado' })
    expect(roleCheckbox).toBeEnabled()
    await user.click(roleCheckbox)
    await user.click(screen.getByRole('button', { name: 'Guardar permisos' }))

    await waitFor(() => {
      expect(updateFolderPermissions).toHaveBeenCalledWith(folder.id, {
        inherits_permissions: false,
        operational_role_ids: ['r2'],
      })
    })
  })
})
