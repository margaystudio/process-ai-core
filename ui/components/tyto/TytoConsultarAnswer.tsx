// components/tyto/TytoConsultarAnswer.tsx
// La respuesta en /consultar: mismo contrato de estados que el hilo completo
// (streaming/thinking, respondida, rechazo honesto, error real — ver
// TytoMessageBubble), pero con la acción que de verdad importa acá arriba de
// todo: un botón grande para abrir el procedimiento citado. Si hay más de una
// fuente, la primera es la acción principal y el resto van más chicas debajo.
'use client'

import Link from 'next/link'
import { AlertCircle, FileText, Info } from 'lucide-react'
import { TytoAnswerText } from './TytoAnswerText'
import { TierDot } from '@/shared/ui/components'
import type { TytoAssistantMessage } from './types'

export function TytoConsultarAnswer({
  message,
  onRetry,
}: {
  message: TytoAssistantMessage
  onRetry: (question: string) => void
}) {
  const isThinking = message.status === 'streaming' && message.text.length === 0
  const sources = message.status === 'answered' ? message.result?.sources ?? [] : []
  const [primarySource, ...otherSources] = sources

  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card sm:p-5">
      {message.status === 'error' ? (
        <div role="alert" className="flex items-start gap-3">
          <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-danger" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-body font-semibold text-danger">
              {message.errorDetail || 'Tyto no pudo generar una respuesta confiable.'}
            </p>
            <button
              type="button"
              onClick={() => onRetry(message.question)}
              className="mt-3 inline-flex h-11 items-center rounded-lg border border-ink-300 bg-white px-4 text-sm font-bold text-ink-800 transition-colors hover:bg-ink-100 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
            >
              Reintentar
            </button>
          </div>
        </div>
      ) : isThinking ? (
        <TytoConsultarThinking />
      ) : message.status === 'refused' ? (
        <div className="flex items-start gap-3">
          <Info size={20} className="mt-0.5 flex-shrink-0 text-ink-600" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-body leading-relaxed text-ink-800">{message.text}</p>
            <p className="mt-2 text-sm text-ink-600">
              Probá con otras palabras o preguntá algo distinto — Tyto solo responde con lo
              que está aprobado.
            </p>
          </div>
        </div>
      ) : (
        <>
          {message.searchDegraded && (
            <div
              role="status"
              className="mb-3 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2"
            >
              <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-amber-700" aria-hidden="true" />
              <p className="text-[12px] leading-relaxed text-amber-900">
                La búsqueda semántica no está disponible ahora, así que esto puede estar
                incompleto.
              </p>
            </div>
          )}

          <TytoAnswerText
            text={message.text}
            sources={message.status === 'answered' ? message.result?.sources ?? [] : null}
          />

          {primarySource && (
            <div className="mt-4 border-t border-line pt-4">
              <Link
                href={`/documents/${primarySource.document_id}`}
                className="flex h-14 w-full items-center justify-center gap-2 rounded-lg bg-ink-800 px-4 text-body font-bold text-white transition-colors hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
              >
                <FileText size={19} aria-hidden="true" />
                Ver el procedimiento
              </Link>
              <div className="mt-2 flex items-center justify-center gap-1.5 text-center text-xs text-ink-600">
                <TierDot tier={primarySource.tier} />
                <span className="truncate">{primarySource.document_name}</span>
              </div>

              {otherSources.length > 0 && (
                <div className="mt-3 flex flex-col gap-1">
                  <span className="px-1 text-[11px] font-extrabold uppercase tracking-[.06em] text-ink-500">
                    También se usó
                  </span>
                  {otherSources.map((source) => (
                    <Link
                      key={source.source_id}
                      href={`/documents/${source.document_id}`}
                      className="flex min-h-[38px] items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ink-600 transition-colors hover:bg-ink-100 hover:text-ink-800"
                    >
                      <TierDot tier={source.tier} />
                      <span className="truncate">{source.document_name}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TytoConsultarThinking() {
  return (
    <div className="flex items-center gap-1.5 py-1" role="status" aria-label="Tyto está pensando">
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300 [animation-delay:300ms]" />
    </div>
  )
}
