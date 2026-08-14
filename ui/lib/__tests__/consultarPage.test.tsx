import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ConsultarPage from '@/app/consultar/page'

// Mismo aislamiento que lib/__tests__/tytoChat.test.tsx: el foco es el
// comportamiento de la pantalla, no el armado de headers de auth.
vi.mock('@/lib/api-auth', () => ({
  getAuthHeaders: vi.fn(async () => ({ 'Content-Type': 'application/json' })),
  getAccessToken: vi.fn(async () => null),
  getActiveTenantId: vi.fn(() => null),
  setActiveTenantId: vi.fn(),
  authFetch: vi.fn((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init)),
}))

const PLACEHOLDER = 'Escribí o grabá tu pregunta…'

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
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Router de `fetch`: sugerencias fijas + lo que el test defina para el stream. */
function withSuggestions(
  suggestions: Array<{ question: string; veces: number }>,
  streamResponder: () => Response | Promise<Response>
) {
  return (input: RequestInfo | URL) => {
    const url = new URL(typeof input === 'string' ? input : input.toString())
    if (url.pathname === '/api/v1/tyto/suggestions') return jsonResponse(suggestions)
    return streamResponder()
  }
}

async function askByTyping(user: ReturnType<typeof userEvent.setup>, question: string) {
  await user.type(screen.getByPlaceholderText(PLACEHOLDER), question)
  await user.click(screen.getByRole('button', { name: 'Enviar pregunta' }))
}

describe('ConsultarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sin conversación en curso, muestra las sugerencias como chips y preguntar por uno pregunta directo', async () => {
    const fetchMock = vi.fn(
      withSuggestions([{ question: '¿Cómo cierro la caja?', veces: 12 }], () =>
        sseResponse([
          sseEvent('result', {
            answered: true,
            answer: 'Contá el efectivo con el supervisor.',
            segments: [],
            sources: [],
          }),
        ])
      )
    )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ConsultarPage />)

    const chip = await screen.findByRole('button', { name: '¿Cómo cierro la caja?' })
    await user.click(chip)

    // La pregunta viaja tal cual el chip, sin pasar por el campo.
    expect(await screen.findByText('¿Cómo cierro la caja?')).toBeInTheDocument()
    expect(await screen.findByText('Contá el efectivo con el supervisor.')).toBeInTheDocument()
  })

  it('workspace nuevo (sin sugerencias): nunca un hueco en blanco, muestra la ayuda breve', async () => {
    const fetchMock = vi.fn(withSuggestions([], () => sseResponse([])))
    vi.stubGlobal('fetch', fetchMock)
    render(<ConsultarPage />)

    expect(await screen.findByText(/Preguntale cosas como/)).toBeInTheDocument()
  })

  it('si falla el pedido de sugerencias, cae a la misma ayuda breve (no un error)', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(typeof input === 'string' ? input : input.toString())
      if (url.pathname === '/api/v1/tyto/suggestions') return jsonResponse({ detail: 'boom' }, 500)
      return sseResponse([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<ConsultarPage />)

    expect(await screen.findByText(/Preguntale cosas como/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('una respuesta contestada ofrece "Ver el procedimiento" apuntando a la primera fuente, y el resto va debajo', async () => {
    const fetchMock = vi.fn(
      withSuggestions([], () =>
        sseResponse([
          sseEvent('result', {
            answered: true,
            answer: 'Contá el efectivo con el supervisor [S1].',
            segments: [],
            sources: [
              {
                source_id: 'S1',
                document_id: 'doc-1',
                document_name: 'Cierre de caja',
                version: 4,
                approved_at: '2026-06-12T00:00:00Z',
                tier: 'aprobado',
              },
              {
                source_id: 'S2',
                document_id: 'doc-2',
                document_name: 'Manual del fabricante · POS',
                version: null,
                approved_at: null,
                tier: 'referencia',
              },
            ],
          }),
        ])
      )
    )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ConsultarPage />)

    await askByTyping(user, '¿Qué necesito para el cierre de caja?')

    const cta = await screen.findByRole('link', { name: /Ver el procedimiento/ })
    expect(cta).toHaveAttribute('href', '/documents/doc-1')

    const secondary = screen.getByRole('link', { name: /Manual del fabricante/ })
    expect(secondary).toHaveAttribute('href', '/documents/doc-2')
  })

  it('un rechazo se muestra como mensaje honesto, no como error, e invita a reformular', async () => {
    const fetchMock = vi.fn(
      withSuggestions([], () =>
        sseResponse([
          sseEvent('result', {
            answered: false,
            answer: '',
            segments: [],
            sources: [],
            refusal_reason: 'No encontré documentación aprobada sobre ese tema.',
          }),
        ])
      )
    )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ConsultarPage />)

    await askByTyping(user, '¿Cuál es el sentido de la vida?')

    expect(await screen.findByText('No encontré documentación aprobada sobre ese tema.')).toBeInTheDocument()
    expect(screen.getByText(/Probá con otras palabras/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('un fallo de red se explica como tal (no un error genérico) y permite reintentar sin perder la pregunta', async () => {
    let shouldFailNetwork = true
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(typeof input === 'string' ? input : input.toString())
      if (url.pathname === '/api/v1/tyto/suggestions') return jsonResponse([])
      if (url.pathname === '/api/v1/tyto/query/stream') {
        if (shouldFailNetwork) {
          shouldFailNetwork = false
          return Promise.reject(new TypeError('Failed to fetch'))
        }
        return sseResponse([
          sseEvent('result', { answered: true, answer: 'Contá el efectivo.', segments: [], sources: [] }),
        ])
      }
      return jsonResponse({ detail: 'not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<ConsultarPage />)

    await askByTyping(user, '¿Cómo cierro la caja?')

    // La pregunta no se pierde: sigue visible arriba del aviso de red.
    expect(await screen.findByText('¿Cómo cierro la caja?')).toBeInTheDocument()
    // El aviso de red aparece tanto arriba del hilo como dentro de la burbuja
    // de la respuesta fallida — ambos son el mismo texto, a propósito.
    await waitFor(() => {
      expect(screen.getAllByText(/No hay conexión con el servidor/).length).toBeGreaterThanOrEqual(1)
    })

    await user.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(await screen.findByText('Contá el efectivo.')).toBeInTheDocument()
  })
})
