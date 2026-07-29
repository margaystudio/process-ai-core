'use client'

/**
 * Verificación pública de vigencia — el otro extremo del QR de la portada del PDF.
 *
 * Es pública a propósito: quien escanea puede ser un contratista o un inspector
 * con una copia impresa y sin cuenta. Sin sesión muestra lo mínimo para actuar
 * sobre esa hoja (vigente / superada, fechas, SHA-256); con sesión y membresía
 * en el workspace dueño, la API agrega código, título y aprobador.
 *
 * No usa el layout del dashboard: se abre desde un teléfono, fuera de la app.
 */

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface VerificationResult {
  version_id: string
  estado: 'vigente' | 'superada' | 'rechazada' | 'sin_aprobar' | 'desconocido'
  es_version_vigente: boolean
  version_number: number | null
  approved_at: string | null
  validity_until: string | null
  pdf_sha256: string | null
  version_vigente_number: number | null
  version_vigente_approved_at: string | null
  detalle_completo: boolean
  code?: string | null
  title?: string | null
  document_type_label?: string | null
  approved_by?: string | null
  client_name?: string | null
}

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('es-UY')
}

/** Vencida por fecha aunque el sistema todavía la marque vigente. */
function isExpired(validityUntil: string | null): boolean {
  if (!validityUntil) return false
  const d = new Date(validityUntil)
  return !Number.isNaN(d.getTime()) && d < new Date()
}

const ESTADOS: Record<string, { titulo: string; detalle: string; tono: 'ok' | 'alerta' | 'neutro' }> = {
  vigente: {
    titulo: 'Versión vigente',
    detalle: 'Esta es la versión en uso del documento.',
    tono: 'ok',
  },
  superada: {
    titulo: 'Versión superada',
    detalle: 'Existe una versión más reciente. No uses esta copia para operar.',
    tono: 'alerta',
  },
  rechazada: {
    titulo: 'Versión rechazada',
    detalle: 'Esta versión no llegó a aprobarse. No tiene validez.',
    tono: 'alerta',
  },
  sin_aprobar: {
    titulo: 'Sin aprobar',
    detalle: 'Esta versión todavía está en el circuito de revisión.',
    tono: 'alerta',
  },
}

export default function VerificarPage() {
  const params = useParams()
  const versionId = String(params?.version_id ?? '')

  const [result, setResult] = useState<VerificationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!versionId) return
    let cancelled = false
    ;(async () => {
      try {
        // Se manda el token SOLO si ya hay sesión; sin ella la consulta igual
        // funciona y devuelve la vista mínima.
        const headers: HeadersInit = {}
        try {
          const { getAccessToken } = await import('@/lib/api-auth')
          const token = await getAccessToken()
          if (token) headers['Authorization'] = `Bearer ${token}`
        } catch {
          /* sin sesión: es el caso normal acá */
        }
        const res = await fetch(`${API_URL}/api/v1/verify/${versionId}`, { headers })
        if (cancelled) return
        if (res.status === 404) {
          setError('No encontramos ninguna versión con ese identificador.')
        } else if (!res.ok) {
          setError('No pudimos verificar el documento. Intentá de nuevo en unos minutos.')
        } else {
          setResult(await res.json())
        }
      } catch {
        if (!cancelled) setError('No pudimos conectarnos para verificar el documento.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [versionId])

  const vencida = result ? isExpired(result.validity_until) : false
  const estadoBase = result ? ESTADOS[result.estado] ?? ESTADOS.sin_aprobar : null
  // Una versión vigente cuya vigencia venció no es "vigente" sin más: el
  // documento pide revisión aunque nadie haya aprobado un reemplazo.
  const estado =
    estadoBase && result?.estado === 'vigente' && vencida
      ? {
          titulo: 'Vigencia vencida',
          detalle:
            'Es la última versión aprobada, pero su vigencia venció. Consultá con el responsable del documento antes de usarla.',
          tono: 'alerta' as const,
        }
      : estadoBase

  const tonoClases = {
    ok: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    alerta: 'border-amber-300 bg-amber-50 text-amber-900',
    neutro: 'border-ink-200 bg-ink-50 text-ink-900',
  }

  return (
    <main className="mx-auto min-h-screen max-w-xl px-5 py-10">
      <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
        Verificación de vigencia
      </p>

      {loading && <p className="mt-6 text-sm text-ink-500">Verificando…</p>}

      {error && !loading && (
        <div className="mt-6 rounded-xl border border-ink-200 bg-white p-5">
          <h1 className="text-lg font-bold text-ink-900">No se pudo verificar</h1>
          <p className="mt-2 text-sm text-ink-600">{error}</p>
          <p className="mt-4 break-all font-mono text-xs text-ink-400">{versionId}</p>
        </div>
      )}

      {result && estado && !loading && (
        <>
          <div className={`mt-4 rounded-xl border p-5 ${tonoClases[estado.tono]}`}>
            <h1 className="text-xl font-bold">{estado.titulo}</h1>
            <p className="mt-1.5 text-sm">{estado.detalle}</p>
            {result.estado === 'superada' && result.version_vigente_number !== null && (
              <p className="mt-2 text-sm font-semibold">
                Versión vigente: {result.version_vigente_number}
                {formatDate(result.version_vigente_approved_at)
                  ? ` (aprobada el ${formatDate(result.version_vigente_approved_at)})`
                  : ''}
              </p>
            )}
          </div>

          {result.detalle_completo && (
            <section className="mt-5 rounded-xl border border-ink-200 bg-white p-5">
              {result.document_type_label && (
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">
                  {result.document_type_label}
                </p>
              )}
              <h2 className="mt-1 text-lg font-bold text-ink-900">{result.title}</h2>
              <p className="mt-1 text-sm text-ink-500">
                {result.code && <span className="font-mono font-semibold">{result.code}</span>}
                {result.code && ' · '}
                {result.client_name}
              </p>
            </section>
          )}

          <dl className="mt-5 rounded-xl border border-ink-200 bg-white p-5 text-sm">
            <Fila label="Versión" value={result.version_number?.toString() ?? null} />
            <Fila label="Aprobada el" value={formatDate(result.approved_at)} />
            <Fila
              label="Vigencia hasta"
              value={formatDate(result.validity_until)}
              nota={vencida ? 'vencida' : undefined}
            />
            {result.detalle_completo && <Fila label="Aprobada por" value={result.approved_by ?? null} />}
          </dl>

          {result.pdf_sha256 && (
            <section className="mt-5 rounded-xl border border-ink-200 bg-ink-50 p-5">
              <h3 className="text-sm font-bold text-ink-900">Huella del PDF aprobado</h3>
              <p className="mt-1 text-xs leading-relaxed text-ink-600">
                Si tenés el archivo, su SHA-256 tiene que coincidir con este. Si no coincide, el PDF
                fue modificado después de aprobarse.
              </p>
              <p className="mt-2 break-all font-mono text-[11px] text-ink-700">{result.pdf_sha256}</p>
            </section>
          )}

          {!result.detalle_completo && (
            <p className="mt-5 text-xs text-ink-400">
              Iniciá sesión con una cuenta de la organización para ver el código, el título y quién
              aprobó el documento.
            </p>
          )}

          <p className="mt-6 break-all font-mono text-[10px] text-ink-300">{result.version_id}</p>
        </>
      )}
    </main>
  )
}

function Fila({ label, value, nota }: { label: string; value: string | null; nota?: string }) {
  if (!value) return null
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-ink-100 py-2 last:border-0">
      <dt className="text-ink-500">{label}</dt>
      <dd className="font-semibold text-ink-900">
        {value}
        {nota && <span className="ml-2 text-xs font-normal text-amber-700">({nota})</span>}
      </dd>
    </div>
  )
}
