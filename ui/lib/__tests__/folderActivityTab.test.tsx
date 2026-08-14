import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FoldersPage from '@/app/folders/page'
import {
  getDocumentTypes,
  getFolderActivity,
  getFolderGovernance,
  getFolderPermissions,
  getFolderStats,
  listDocuments,
  listFolders,
  listOperationalRoles,
  type Folder,
} from '@/lib/api'

vi.mock('@/lib/api', () => ({
  getDocumentTypes: vi.fn(),
  getFolderActivity: vi.fn(),
  getFolderGovernance: vi.fn(),
  getFolderPermissions: vi.fn(),
  getFolderStats: vi.fn(),
  getMyCapabilities: vi.fn().mockResolvedValue({ folders: {} }),
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
  name: 'Operaciones',
  path: 'Operaciones',
  sort_order: 0,
  created_at: '2026-07-28T10:00:00Z',
}

describe('ActivityTab', () => {
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
  })

  it('muestra actor, acción, documento y fecha', async () => {
    vi.mocked(getFolderActivity).mockResolvedValue({
      items: [
        {
          id: 'activity-1',
          action: 'version.approved',
          entity_type: 'version',
          entity_id: 'version-1',
          document: { id: 'document-1', name: 'Cierre de caja' },
          actor: { id: 'user-1', name: 'Ana Auditora' },
          created_at: '2026-07-28T12:30:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    })

    const user = userEvent.setup()
    render(<FoldersPage />)
    // La pestaña, no el nombre: el nombre ya está en el árbol lateral mientras
    // el panel de detalle todavía no se pintó (ver folderPermissionsTab.test.tsx).
    await user.click(await screen.findByRole('tab', { name: 'Actividad' }))

    expect(await screen.findByText('Ana Auditora')).toBeInTheDocument()
    expect(screen.getByText('aprobó una versión')).toBeInTheDocument()
    expect(screen.getByText('Cierre de caja')).toBeInTheDocument()
    expect(
      screen.getByText(
        (content, element) => element?.tagName === 'TIME' && content.includes('2026')
      )
    ).toBeInTheDocument()
  })

  it('muestra empty state real cuando no hay eventos', async () => {
    vi.mocked(getFolderActivity).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
    })

    const user = userEvent.setup()
    render(<FoldersPage />)
    // La pestaña, no el nombre: el nombre ya está en el árbol lateral mientras
    // el panel de detalle todavía no se pintó (ver folderPermissionsTab.test.tsx).
    await user.click(await screen.findByRole('tab', { name: 'Actividad' }))

    expect(await screen.findByText('Todavía no hay actividad')).toBeInTheDocument()
  })
})
