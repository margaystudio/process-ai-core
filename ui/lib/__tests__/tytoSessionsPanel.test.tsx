import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TytoPage from '@/app/tyto/page'
import type { TytoSessionSummary } from '@/lib/api'

// Mismo aislamiento que lib/__tests__/tytoChat.test.tsx: no hace falta mockear
// WorkspaceContext ni auth de verdad, solo el armado de headers.
vi.mock('@/lib/api-auth', () => ({
  getAuthHeaders: vi.fn(async () => ({ 'Content-Type': 'application/json' })),
  getAccessToken: vi.fn(async () => null),
  getActiveTenantId: vi.fn(() => null),
  setActiveTenantId: vi.fn(),
  authFetch: vi.fn((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init)),
}))

function sseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeSession(overrides: Partial<TytoSessionSummary> = {}): TytoSessionSummary {
  return {
    id: 's1',
    title: 'Cierre de caja',
    pinned: false,
    created_at: '2026-08-01T10:00:00Z',
    updated_at: '2026-08-01T10:00:00Z',
    message_count: 2,
    ...overrides,
  }
}

/**
 * Router de `fetch` que simula el backend de sesiones de Tyto: lista con
 * filtro `q`, detalle, PATCH y DELETE — todo respaldado por un mapa mutable
 * en memoria para poder armar estados optimistas y sus reversiones.
 */
function createBackend(initialSessions: TytoSessionSummary[]) {
  const sessionsById = new Map(initialSessions.map((s) => [s.id, s]))
  const entriesById = new Map<string, unknown[]>()
  let failNextPatch = false
  let failNextDelete = false
  let streamResponseFactory: (() => Response) | null = null

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === 'string' ? input : input.toString())
    const method = (init?.method || 'GET').toUpperCase()
    const path = url.pathname

    if (path === '/api/v1/tyto/query/stream') {
      // El servidor ya habría creado/actualizado la sesión antes de emitir el
      // primer evento — el side effect sobre `sessionsById` se dispara desde
      // el test vía `streamResponseFactory` para simular eso.
      return streamResponseFactory ? streamResponseFactory() : sseResponse([])
    }

    if (path === '/api/v1/tyto/sessions') {
      if (method !== 'GET') return jsonResponse({ detail: 'method not allowed' }, 405)
      const q = url.searchParams.get('q')?.toLowerCase()
      let list = [...sessionsById.values()]
      if (q) list = list.filter((s) => (s.title ?? '').toLowerCase().includes(q))
      list.sort((a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      })
      return jsonResponse(list)
    }

    const detailMatch = path.match(/^\/api\/v1\/tyto\/sessions\/([^/]+)$/)
    if (detailMatch) {
      const id = detailMatch[1]
      if (method === 'GET') {
        const session = sessionsById.get(id)
        if (!session) return jsonResponse({ detail: 'not found' }, 404)
        return jsonResponse({ session, entries: entriesById.get(id) ?? [] })
      }
      if (method === 'PATCH') {
        // Demora artificial: sin esto, el mock resuelve tan rápido que la
        // reversión llega antes de que el test alcance a observar el frame
        // optimista — en un backend real esa ventana la da la latencia real.
        await new Promise((resolve) => setTimeout(resolve, 20))
        if (failNextPatch) {
          failNextPatch = false
          return jsonResponse({ detail: 'No se pudo guardar' }, 500)
        }
        const session = sessionsById.get(id)
        if (!session) return jsonResponse({ detail: 'not found' }, 404)
        const patch = JSON.parse(String(init?.body ?? '{}'))
        const updated = { ...session, ...patch }
        sessionsById.set(id, updated)
        return jsonResponse(updated)
      }
      if (method === 'DELETE') {
        await new Promise((resolve) => setTimeout(resolve, 20))
        if (failNextDelete) {
          failNextDelete = false
          return jsonResponse({ detail: 'No se pudo eliminar' }, 500)
        }
        sessionsById.delete(id)
        return jsonResponse({ deleted: id })
      }
    }

    return jsonResponse({ detail: 'not found' }, 404)
  })

  return {
    fetchMock,
    setEntries: (id: string, entries: unknown[]) => entriesById.set(id, entries),
    addSession: (session: TytoSessionSummary) => sessionsById.set(session.id, session),
    failNextPatch: () => {
      failNextPatch = true
    },
    failNextDelete: () => {
      failNextDelete = true
    },
    setStreamResponse: (factory: () => Response) => {
      streamResponseFactory = factory
    },
  }
}

describe('TytoPage — panel de conversaciones', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('lista las conversaciones con título, cantidad de mensajes y ancladas primero', async () => {
    const backend = createBackend([
      makeSession({ id: 'reciente', title: 'Reciente sin anclar', pinned: false, updated_at: '2026-08-10T00:00:00Z', message_count: 3 }),
      makeSession({ id: 'anclada', title: 'Conversación anclada', pinned: true, updated_at: '2026-08-01T00:00:00Z', message_count: 5 }),
    ])
    vi.stubGlobal('fetch', backend.fetchMock)

    render(<TytoPage />)

    const rows = await screen.findAllByRole('button', { name: /mensajes/ })
    expect(rows).toHaveLength(2)
    // Ancladas primero, sin importar la fecha.
    expect(rows[0]).toHaveTextContent('Conversación anclada')
    expect(rows[0]).toHaveTextContent('5 mensajes')
    expect(rows[1]).toHaveTextContent('Reciente sin anclar')
  })

  it('estado vacío de primer uso: invita a preguntar, no dice "no hay datos"', async () => {
    const backend = createBackend([])
    vi.stubGlobal('fetch', backend.fetchMock)

    render(<TytoPage />)

    expect(
      await screen.findByText(/Preguntale algo a Tyto y tus conversaciones van a aparecer acá/)
    ).toBeInTheDocument()
    expect(screen.queryByText(/no hay datos/i)).not.toBeInTheDocument()
  })

  it('error de carga con reintento', async () => {
    const backend = createBackend([makeSession()])
    let shouldFail = true
    const originalMock = backend.fetchMock.getMockImplementation()!
    backend.fetchMock.mockImplementation(async (input, init) => {
      const url = new URL(typeof input === 'string' ? input : (input as URL).toString())
      if (shouldFail && url.pathname === '/api/v1/tyto/sessions' && (init?.method ?? 'GET') === 'GET') {
        shouldFail = false
        return jsonResponse({ detail: 'Error de red' }, 500)
      }
      return originalMock(input, init)
    })
    vi.stubGlobal('fetch', backend.fetchMock)

    const user = userEvent.setup()
    render(<TytoPage />)

    expect(await screen.findByText('Error de red')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByRole('button', { name: /mensajes/ })).toHaveTextContent('Cierre de caja')
  })

  it('busca con debounce: no dispara una consulta por cada tecla', async () => {
    const backend = createBackend([
      makeSession({ id: 's1', title: 'Cierre de caja' }),
      makeSession({ id: 's2', title: 'Arqueo de mercadería' }),
    ])
    vi.stubGlobal('fetch', backend.fetchMock)

    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findAllByRole('button', { name: /mensajes/ })
    const callsBeforeSearch = backend.fetchMock.mock.calls.length

    await user.type(screen.getByPlaceholderText('Buscar conversaciones…'), 'caja')

    // Mientras se tipea no debería haber una consulta por cada letra.
    expect(backend.fetchMock.mock.calls.length).toBeLessThan(callsBeforeSearch + 4)

    await waitFor(
      () => {
        const lastCall = backend.fetchMock.mock.calls.at(-1)!
        const url = new URL(String(lastCall[0]))
        expect(url.searchParams.get('q')).toBe('caja')
      },
      { timeout: 2000 }
    )

    await waitFor(() => {
      expect(screen.queryByText('Arqueo de mercadería')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Cierre de caja')).toBeInTheDocument()

    // Limpiar la búsqueda vuelve a traer la lista completa.
    await user.click(screen.getByRole('button', { name: 'Limpiar búsqueda' }))
    await waitFor(() => {
      expect(screen.getByText('Arqueo de mercadería')).toBeInTheDocument()
    })
  })

  it('retomar carga el hilo completo con sus fuentes y sigue la conversación', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'Cierre de caja' })])
    backend.setEntries('s1', [
      {
        id: 'e1',
        question: '¿Qué necesito para el cierre de caja?',
        answered: true,
        answer: 'Contá el efectivo con el supervisor [S1].',
        refusal_reason: null,
        sources: [
          {
            source_id: 'S1',
            document_id: 'doc-1',
            document_name: 'Cierre de caja',
            version: 4,
            approved_at: '2026-06-12T00:00:00Z',
            tier: 'aprobado',
          },
        ],
        created_at: '2026-08-01T10:00:00Z',
      },
    ])
    backend.setStreamResponse(() =>
      sseResponse([
        sseEvent('session', { session_id: 's1' }),
        sseEvent('token', { text: 'Y si hay faltante, avisá [S1].' }),
        sseEvent('result', {
          answered: true,
          answer: 'Y si hay faltante, avisá [S1].',
          segments: [],
          sources: [],
        }),
      ])
    )
    vi.stubGlobal('fetch', backend.fetchMock)

    const user = userEvent.setup()
    render(<TytoPage />)

    await user.click(await screen.findByRole('button', { name: /Cierre de caja.*mensajes/s }))

    expect(await screen.findByText('¿Qué necesito para el cierre de caja?')).toBeInTheDocument()
    expect(screen.getByText(/Contá el efectivo con el supervisor/)).toBeInTheDocument()
    const sourcesPanel = screen.getByRole('complementary', { name: 'Fuentes de la respuesta' })
    expect(within(sourcesPanel).getByText('Cierre de caja')).toBeInTheDocument()

    // La siguiente pregunta continúa la MISMA sesión retomada.
    await user.type(
      screen.getByPlaceholderText('Preguntá sobre cualquier procedimiento…'),
      '¿Y si hay faltante?'
    )
    await user.click(screen.getByRole('button', { name: 'Enviar pregunta' }))

    await waitFor(() => {
      const streamCall = backend.fetchMock.mock.calls.find(
        (c) => new URL(String(c[0])).pathname === '/api/v1/tyto/query/stream'
      )
      expect(streamCall).toBeDefined()
      expect(JSON.parse(String(streamCall![1]?.body)).session_id).toBe('s1')
    })
  })

  it('un rechazo guardado (answered: false) se ve con el mismo tratamiento que uno en vivo', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'Pregunta rara' })])
    backend.setEntries('s1', [
      {
        id: 'e1',
        question: '¿Cuándo juega Peñarol?',
        answered: false,
        answer: null,
        refusal_reason: 'No tengo documentación aprobada sobre ese tema.',
        sources: [],
        created_at: '2026-08-01T10:00:00Z',
      },
    ])
    vi.stubGlobal('fetch', backend.fetchMock)

    const user = userEvent.setup()
    render(<TytoPage />)
    await user.click(await screen.findByRole('button', { name: /Pregunta rara.*mensajes/s }))

    expect(
      await screen.findByText('No tengo documentación aprobada sobre ese tema.')
    ).toBeInTheDocument()
    // Como en el chat en vivo: un rechazo no es un error real.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('renombrar actualiza optimistamente y revierte si falla el guardado', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'Título viejo' })])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findByText('Título viejo')

    backend.failNextPatch()
    await user.click(screen.getByRole('button', { name: 'Renombrar conversación' }))
    const input = screen.getByLabelText('Título de la conversación')
    await user.clear(input)
    await user.type(input, 'Título nuevo')
    await user.keyboard('{Enter}')

    // Optimista: se ve el nuevo título de inmediato.
    expect(await screen.findByText('Título nuevo')).toBeInTheDocument()
    // El PATCH falló: revierte al título anterior y avisa.
    await waitFor(() => expect(screen.getByText('Título viejo')).toBeInTheDocument())
    expect(screen.getByText(/No se pudo/)).toBeInTheDocument()
  })

  it('anclar es optimista: la fila salta de sección antes de que responda el servidor', async () => {
    const backend = createBackend([
      makeSession({ id: 'a', title: 'A', pinned: false, updated_at: '2026-08-01T00:00:00Z' }),
      makeSession({ id: 'b', title: 'B', pinned: false, updated_at: '2026-08-05T00:00:00Z' }),
    ])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findAllByRole('button', { name: /mensajes/ })

    // "A" es más vieja que "B": sin anclar, va segunda.
    let rows = screen.getAllByRole('button', { name: /mensajes/ })
    expect(rows[1]).toHaveTextContent('A')

    const rowA = screen.getByText('A').closest('.group') as HTMLElement
    await user.click(within(rowA).getByRole('button', { name: 'Anclar conversación' }))

    // Ahora "A" pasa a estar anclada y salta al principio, ya antes de que el
    // PATCH optimista termine de resolver.
    rows = screen.getAllByRole('button', { name: /mensajes/ })
    expect(rows[0]).toHaveTextContent('A')
  })

  it('anclar revierte si el servidor rechaza el cambio', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'Cierre de caja', pinned: false })])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findByText('Cierre de caja')

    backend.failNextPatch()
    await user.click(screen.getByRole('button', { name: 'Anclar conversación' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Anclar conversación' })).toBeInTheDocument()
    })
    expect(screen.getByText(/No se pudo/)).toBeInTheDocument()
  })

  it('borrar pide confirmación y elimina la fila de forma optimista', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'A borrar' })])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findByText('A borrar')

    await user.click(screen.getByRole('button', { name: 'Eliminar conversación' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar conversación' })
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar' }))

    await waitFor(() => {
      expect(screen.queryByText('A borrar')).not.toBeInTheDocument()
    })
  })

  it('borrar revierte y avisa si falla', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'A borrar' })])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findByText('A borrar')

    backend.failNextDelete()
    await user.click(screen.getByRole('button', { name: 'Eliminar conversación' }))
    const dialog = await screen.findByRole('dialog', { name: 'Eliminar conversación' })
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar' }))

    await waitFor(() => {
      expect(screen.getByText(/No se pudo eliminar/)).toBeInTheDocument()
    })
    // La fila sigue ahí: se revirtió el borrado optimista.
    expect(screen.getByText('A borrar')).toBeInTheDocument()
  })

  it('una conversación nueva creada por el stream refresca la lista para que aparezca', async () => {
    const backend = createBackend([])
    backend.setStreamResponse(() => {
      // El servidor ya la creó antes de emitir el primer evento.
      backend.addSession(
        makeSession({ id: 'sess-nueva', title: 'Conversación nueva', message_count: 1 })
      )
      return sseResponse([
        sseEvent('session', { session_id: 'sess-nueva' }),
        sseEvent('token', { text: 'Respuesta [S1].' }),
        sseEvent('result', { answered: true, answer: 'Respuesta [S1].', segments: [], sources: [] }),
      ])
    })
    vi.stubGlobal('fetch', backend.fetchMock)

    const user = userEvent.setup()
    render(<TytoPage />)
    await screen.findByText(/Preguntale algo a Tyto/)

    await user.type(
      screen.getByPlaceholderText('Preguntá sobre cualquier procedimiento…'),
      '¿Cómo hago el cierre?'
    )
    await user.click(screen.getByRole('button', { name: 'Enviar pregunta' }))

    expect(await screen.findByText('Conversación nueva')).toBeInTheDocument()
  })

  it('el panel mobile abre como drawer y cierra con Escape', async () => {
    const backend = createBackend([makeSession({ id: 's1', title: 'Cierre de caja' })])
    vi.stubGlobal('fetch', backend.fetchMock)
    const user = userEvent.setup()
    render(<TytoPage />)

    await user.click(screen.getByRole('button', { name: /Mis conversaciones/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Mis conversaciones' })
    expect(within(dialog).getByText('Cierre de caja')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Mis conversaciones' })).not.toBeInTheDocument()
    })
  })
})
