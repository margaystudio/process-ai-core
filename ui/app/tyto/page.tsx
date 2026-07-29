'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { streamTytoQuery, type TytoQueryResult, type TytoStreamEvent } from '@/lib/api'
import { TytoUserBubble, TytoAssistantBubble } from '@/components/tyto/TytoMessageBubble'
import { TytoSourcesPanel } from '@/components/tyto/TytoSourcesPanel'
import { TytoComposer } from '@/components/tyto/TytoComposer'
import type { TytoAssistantMessage, TytoMessage } from '@/components/tyto/types'

function TytoHeaderAvatar() {
  return (
    <span
      className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-[13px] bg-indigo text-white"
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="9" opacity={0.5} />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </span>
  )
}

function TytoEmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <div className="mb-1 text-[15px] font-bold text-ink-700">
        Preguntale a Tyto sobre cualquier procedimiento
      </div>
      <p className="max-w-sm text-[13px] leading-relaxed text-ink-400">
        Tyto responde solo con documentación aprobada y siempre cita la fuente,
        la versión y el estado de lo que usó.
      </p>
    </div>
  )
}

export default function TytoPage() {
  const [messages, setMessages] = useState<TytoMessage[]>([])
  const [sending, setSending] = useState(false)
  const idRef = useRef(0)
  // Conversación en curso. En ref y no en estado: se lee y se escribe dentro del
  // handler del stream, y un valor de estado quedaría capturado por el closure
  // en el valor que tenía al empezar la consulta. Además no afecta al render.
  const sessionIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const threadEndRef = useRef<HTMLDivElement | null>(null)
  // Buffer de tokens del stream: sin esto, cada token disparaba un setState
  // (re-render de todas las burbujas) + un scrollIntoView (reflow forzado).
  const pendingTokensRef = useRef('')
  const flushTimerRef = useRef<number | null>(null)

  useEffect(() => {
    threadEndRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages])

  useEffect(() => {
    return () => {
      if (flushTimerRef.current !== null) window.clearTimeout(flushTimerRef.current)
    }
  }, [])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  // Última respuesta contestada — es la que se refleja en el panel de fuentes.
  const lastAnsweredResult: TytoQueryResult | null = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i]
      if (m.role === 'assistant' && m.status === 'answered' && m.result) return m.result
    }
    return null
  }, [messages])

  function nextId(prefix: string): string {
    idRef.current += 1
    return `${prefix}-${idRef.current}`
  }

  async function ask(question: string) {
    const userId = nextId('user')
    const assistantId = nextId('assistant')

    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', question },
      { id: assistantId, role: 'assistant', question, status: 'streaming', text: '' },
    ])
    setSending(true)

    const controller = new AbortController()
    abortRef.current = controller

    function patchAssistant(patch: Partial<TytoAssistantMessage>) {
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId && m.role === 'assistant' ? { ...m, ...patch } : m))
      )
    }

    function flushTokens() {
      flushTimerRef.current = null
      const chunk = pendingTokensRef.current
      if (!chunk) return
      pendingTokensRef.current = ''
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.role === 'assistant'
            ? { ...m, text: m.text + chunk }
            : m
        )
      )
    }

    function clearPendingTokens() {
      if (flushTimerRef.current !== null) {
        window.clearTimeout(flushTimerRef.current)
        flushTimerRef.current = null
      }
      pendingTokensRef.current = ''
    }

    function handleEvent(event: TytoStreamEvent) {
      if (event.type === 'session') {
        // Llega antes que el primer token: a partir de acá, todas las preguntas
        // de esta conversación viajan con el mismo id. Sin esto cada pregunta
        // sería una sesión de un mensaje y el historial no serviría para nada.
        sessionIdRef.current = event.sessionId
        return
      }
      if (event.type === 'token') {
        // Acumular y flushear cada ~50ms: un solo re-render por lote de tokens.
        pendingTokensRef.current += event.text
        if (flushTimerRef.current === null) {
          flushTimerRef.current = window.setTimeout(flushTokens, 50)
        }
        return
      }
      if (event.type === 'result') {
        // El result trae el texto completo: descartar lo pendiente del buffer.
        clearPendingTokens()
        const searchDegraded = Boolean(event.data.search_degraded)
        if (event.data.answered) {
          patchAssistant({
            status: 'answered',
            text: event.data.answer,
            result: event.data,
            searchDegraded,
          })
        } else {
          patchAssistant({
            status: 'refused',
            // El backend ya redacta el rechazo degradado sin afirmar que no haya
            // documentación; el fallback de acá solo cubre un result sin motivo.
            text: event.data.refusal_reason || 'No encontré documentación aprobada suficiente para responder con confianza.',
            searchDegraded,
          })
        }
        return
      }
      // event.type === 'error'
      clearPendingTokens()
      patchAssistant({ status: 'error', errorDetail: event.detail })
    }

    try {
      await streamTytoQuery(question, handleEvent, controller.signal, sessionIdRef.current)
      // Si el stream terminó sin evento result (corte), mostrar lo acumulado.
      flushTokens()
    } catch (err) {
      clearPendingTokens()
      patchAssistant({
        status: 'error',
        errorDetail: err instanceof Error ? err.message : 'No se pudo conectar con Tyto.',
      })
    } finally {
      setSending(false)
      abortRef.current = null
    }
  }

  function startNewConversation() {
    // Solo se suelta el id y se limpia la vista. Lo ya escrito en
    // `tyto_query_log` no se toca: es auditoría, no historial de chat.
    abortRef.current?.abort()
    sessionIdRef.current = null
    setMessages([])
    setSending(false)
  }

  return (
    <div className="flex h-full min-h-0 flex-col" data-module="process">
      <header className="flex flex-shrink-0 items-center gap-3.5 border-b border-line px-6 py-5">
        <TytoHeaderAvatar />
        <div className="min-w-0 flex-1">
          <h1 className="text-h2 text-ink-900">Tyto</h1>
          <p className="mt-0.5 truncate text-[12.5px] text-ink-400">
            Solo consulta la red documental aprobada · cita fuente, versión y estado
          </p>
        </div>
        {/*
          Corta el hilo: la próxima pregunta abre una conversación nueva en vez
          de colgarse de la anterior. Sin esto, todo lo que alguien pregunte en
          el día queda en una sola sesión y el historial no distingue temas.
        */}
        <button
          type="button"
          onClick={startNewConversation}
          disabled={sending || messages.length === 0}
          className="flex-shrink-0 rounded-lg border border-line px-3 py-2 text-[12.5px] font-bold text-ink-700 transition-colors hover:bg-ink-50 disabled:opacity-40"
        >
          Nueva conversación
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            {messages.length === 0 ? (
              <TytoEmptyState />
            ) : (
              <div className="mx-auto max-w-[820px]">
                {messages.map((m) =>
                  m.role === 'user' ? (
                    <TytoUserBubble key={m.id} message={m} />
                  ) : (
                    <TytoAssistantBubble key={m.id} message={m} onRetry={ask} />
                  )
                )}
                <div ref={threadEndRef} />
              </div>
            )}
          </div>

          <TytoComposer disabled={sending} onSubmit={ask} />
        </div>

        <TytoSourcesPanel result={lastAnsweredResult} />
      </div>
    </div>
  )
}
