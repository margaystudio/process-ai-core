/**
 * Los permisos de carpeta se consolidaron en /folders (pestaña Permisos, con
 * el árbol al lado que explica la herencia). Este tab de Configuración del
 * workspace ya no abre un modal propio: solo muestra el estado
 * (restringida/abierta) y enlaza directo a esa pestaña.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import FoldersSettingsTab from '@/components/workspace/FoldersSettingsTab'
import { type Folder } from '@/lib/api'

vi.mock('@/hooks/useFolderCrud', () => ({
  useFolderCrud: () => ({
    saving: false,
    error: null,
    createFolder: vi.fn(),
    updateFolder: vi.fn(),
    deleteFolder: vi.fn(),
  }),
}))

const restricted: Folder = {
  id: 'folder-1',
  workspace_id: 'workspace-1',
  name: 'Liquidaciones',
  path: 'RRHH/Liquidaciones',
  sort_order: 0,
  permissions_restricted: true,
  created_at: '2026-07-20T00:00:00Z',
}

const open: Folder = {
  id: 'folder-2',
  workspace_id: 'workspace-1',
  name: 'Clientes',
  path: 'Clientes',
  sort_order: 1,
  permissions_restricted: false,
  created_at: '2026-07-20T00:00:00Z',
}

describe('FoldersSettingsTab', () => {
  it('enlaza a la pestaña Permisos de /folders para cada carpeta, sin abrir un editor propio', () => {
    render(
      <FoldersSettingsTab
        workspaceId="workspace-1"
        folders={[restricted, open]}
        onFoldersChange={vi.fn()}
      />
    )

    const links = screen.getAllByRole('link', { name: 'Permisos' })
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/folders?folder=folder-1&tab=permisos')
    expect(links[1]).toHaveAttribute('href', '/folders?folder=folder-2&tab=permisos')

    // Indicadores de estado (los mismos que antes), sin editor embebido.
    expect(screen.getByText('Restringida')).toBeInTheDocument()
    expect(screen.getByText('Todos')).toBeInTheDocument()

    // El modal viejo ya no existe: nada de checkboxes ni "Heredar permisos".
    expect(screen.queryByText('Heredar permisos del padre')).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('muestra el estado vacío cuando el workspace no tiene carpetas', () => {
    render(<FoldersSettingsTab workspaceId="workspace-1" folders={[]} onFoldersChange={vi.fn()} />)

    expect(screen.getByText('No hay carpetas en este workspace.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Permisos' })).not.toBeInTheDocument()
  })
})
