/**
 * La edición de permisos de carpeta vivía duplicada: un modal en
 * Configuración del workspace y la pestaña Permisos de /folders. Se dejó
 * solo la de /folders, así que la salida desde Configuración necesita un
 * deep-link (?folder=&tab=permisos) que abra directo esa carpeta y esa
 * pestaña — si no, el usuario queda en un callejón sin salida.
 *
 * Mismo patrón que /documents/[id] (?historial=1): se lee `window.location`
 * una sola vez tras la carga, sin useSearchParams.
 */
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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

// "Clientes" ordena primero (sort_order 0): si el deep-link no funcionara, la
// selección por defecto caería acá y no en "Liquidaciones".
const clientes: Folder = {
  id: 'folder-clientes',
  workspace_id: 'workspace-1',
  name: 'Clientes',
  path: 'Clientes',
  sort_order: 0,
  created_at: '2026-07-20T00:00:00Z',
}

const liquidaciones: Folder = {
  id: 'folder-liquidaciones',
  workspace_id: 'workspace-1',
  name: 'Liquidaciones',
  path: 'Liquidaciones',
  sort_order: 1,
  created_at: '2026-07-20T00:00:00Z',
}

describe('app/folders/page.tsx — deep-link ?folder=&tab= desde Configuración', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listFolders).mockResolvedValue([clientes, liquidaciones])
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
    vi.mocked(listOperationalRoles).mockResolvedValue([])
    vi.mocked(getFolderPermissions).mockResolvedValue({
      folder_id: liquidaciones.id,
      inherits_permissions: true,
      operational_role_ids: [],
      operational_roles: [],
      origin: 'base',
      from: null,
    })
  })

  afterEach(() => {
    // No filtrar la URL simulada a otros tests del mismo archivo/worker.
    window.history.pushState({}, '', '/folders')
  })

  it('abre directo la carpeta y la pestaña Permisos indicadas por querystring', async () => {
    window.history.pushState({}, '', '/folders?folder=folder-liquidaciones&tab=permisos')

    render(<FoldersPage />)

    expect(await screen.findByRole('heading', { level: 1, name: 'Liquidaciones' })).toBeInTheDocument()
    const permisosTab = await screen.findByRole('tab', { name: 'Permisos' })
    expect(permisosTab).toHaveAttribute('aria-selected', 'true')
  })

  it('si el querystring no trae folder/tab, se comporta como siempre (Resumen de la primera carpeta)', async () => {
    render(<FoldersPage />)

    expect(await screen.findByRole('heading', { level: 1, name: 'Clientes' })).toBeInTheDocument()
    const resumenTab = await screen.findByRole('tab', { name: 'Resumen' })
    expect(resumenTab).toHaveAttribute('aria-selected', 'true')
  })
})
