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
  version_vigente_id: string | null
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

/**
 * Lo primero que ve quien escanea. Está redactado como una instrucción y no como
 * un estado: alguien parado frente a un documento en papel necesita saber si
 * puede usarlo, no cómo lo clasifica el sistema.
 */
const ESTADOS: Record<string, { titulo: string; detalle: string; tono: 'ok' | 'alerta' | 'neutro' }> = {
  vigente: {
    titulo: 'Esta copia está vigente',
    detalle: 'Es la versión en uso del documento. Podés operar con ella.',
    tono: 'ok',
  },
  superada: {
    titulo: 'No uses esta copia',
    detalle:
      'Hay una versión más nueva del documento. La hoja que tenés quedó sin efecto: pedí la versión actualizada antes de seguir.',
    tono: 'alerta',
  },
  rechazada: {
    titulo: 'Esta copia no tiene validez',
    detalle:
      'Esta versión se revisó y no se aprobó, así que nunca llegó a regir. Pedí la versión aprobada del documento.',
    tono: 'alerta',
  },
  sin_aprobar: {
    titulo: 'Esta copia todavía no está aprobada',
    detalle:
      'El documento sigue en revisión, así que esta hoja es un borrador. No la uses para operar.',
    tono: 'alerta',
  },
  desconocido: {
    titulo: 'No pudimos determinar el estado',
    detalle:
      'Existe la versión, pero su estado no es concluyente. Consultá con el responsable del documento antes de usarla.',
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
          titulo: 'Esta copia venció',
          detalle:
            'Es la última versión aprobada, pero el plazo de vigencia que se fijó al aprobarla ya pasó. Nadie la reemplazó todavía: consultá con el responsable del documento antes de usarla.',
          tono: 'alerta' as const,
        }
      : estadoBase

  const tonoClases = {
    ok: 'border-emerald-300 bg-emerald-50 text-emerald-900',
    alerta: 'border-amber-300 bg-amber-50 text-amber-900',
    neutro: 'border-ink-200 bg-ink-50 text-ink-900',
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-xl px-4 py-8 sm:px-5 sm:py-10">
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
            <h1 className="text-2xl font-bold leading-tight">{estado.titulo}</h1>
            <p className="mt-2 text-[15px] leading-relaxed">{estado.detalle}</p>
            {result.estado === 'superada' && result.version_vigente_number !== null && (
              <div className="mt-3 border-t border-amber-300/60 pt-3">
                <p className="text-sm">
                  La versión que rige hoy es la{' '}
                  <span className="font-bold">{result.version_vigente_number}</span>
                  {formatDate(result.version_vigente_approved_at)
                    ? `, aprobada el ${formatDate(result.version_vigente_approved_at)}`
                    : ''}
                  .
                </p>
                {result.version_vigente_id && (
                  // min-h-11: objetivo táctil cómodo en teléfono, que es de
                  // donde viene casi todo el tráfico de esta página.
                  <a
                    href={`/verificar/${result.version_vigente_id}`}
                    className="mt-2 inline-flex min-h-11 items-center font-semibold underline underline-offset-4"
                  >
                    Ver la versión vigente
                  </a>
                )}
              </div>
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

          <dl className="mt-5 rounded-xl border border-ink-200 bg-white p-4 text-[15px] sm:p-5">
            <Fila label="Versión" value={result.version_number?.toString() ?? null} />
            <Fila label="Aprobada el" value={formatDate(result.approved_at)} />
            <Fila
              label="Vigencia hasta"
              value={formatDate(result.validity_until)}
              nota={vencida ? 'vencida' : undefined}
            />
            {result.detalle_completo && <Fila label="Aprobada por" value={result.approved_by ?? null} />}
          </dl>

          {/*
            La huella va ÚLTIMA y a propósito. Si el documento está superado, lo
            que importa es que no se use; poner acá arriba una explicación sobre
            hashes convierte una advertencia operativa en un tecnicismo, y quien
            escanea desde el teléfono deja de leer antes de llegar a lo que le
            servía.
          */}
          {result.pdf_sha256 && (
            <section className="mt-5 rounded-xl border border-ink-200 bg-ink-50 p-5">
              <h3 className="text-sm font-bold text-ink-900">
                Cómo comprobar que el archivo no fue modificado
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-600">
                Cada documento aprobado queda guardado con una huella digital: un código largo que
                se calcula a partir del archivo. Si alguien le cambia una coma, la huella cambia
                entera. Quien tenga el PDF puede calcular su huella y compararla con esta.
              </p>
              <p className="mt-2 break-all font-mono text-[11px] leading-relaxed text-ink-700">
                {result.pdf_sha256}
              </p>

              {result.estado === 'superada' && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/70 p-3">
                  <p className="text-xs font-bold text-amber-900">
                    Si descargaste esta versión, su huella no va a coincidir. Es lo esperado.
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-amber-900/90">
                    Cuando se descarga una versión superada, el sistema le agrega una banda que
                    avisa que quedó sin efecto. Esa banda se estampa en el momento de la descarga,
                    así que el archivo que recibís no es idéntico al que se aprobó y su huella da
                    distinta. El documento aprobado original está intacto y guardado: no se tocó.
                  </p>
                  <p className="mt-2 text-xs leading-relaxed text-amber-900/90">
                    Para obtener el archivo original, sin la banda, hay que descargarlo desde la
                    aplicación con la opción de documento original. Es la copia cuya huella coincide
                    con el código de arriba.
                  </p>
                </div>
              )}
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
