/**
 * Página pública de verificación — lo que ve alguien con una copia en papel.
 *
 * Se testea el ORDEN y no solo el contenido. Si el documento está superado, lo
 * que importa es que no se use; una explicación sobre huellas digitales antes de
 * esa advertencia convierte algo operativo en un tecnicismo, y quien escanea
 * desde el teléfono deja de leer antes de llegar a lo que le servía.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import VerificarPage from '@/app/verificar/[version_id]/page'

vi.mock('next/navigation', () => ({
  useParams: () => ({ version_id: 'ver-superada' }),
}))

const BASE = {
  version_id: 'ver-superada',
  es_version_vigente: false,
  version_number: 2,
  approved_at: '2026-03-10T12:00:00Z',
  validity_until: null,
  pdf_sha256: 'a'.repeat(64),
  version_vigente_number: null,
  version_vigente_id: null,
  version_vigente_approved_at: null,
  detalle_completo: false,
}

function responder(payload: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ...BASE, ...payload }),
    })
  )
}

describe('página de verificación', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('lo primero que dice de una versión superada es que no se use', async () => {
    responder({
      estado: 'superada',
      version_vigente_number: 5,
      version_vigente_id: 'ver-vigente',
      version_vigente_approved_at: '2026-07-01T12:00:00Z',
    })
    const { container } = render(<VerificarPage />)

    const titulo = await screen.findByRole('heading', { level: 1 })
    expect(titulo).toHaveTextContent('No uses esta copia')

    // El veredicto va ANTES que la explicación de la huella, en el documento.
    const texto = container.textContent ?? ''
    expect(texto.indexOf('No uses esta copia')).toBeLessThan(
      texto.indexOf('Cómo comprobar que el archivo no fue modificado')
    )
  })

  it('dice cuál es la versión vigente y enlaza a ella', async () => {
    responder({
      estado: 'superada',
      version_vigente_number: 5,
      version_vigente_id: 'ver-vigente',
      version_vigente_approved_at: '2026-07-01T12:00:00Z',
    })
    render(<VerificarPage />)

    const link = await screen.findByRole('link', { name: /ver la versión vigente/i })
    expect(link).toHaveAttribute('href', '/verificar/ver-vigente')
    expect(screen.getByText(/la versión que rige hoy es la/i)).toBeInTheDocument()
  })

  it('explica por qué la huella de una copia sellada no coincide', async () => {
    responder({ estado: 'superada', version_vigente_number: 5, version_vigente_id: 'v5' })
    render(<VerificarPage />)

    expect(
      await screen.findByText(/su huella no va a coincidir. Es lo esperado/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/le agrega una banda/i)).toBeInTheDocument()
    expect(screen.getByText(/está intacto y guardado/i)).toBeInTheDocument()
    expect(screen.getByText(/opción de documento original/i)).toBeInTheDocument()
  })

  it('no mete la aclaración de la banda cuando la versión está vigente', async () => {
    responder({ estado: 'vigente', es_version_vigente: true, version_number: 5 })
    render(<VerificarPage />)

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'Esta copia está vigente'
    )
    // La huella se sigue mostrando; lo que no corresponde es la advertencia.
    expect(screen.getByText(/Cómo comprobar que el archivo no fue modificado/i)).toBeInTheDocument()
    expect(screen.queryByText(/su huella no va a coincidir/i)).not.toBeInTheDocument()
  })

  it('una versión aprobada con la vigencia vencida no se anuncia como vigente', async () => {
    responder({
      estado: 'vigente',
      es_version_vigente: true,
      validity_until: '2020-01-01T00:00:00Z',
    })
    render(<VerificarPage />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Esta copia venció')
    )
  })
})
