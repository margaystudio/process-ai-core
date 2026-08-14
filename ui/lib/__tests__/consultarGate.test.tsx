/**
 * Quién aterriza en /consultar: la cascada de redirect de app/page.tsx (no hay
 * gate propio en la pantalla — /consultar es tan abierta como /tyto, cualquier
 * staff autenticado del workspace puede entrar. Lo que se testea acá es a
 * dónde manda el "/" según capacidades, que es lo que hace que sea la
 * pantalla principal de quien solo lee documentación.
 */
import { render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Home from '@/app/page'
import { getMyCapabilities, type MyCapabilities } from '@/lib/api'

const pushMock = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return { ...actual, getMyCapabilities: vi.fn() }
})

vi.mock('@/contexts/WorkspaceContext', () => ({
  useWorkspace: () => ({
    workspaces: [{ id: 'ws-1' }],
    selectedWorkspaceId: 'ws-1',
    selectedWorkspace: { id: 'ws-1' },
    activeTenantId: 'tenant-1',
    currentUser: { id: 'user-1', email: 'pistero@example.com', name: 'Pistero' },
    loading: false,
  }),
}))

function capabilities(permissions: string[]): MyCapabilities {
  return {
    user_id: 'user-1',
    workspace_id: 'ws-1',
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

describe('app/page.tsx — cascada de redirect según capacidades', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sin documents.edit ni documents.approve (solo documents.view): manda a /consultar, no a la Biblioteca', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities(['documents.view']))

    render(<Home />)

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/consultar'))
    expect(pushMock).not.toHaveBeenCalledWith('/dashboard/view')
  })

  it('quien aprueba (documents.approve) sigue yendo a la cola de aprobación', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(
      capabilities(['documents.view', 'documents.edit', 'documents.approve'])
    )

    render(<Home />)

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/dashboard/approval-queue'))
    expect(pushMock).not.toHaveBeenCalledWith('/consultar')
  })

  it('quien edita (sin aprobar) sigue yendo a la Biblioteca, no a /consultar', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities(['documents.view', 'documents.edit']))

    render(<Home />)

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/workspace'))
    expect(pushMock).not.toHaveBeenCalledWith('/consultar')
  })

  it('sin ningún permiso de documentos, cae al fallback existente (no a /consultar)', async () => {
    vi.mocked(getMyCapabilities).mockResolvedValue(capabilities([]))

    render(<Home />)

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/workspace'))
    expect(pushMock).not.toHaveBeenCalledWith('/consultar')
  })
})
