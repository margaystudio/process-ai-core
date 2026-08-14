// components/tyto/TytoConsultarComposer.tsx
// Composer de /consultar: campo grande + un solo control grande a la derecha
// (micrófono si el campo está vacío, enviar si ya hay texto) — pensado para un
// pulgar con guante, no para un teclado. Grabar reemplaza toda la fila por una
// barra "en vivo" (punto pulsando + timer + cancelar/usar): nunca un texto
// estático que no deje claro que está grabando.
'use client'

import { useRef, useState, type FormEvent } from 'react'
import { Mic, Send, Square, X } from 'lucide-react'
import { Spinner } from '@/shared/ui/components'
import { useTytoVoiceRecorder, formatVoiceSeconds } from '@/hooks/useTytoVoiceRecorder'

export function TytoConsultarComposer({
  disabled,
  onSubmit,
}: {
  disabled: boolean
  onSubmit: (question: string) => void
}) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const voice = useTytoVoiceRecorder((text) => {
    setValue((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))
    inputRef.current?.focus()
  })

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  const isRecording = voice.status === 'recording' || voice.status === 'requesting'
  const isTranscribing = voice.status === 'transcribing'
  const showMic = voice.supported && !value.trim()

  return (
    <div className="flex-shrink-0 border-t border-line bg-surface px-4 pb-[max(env(safe-area-inset-bottom),12px)] pt-3 sm:px-6">
      <div className="mx-auto max-w-[640px]">
        {isRecording ? (
          <div className="flex h-14 items-center gap-2 rounded-lg border-[1.5px] border-danger-bd bg-danger-bg pl-2 pr-2">
            <button
              type="button"
              onClick={voice.cancel}
              aria-label="Cancelar grabación"
              className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-md text-danger transition-colors hover:bg-white/50 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
            >
              <X size={20} aria-hidden="true" />
            </button>

            <div className="flex min-w-0 flex-1 items-center gap-2.5" role="status">
              <span className="relative grid h-3 w-3 flex-shrink-0 place-items-center" aria-hidden="true">
                <span className="absolute inset-0 animate-ping rounded-full bg-danger/50" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-danger" />
              </span>
              <span className="font-mono text-body font-bold text-ink-900">
                {formatVoiceSeconds(voice.seconds)}
              </span>
              <span className="truncate text-sm text-ink-600">
                {voice.status === 'requesting' ? 'Pidiendo el micrófono…' : 'Escuchando tu pregunta…'}
              </span>
            </div>

            <button
              type="button"
              onClick={voice.stop}
              disabled={voice.status !== 'recording'}
              aria-label="Detener grabación y transcribir"
              className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-md bg-danger text-white transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-danger/30 disabled:opacity-50"
            >
              <Square size={16} aria-hidden="true" fill="currentColor" />
            </button>
          </div>
        ) : isTranscribing ? (
          <div className="flex h-14 items-center gap-3 rounded-lg border-[1.5px] border-line bg-surface-app px-4">
            <Spinner size="sm" />
            <span className="text-sm font-semibold text-ink-700">Transcribiendo tu pregunta…</span>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex items-center gap-2.5">
            <label htmlFor="tyto-consultar-question" className="sr-only">
              Pregunta para Tyto
            </label>
            <input
              id="tyto-consultar-question"
              ref={inputRef}
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={disabled}
              placeholder="Escribí o grabá tu pregunta…"
              className="h-14 min-w-0 flex-1 rounded-lg border-[1.5px] border-line bg-surface-app px-4 text-body text-ink-800 outline-none transition-colors placeholder:text-ink-500 focus:border-action focus:ring-[3px] focus:ring-action-ring disabled:cursor-not-allowed disabled:opacity-60"
            />
            {showMic ? (
              <button
                type="button"
                onClick={voice.start}
                disabled={disabled}
                aria-label="Grabar pregunta por voz"
                className="grid h-14 w-14 flex-shrink-0 place-items-center rounded-lg bg-ink-800 text-white transition-colors hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring disabled:cursor-not-allowed disabled:bg-ink-150 disabled:text-ink-400"
              >
                <Mic size={24} aria-hidden="true" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={disabled || !value.trim()}
                aria-label="Enviar pregunta"
                className="grid h-14 w-14 flex-shrink-0 place-items-center rounded-lg bg-action text-action-on transition-colors hover:bg-action-hover focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring disabled:cursor-not-allowed disabled:bg-ink-150 disabled:text-ink-400"
              >
                <Send size={22} aria-hidden="true" />
              </button>
            )}
          </form>
        )}

        {voice.status === 'permission-denied' && (
          <p role="alert" className="mt-2 text-[12.5px] leading-relaxed text-danger">
            No pudimos acceder al micrófono. Activá el permiso para este sitio en la
            configuración del navegador y volvé a intentar — o escribí tu pregunta.
          </p>
        )}
        {voice.status === 'error' && voice.errorMessage && (
          <div
            role="alert"
            className="mt-2 flex items-start justify-between gap-3 text-[12.5px] leading-relaxed text-danger"
          >
            <span>{voice.errorMessage}</span>
            <button
              type="button"
              onClick={voice.dismissError}
              className="flex-shrink-0 font-bold underline underline-offset-2"
            >
              Descartar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
