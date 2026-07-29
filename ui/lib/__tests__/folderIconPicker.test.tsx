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
  type Folder,
} from '@/lib/api'

const { updateFolderMock } = vi.hoisted(() => ({
  updateFolderMock: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  getDocumentTypes: vi.fn(),
  getFolderActivity: vi.fn(),
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
    updateFolder: updateFolderMock,
    reparentFolder: vi.fn(),
  }),
}))

const folder: Folder = {
  id: 'folder-1',
  workspace_id: 'workspace-1',
  name: 'Operaciones',
  path: 'Operaciones',
  sort_order: 0,
  icon: 'folder',
  color: '#48569C',
  metadata: { description: 'Documentación operativa' },
  created_at: '2026-07-28T10:00:00Z',
}

describe('FolderIconPicker', () => {
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
    vi.mocked(getFolderPermissions).mockResolvedValue({
      folder_id: folder.id,
      inherits_permissions: true,
      operational_role_ids: [],
      operational_roles: [],
      origin: 'heredado',
      from: null,
    })
    vi.mocked(getDocumentTypes).mockResolvedValue([])
    vi.mocked(listOperationalRoles).mockResolvedValue([])
    updateFolderMock.mockResolvedValue({ ...folder, icon: 'archive' })
  })

  it('muestra iconos en las opciones y persiste el seleccionado', async () => {
    const user = userEvent.setup()
    render(<FoldersPage />)
    const folderButton = await screen.findByRole('button', { name: 'Operaciones0' })
    await user.click(folderButton)
    await user.click(screen.getByRole('tab', { name: 'General' }))

    const picker = screen.getByRole('combobox', { name: 'Icono' })
    expect(picker.querySelector('svg')).not.toBeNull()
    await user.click(picker)

    const archiveOption = screen.getByRole('option', { name: 'Archivo' })
    expect(archiveOption.querySelector('svg')).not.toBeNull()
    await user.click(archiveOption)
    await user.click(screen.getByRole('button', { name: 'Guardar cambios' }))

    await waitFor(() => {
      expect(updateFolderMock).toHaveBeenCalledWith(folder.id, {
        name: folder.name,
        path: folder.path,
        color: folder.color,
        icon: 'archive',
        metadata: { description: 'Documentación operativa' },
      })
    })
  })
})
