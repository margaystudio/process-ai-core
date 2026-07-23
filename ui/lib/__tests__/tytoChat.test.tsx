import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import TytoPage from '@/app/tyto/page'

// La página no gatea por rol (Tyto es para cualquier staff del workspace, igual
// que el backend): no hace falta mockear WorkspaceContext acá.

// Aísla la autenticación: el foco del test es el parseo del stream SSE, no el
// armado de headers (eso ya lo cubre api-auth por su cuenta).
vi.mock('@/lib/api-auth', () => ({
  getAuthHeaders: vi.fn(async () => ({ 'Content-Type': 'application/json' })),
  getAccessToken: vi.fn(async () => null),
  getActiveTenantId: vi.fn(() => null),
  setActiveTenantId: vi.fn(),
}))

const PLACEHOLDER = 'Preguntá sobre cualquier procedimiento…'

function sseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

/** Arma una Response cuyo body es un ReadableStream con los bloques SSE dados. */
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

async function askQuestion(question: string) {
  const user = userEvent.setup()
  render(<TytoPage />)
  await user.type(screen.getByPlaceholderText(PLACEHOLDER), question)
  await user.click(screen.getByRole('button', { name: 'Enviar pregunta' }))
  return user
}

describe('TytoPage — chat streaming', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('muestra el texto de los tokens a medida que van llegando', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        sseEvent('token', { text: 'Contá el efectivo ' }),
        sseEvent('token', { text: 'con el supervisor [S1].' }),
        sseEvent('result', {
          answered: true,
          answer: 'Contá el efectivo con el supervisor [S1].',
          segments: [
            { text: 'Contá el efectivo con el supervisor', source_ids: ['S1'], tier: 'aprobado' },
          ],
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
        }),
      ])
    )
    vi.stubGlobal('fetch', fetchMock)

    await askQuestion('¿Qué necesito para hacer el cierre de caja?')

    expect(
      await screen.findByText('¿Qué necesito para hacer el cierre de caja?')
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/Contá el efectivo/)).toBeInTheDocument()
    })
  })

  it('al llegar `result` aparecen los badges con el copy exacto por nivel de cada fuente', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        sseEvent('token', { text: 'Necesitás POS, SAP y un Supervisor [S1] [S2] [S3].' }),
        sseEvent('result', {
          answered: true,
          answer: 'Necesitás POS, SAP y un Supervisor [S1] [S2] [S3].',
          segments: [
            { text: 'Necesitás POS, SAP y un Supervisor', source_ids: ['S1', 'S2', 'S3'], tier: 'aprobado' },
          ],
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
            {
              source_id: 'S3',
              document_id: 'doc-3',
              document_name: 'Fondo fijo $20.000',
              version: null,
              approved_at: null,
              tier: 'inferido',
            },
          ],
        }),
      ])
    )
    vi.stubGlobal('fetch', fetchMock)

    await askQuestion('¿Qué necesito para el cierre de caja?')

    // Antes del `result` NUNCA se pintan niveles — al terminar, el copy exacto
    // aparece una vez por fuente en la card + una vez en la leyenda de niveles.
    expect((await screen.findAllByText('Fuente aprobada')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Referencia no validada')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Inferido')).length).toBeGreaterThan(0)

    // Nunca la palabra "verificado" en esta pantalla.
    expect(screen.queryByText(/verificado/i)).not.toBeInTheDocument()
  })

  it('mientras streamea, los marcadores [Sn] se muestran neutros (sin color de nivel)', async () => {
    // Sin evento `result` todavía: el mensaje queda en estado streaming y el
    // marcador [S1] debe mostrarse neutro, no como link a ninguna fuente.
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([sseEvent('token', { text: 'Arqueá el efectivo [S1].' })])
    )
    vi.stubGlobal('fetch', fetchMock)

    await askQuestion('¿Cómo hago el arqueo?')

    await waitFor(() => {
      expect(screen.getByText('S1')).toBeInTheDocument()
    })
    // Antes de `result` el marcador no es un link (no hay ficha de documento resuelta).
    expect(screen.getByText('S1').closest('a')).toBeNull()
  })

  it('un `result` de rechazo se renderiza como mensaje del asistente, no como error', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
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
    vi.stubGlobal('fetch', fetchMock)

    await askQuestion('¿Cuál es el sentido de la vida?')

    expect(
      await screen.findByText('No encontré documentación aprobada sobre ese tema.')
    ).toBeInTheDocument()

    // No debe verse como un error real: sin rol de alerta ni botón de reintento.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument()
  })

  it('un evento `error` se muestra como error real, distinto del rechazo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        sseEvent('token', { text: 'Registrá ' }),
        sseEvent('error', { detail: 'Tyto no pudo generar una respuesta confiable' }),
      ])
    )
    vi.stubGlobal('fetch', fetchMock)

    await askQuestion('¿Cómo cierro la caja?')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Tyto no pudo generar una respuesta confiable')
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })
})
