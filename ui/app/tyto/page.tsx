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
  const abortRef = useRef<AbortController | null>(null)
  const threadEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    threadEndRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages])

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

    function handleEvent(event: TytoStreamEvent) {
      if (event.type === 'token') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.role === 'assistant'
              ? { ...m, text: m.text + event.text }
              : m
          )
        )
        return
      }
      if (event.type === 'result') {
        if (event.data.answered) {
          patchAssistant({ status: 'answered', text: event.data.answer, result: event.data })
        } else {
          patchAssistant({
            status: 'refused',
            text: event.data.refusal_reason || 'No encontré documentación aprobada suficiente para responder con confianza.',
          })
        }
        return
      }
      // event.type === 'error'
      patchAssistant({ status: 'error', errorDetail: event.detail })
    }

    try {
      await streamTytoQuery(question, handleEvent, controller.signal)
    } catch (err) {
      patchAssistant({
        status: 'error',
        errorDetail: err instanceof Error ? err.message : 'No se pudo conectar con Tyto.',
      })
    } finally {
      setSending(false)
      abortRef.current = null
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col" data-module="process">
      <header className="flex flex-shrink-0 items-center gap-3.5 border-b border-line px-6 py-5">
        <TytoHeaderAvatar />
        <div className="min-w-0">
          <h1 className="text-h2 text-ink-900">Tyto</h1>
          <p className="mt-0.5 truncate text-[12.5px] text-ink-400">
            Solo consulta la red documental aprobada · cita fuente, versión y estado
          </p>
        </div>
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
