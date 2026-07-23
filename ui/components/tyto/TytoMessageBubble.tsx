// components/tyto/TytoMessageBubble.tsx
// Un turno del hilo de chat: burbuja del usuario a la derecha, respuesta de
// Tyto a la izquierda con sus 4 estados (pensando / streameando / respondida /
// rechazo honesto / error real). El rechazo (`refused`) es Tyto diciendo que no
// tiene documentación aprobada suficiente — estilo neutro, nunca rojo.
'use client'

import { AlertCircle, Info } from 'lucide-react'
import { TytoAnswerText } from './TytoAnswerText'
import type { TytoAssistantMessage, TytoUserMessage } from './types'

export function TytoUserBubble({ message }: { message: TytoUserMessage }) {
  return (
    <div className="mb-4 flex justify-end">
      <div className="max-w-[75%] rounded-[14px_14px_4px_14px] bg-ink-800 px-4 py-[11px] text-sm font-semibold leading-normal text-white">
        {message.question}
      </div>
    </div>
  )
}

export function TytoAssistantBubble({
  message,
  onRetry,
}: {
  message: TytoAssistantMessage
  onRetry: (question: string) => void
}) {
  const isThinking = message.status === 'streaming' && message.text.length === 0
  const sourceCount = message.status === 'answered' ? message.result?.sources.length ?? 0 : 0

  return (
    <div className="mb-6">
      <div className="mb-2.5 flex items-center gap-2">
        <TytoMiniAvatar />
        <span className="text-[13px] font-extrabold text-ink-900">Tyto</span>
      </div>

      {message.status === 'error' ? (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-lg border border-danger-bd bg-danger-bg px-3.5 py-3"
        >
          <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-danger" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-danger">
              {message.errorDetail || 'Tyto no pudo generar una respuesta confiable.'}
            </p>
            <button
              type="button"
              onClick={() => onRetry(message.question)}
              className="mt-2 text-[12px] font-bold text-ink-700 underline underline-offset-2"
            >
              Reintentar
            </button>
          </div>
        </div>
      ) : (
        <div className="rounded-[14px] border border-line bg-surface px-4 py-4 shadow-card">
          {sourceCount > 0 && (
            <div className="mb-3 inline-flex items-center gap-1.5 rounded-pill border border-indigo-border bg-indigo-tint px-3 py-1 text-xs font-bold text-indigo">
              Construida con {sourceCount} {sourceCount === 1 ? 'pieza' : 'piezas'} de la red aprobada
            </div>
          )}

          {message.status === 'refused' ? (
            <div className="flex items-start gap-2.5">
              <Info size={16} className="mt-0.5 flex-shrink-0 text-ink-400" aria-hidden="true" />
              <p className="text-body leading-relaxed text-ink-700">{message.text}</p>
            </div>
          ) : isThinking ? (
            <TytoThinkingIndicator />
          ) : (
            <TytoAnswerText
              text={message.text}
              sources={message.status === 'answered' ? message.result?.sources ?? [] : null}
            />
          )}
        </div>
      )}
    </div>
  )
}

function TytoThinkingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1" role="status" aria-label="Tyto está pensando">
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300 [animation-delay:150ms]" />
      <span className="h-2 w-2 animate-pulse rounded-full bg-ink-300 [animation-delay:300ms]" />
    </div>
  )
}

function TytoMiniAvatar() {
  return (
    <span
      className="grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-[7px] bg-indigo text-white"
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2.2}>
        <circle cx="12" cy="12" r="9" opacity={0.5} />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </span>
  )
}
