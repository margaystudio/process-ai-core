'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, History, X } from 'lucide-react'
import {
  deleteTytoSession,
  getTytoSession,
  getTytoSessions,
  streamTytoQuery,
  updateTytoSession,
  type TytoQueryResult,
  type TytoSessionSummary,
  type TytoStreamEvent,
} from '@/lib/api'
import { mapSessionEntryToMessages, sortTytoSessions, useDebouncedValue } from '@/lib/tytoHistory'
import { TytoUserBubble, TytoAssistantBubble } from '@/components/tyto/TytoMessageBubble'
import { TytoSourcesPanel } from '@/components/tyto/TytoSourcesPanel'
import { TytoComposer } from '@/components/tyto/TytoComposer'
import { TytoConversationsPanel } from '@/components/tyto/TytoConversationsPanel'
import { Skeleton } from '@/shared/ui/components'
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

/** Ocupa el área del hilo mientras se retoma una conversación guardada. */
function TytoHistorySkeleton() {
  return (
    <div className="mx-auto flex max-w-[820px] flex-col gap-6" aria-hidden="true">
      {[0, 1].map((i) => (
        <div key={i} className="flex flex-col gap-2.5">
          <div className="flex justify-end">
            <Skeleton className="h-8 w-2/5 rounded-[14px_14px_4px_14px]" />
          </div>
          <Skeleton className="h-24 w-4/5 rounded-[14px]" />
        </div>
      ))}
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

  // ── Historial de conversaciones ───────────────────────────────────────────
  // Espejo en estado de `sessionIdRef`, solo para poder resaltar la fila activa
  // en el panel (un ref no dispara re-render).
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<TytoSessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const debouncedSearch = useDebouncedValue(searchInput, 300)
  const [pendingSessionIds, setPendingSessionIds] = useState<Set<string>>(new Set())
  const [actionError, setActionError] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<{ session: TytoSessionSummary; message: string } | null>(null)
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  const loadSessions = useCallback(async (q: string, opts?: { silent?: boolean }) => {
    if (!opts?.silent) setSessionsLoading(true)
    setSessionsError(null)
    try {
      const data = await getTytoSessions(q || undefined)
      setSessions(data)
    } catch (err) {
      setSessionsError(
        err instanceof Error ? err.message : 'No se pudieron cargar tus conversaciones.'
      )
    } finally {
      if (!opts?.silent) setSessionsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSessions(debouncedSearch)
  }, [debouncedSearch, loadSessions])

  // Cierre con Escape y scroll-lock del body mientras el drawer mobile está abierto.
  useEffect(() => {
    if (!mobilePanelOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMobilePanelOpen(false)
    }
    document.addEventListener('keydown', onKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [mobilePanelOpen])

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

  async function withPendingAction(id: string, action: () => Promise<void>) {
    setPendingSessionIds((prev) => new Set(prev).add(id))
    try {
      await action()
    } finally {
      setPendingSessionIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  async function renameSession(session: TytoSessionSummary, title: string) {
    const previous = sessions
    setSessions((prev) =>
      sortTytoSessions(prev.map((s) => (s.id === session.id ? { ...s, title } : s)))
    )
    await withPendingAction(session.id, async () => {
      try {
        const updated = await updateTytoSession(session.id, { title })
        setSessions((prev) => sortTytoSessions(prev.map((s) => (s.id === session.id ? updated : s))))
      } catch (err) {
        setSessions(previous)
        setActionError(err instanceof Error ? err.message : 'No se pudo renombrar la conversación.')
      }
    })
  }

  async function togglePin(session: TytoSessionSummary) {
    const previous = sessions
    const nextPinned = !session.pinned
    setSessions((prev) =>
      sortTytoSessions(prev.map((s) => (s.id === session.id ? { ...s, pinned: nextPinned } : s)))
    )
    await withPendingAction(session.id, async () => {
      try {
        const updated = await updateTytoSession(session.id, { pinned: nextPinned })
        setSessions((prev) => sortTytoSessions(prev.map((s) => (s.id === session.id ? updated : s))))
      } catch (err) {
        setSessions(previous)
        setActionError(
          err instanceof Error ? err.message : 'No se pudo anclar/desanclar la conversación.'
        )
      }
    })
  }

  async function deleteSession(session: TytoSessionSummary) {
    const previous = sessions
    await withPendingAction(session.id, async () => {
      try {
        await deleteTytoSession(session.id)
        setSessions((prev) => prev.filter((s) => s.id !== session.id))
        // La conversación borrada era la que se estaba viendo: no dejarla en
        // pantalla como si siguiera existiendo.
        if (sessionIdRef.current === session.id) {
          startNewConversation()
        }
      } catch (err) {
        setSessions(previous)
        setActionError(err instanceof Error ? err.message : 'No se pudo eliminar la conversación.')
      }
    })
  }

  async function resumeSession(session: TytoSessionSummary) {
    // Retomar corta cualquier pregunta en vuelo: la respuesta de una
    // conversación no puede terminar escribiéndose sobre otra.
    abortRef.current?.abort()
    setSending(false)
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const detail = await getTytoSession(session.id)
      // Se ordena acá por las dudas de que el backend no garantice el orden:
      // un hilo fuera de orden se lee como una conversación rota.
      const orderedEntries = [...detail.entries].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      )
      const built: TytoMessage[] = []
      for (const entry of orderedEntries) {
        const { user, assistant } = mapSessionEntryToMessages(entry)
        built.push(user, assistant)
      }
      setMessages(built)
      sessionIdRef.current = detail.session.id
      setActiveSessionId(detail.session.id)
      setMobilePanelOpen(false)
    } catch (err) {
      setHistoryError({
        session,
        message: err instanceof Error ? err.message : 'No se pudo cargar esta conversación.',
      })
    } finally {
      setHistoryLoading(false)
    }
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
        setActiveSessionId(event.sessionId)
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

    // Refresco único, recién acá (no evento a evento): cubre tanto una
    // conversación recién creada por el servidor (todavía invisible en el
    // panel) como el contador de mensajes de una ya existente, que esta
    // pregunta acaba de desactualizar.
    if (sessionIdRef.current) {
      loadSessions(debouncedSearch, { silent: true })
    }
  }

  function startNewConversation() {
    // Solo se suelta el id y se limpia la vista. Lo ya escrito en
    // `tyto_query_log` no se toca: es auditoría, no historial de chat.
    abortRef.current?.abort()
    sessionIdRef.current = null
    setActiveSessionId(null)
    setMessages([])
    setSending(false)
    setHistoryError(null)
  }

  const conversationsPanelProps = {
    sessions,
    loading: sessionsLoading,
    error: sessionsError,
    onRetry: () => loadSessions(debouncedSearch),
    searchValue: searchInput,
    onSearchChange: setSearchInput,
    activeSessionId,
    pendingIds: pendingSessionIds,
    actionError,
    onDismissActionError: () => setActionError(null),
    onSelect: resumeSession,
    onRename: renameSession,
    onTogglePin: togglePin,
    onDelete: deleteSession,
  }

  return (
    <div className="flex h-full min-h-0 flex-col" data-module="arrayan">
      <header className="flex flex-shrink-0 items-center gap-3.5 border-b border-line px-6 py-5">
        <TytoHeaderAvatar />
        <div className="min-w-0 flex-1">
          <h1 className="text-h2 text-ink-900">Tyto</h1>
          <p className="mt-0.5 truncate text-[12.5px] text-ink-400">
            Solo consulta la red documental aprobada · cita fuente, versión y estado
          </p>
        </div>
        <button
          type="button"
          onClick={() => setMobilePanelOpen(true)}
          className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[12.5px] font-bold text-ink-700 transition-colors hover:bg-ink-50 lg:hidden"
        >
          <History size={14} aria-hidden="true" />
          Mis conversaciones
        </button>
        {/*
          Corta el hilo: la próxima pregunta abre una conversación nueva en vez
          de colgarse de la anterior. Sin esto, todo lo que alguien pregunte en
          el día queda en una sola sesión y el historial no distingue temas.
        */}
        <button
          type="button"
          onClick={startNewConversation}
          disabled={sending || historyLoading || messages.length === 0}
          className="flex-shrink-0 rounded-lg border border-line px-3 py-2 text-[12.5px] font-bold text-ink-700 transition-colors hover:bg-ink-50 disabled:opacity-40"
        >
          Nueva conversación
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Panel de conversaciones — desktop: columna fija; mobile: drawer. */}
        <aside
          aria-label="Mis conversaciones"
          className="hidden w-[260px] flex-shrink-0 flex-col overflow-hidden border-r border-line bg-surface lg:flex"
        >
          <TytoConversationsPanel {...conversationsPanelProps} className="h-full" />
        </aside>

        {/*
          Montado solo mientras está abierto: a diferencia del drawer de navegación
          del shell (que anima con transform y queda siempre en el DOM), acá adentro
          hay inputs y botones — dejarlos montados fuera de pantalla los deja
          alcanzables por teclado/lector de pantalla aunque no se vean, y además
          duplica ids con el panel de escritorio. Se pierde la animación de salida,
          se gana que "cerrado" signifique cerrado de verdad.
        */}
        {mobilePanelOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-ink-900/40 lg:hidden"
              onClick={() => setMobilePanelOpen(false)}
              aria-hidden="true"
            />
            <div
              className="animate-in fixed inset-y-0 left-0 z-50 flex w-[300px] max-w-[85vw] flex-col bg-surface shadow-modal lg:hidden"
              role="dialog"
              aria-modal="true"
              aria-label="Mis conversaciones"
            >
              <div className="flex flex-shrink-0 items-center justify-between border-b border-line px-3 py-3">
                <span className="text-[13px] font-extrabold text-ink-900">Mis conversaciones</span>
                <button
                  type="button"
                  onClick={() => setMobilePanelOpen(false)}
                  aria-label="Cerrar panel de conversaciones"
                  className="grid h-8 w-8 place-items-center rounded-md text-ink-500 hover:bg-ink-100 hover:text-ink-800"
                >
                  <X size={16} aria-hidden="true" />
                </button>
              </div>
              <TytoConversationsPanel {...conversationsPanelProps} className="min-h-0 flex-1" />
            </div>
          </>
        )}

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
            {historyError && (
              <div className="mx-auto mb-4 flex max-w-[820px] items-start gap-2.5 rounded-lg border border-danger-bd bg-danger-bg px-3.5 py-3">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0 text-danger" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-semibold text-danger">{historyError.message}</p>
                  <button
                    type="button"
                    onClick={() => resumeSession(historyError.session)}
                    className="mt-2 text-[12px] font-bold text-ink-700 underline underline-offset-2"
                  >
                    Reintentar
                  </button>
                </div>
              </div>
            )}

            {historyLoading ? (
              <TytoHistorySkeleton />
            ) : messages.length === 0 ? (
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

          <TytoComposer disabled={sending || historyLoading} onSubmit={ask} />
        </div>

        <TytoSourcesPanel result={lastAnsweredResult} />
      </div>
    </div>
  )
}
