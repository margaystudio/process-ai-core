'use client'

// app/consultar/page.tsx
// La superficie de consulta de Tyto para quien trabaja en el piso: una caja
// para preguntar, no una app de documentación. Es la pantalla principal de
// quien no tiene `documents.edit` ni `documents.approve` (ver app/page.tsx);
// quien sí los tiene llega acá desde el ítem "Consultar" del menú si quiere.
//
// Comparte backend y contratos con /tyto (misma sesión, mismo streaming SSE,
// mismo historial personal) pero es una implementación de pantalla propia: acá
// no hay panel de fuentes ni hilo de dos columnas, hay una acción grande
// ("Ver el procedimiento") y un composer pensado para un pulgar con guante.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, History, RotateCcw, WifiOff } from 'lucide-react'
import {
  deleteTytoSession,
  getTytoSession,
  getTytoSessions,
  getTytoSuggestions,
  streamTytoQuery,
  updateTytoSession,
  type TytoSessionSummary,
  type TytoStreamEvent,
  type TytoSuggestion,
} from '@/lib/api'
import { mapSessionEntryToMessages, sortTytoSessions, useDebouncedValue } from '@/lib/tytoHistory'
import { isNetworkError, NETWORK_ERROR_MESSAGE } from '@/lib/networkError'
import { TytoUserBubble } from '@/components/tyto/TytoMessageBubble'
import { TytoConsultarAnswer } from '@/components/tyto/TytoConsultarAnswer'
import { TytoConsultarComposer } from '@/components/tyto/TytoConsultarComposer'
import { TytoSuggestionChips } from '@/components/tyto/TytoSuggestionChips'
import { TytoHistorySheet } from '@/components/tyto/TytoHistorySheet'
import type { TytoAssistantMessage, TytoMessage } from '@/components/tyto/types'

function TytoHeaderAvatar() {
  return (
    <span
      className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-[12px] bg-indigo text-white"
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={20} height={20} fill="none" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="9" opacity={0.5} />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </span>
  )
}

export default function ConsultarPage() {
  const [messages, setMessages] = useState<TytoMessage[]>([])
  const [sending, setSending] = useState(false)
  const idRef = useRef(0)
  const sessionIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const threadEndRef = useRef<HTMLDivElement | null>(null)
  const pendingTokensRef = useRef('')
  const flushTimerRef = useRef<number | null>(null)

  // ── Sugerencias ("no sé qué preguntar") ─────────────────────────────────
  const [suggestions, setSuggestions] = useState<TytoSuggestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    getTytoSuggestions(6)
      .then((data) => {
        if (!cancelled) setSuggestions(data)
      })
      .catch(() => {
        // Sugerencias son un accesorio, no algo crítico: si falla (sin red,
        // 500), la pantalla no muestra un banner de error — cae al mismo
        // texto de ayuda que un workspace nuevo sin preguntas todavía.
        if (!cancelled) setSuggestions([])
      })
      .finally(() => {
        if (!cancelled) setSuggestionsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // ── "Lo que pregunté" ────────────────────────────────────────────────────
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<TytoSessionSummary[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const debouncedSearch = useDebouncedValue(searchInput, 300)
  const [pendingSessionIds, setPendingSessionIds] = useState<Set<string>>(new Set())
  const [actionError, setActionError] = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<{ session: TytoSessionSummary; message: string } | null>(
    null
  )
  const [historyOpen, setHistoryOpen] = useState(false)

  const loadSessions = useCallback(async (q: string, opts?: { silent?: boolean }) => {
    if (!opts?.silent) setSessionsLoading(true)
    setSessionsError(null)
    try {
      const data = await getTytoSessions(q || undefined)
      setSessions(data)
    } catch (err) {
      setSessionsError(
        isNetworkError(err)
          ? NETWORK_ERROR_MESSAGE
          : err instanceof Error
          ? err.message
          : 'No se pudieron cargar tus consultas.'
      )
    } finally {
      if (!opts?.silent) setSessionsLoading(false)
    }
  }, [])

  useEffect(() => {
    // Solo hace falta traer la lista una vez que se abre "Lo que pregunté" (y
    // al retipear la búsqueda mientras sigue abierta) — nadie entra a /consultar
    // a mirar su historial, así que no vale gastar el primer request en eso.
    if (!historyOpen) return
    loadSessions(debouncedSearch)
  }, [historyOpen, debouncedSearch, loadSessions])

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
    setSessions((prev) => sortTytoSessions(prev.map((s) => (s.id === session.id ? { ...s, title } : s))))
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
        setActionError(err instanceof Error ? err.message : 'No se pudo anclar/desanclar la conversación.')
      }
    })
  }

  async function deleteSession(session: TytoSessionSummary) {
    const previous = sessions
    await withPendingAction(session.id, async () => {
      try {
        await deleteTytoSession(session.id)
        setSessions((prev) => prev.filter((s) => s.id !== session.id))
        if (sessionIdRef.current === session.id) startNewConversation()
      } catch (err) {
        setSessions(previous)
        setActionError(err instanceof Error ? err.message : 'No se pudo eliminar la conversación.')
      }
    })
  }

  async function resumeSession(session: TytoSessionSummary) {
    abortRef.current?.abort()
    setSending(false)
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const detail = await getTytoSession(session.id)
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
      setHistoryOpen(false)
    } catch (err) {
      setHistoryError({
        session,
        message: isNetworkError(err)
          ? NETWORK_ERROR_MESSAGE
          : err instanceof Error
          ? err.message
          : 'No se pudo cargar esta conversación.',
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
        prev.map((m) => (m.id === assistantId && m.role === 'assistant' ? { ...m, text: m.text + chunk } : m))
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
        sessionIdRef.current = event.sessionId
        setActiveSessionId(event.sessionId)
        return
      }
      if (event.type === 'token') {
        pendingTokensRef.current += event.text
        if (flushTimerRef.current === null) {
          flushTimerRef.current = window.setTimeout(flushTokens, 50)
        }
        return
      }
      if (event.type === 'result') {
        clearPendingTokens()
        const searchDegraded = Boolean(event.data.search_degraded)
        if (event.data.answered) {
          patchAssistant({ status: 'answered', text: event.data.answer, result: event.data, searchDegraded })
        } else {
          patchAssistant({
            status: 'refused',
            text:
              event.data.refusal_reason ||
              'No encontré documentación aprobada suficiente para responder con confianza.',
            searchDegraded,
          })
        }
        return
      }
      clearPendingTokens()
      patchAssistant({ status: 'error', errorDetail: event.detail })
    }

    try {
      await streamTytoQuery(question, handleEvent, controller.signal, sessionIdRef.current)
      // Si el stream se cortó sin `result`, mostrar lo acumulado igual: la
      // última respuesta visible no se borra por un corte de conexión.
      flushTokens()
    } catch (err) {
      clearPendingTokens()
      patchAssistant({
        status: 'error',
        errorDetail: isNetworkError(err)
          ? NETWORK_ERROR_MESSAGE
          : err instanceof Error
          ? err.message
          : 'No se pudo conectar con Tyto.',
      })
    } finally {
      setSending(false)
      abortRef.current = null
    }
  }

  function startNewConversation() {
    abortRef.current?.abort()
    sessionIdRef.current = null
    setActiveSessionId(null)
    setMessages([])
    setSending(false)
    setHistoryError(null)
  }

  // Última pregunta que terminó en error de red — mostrada arriba del hilo
  // para que quede clarísimo que fue la conexión, no Tyto, sin duplicar el
  // aviso dentro de cada burbuja (que ya tiene su propio "Reintentar").
  const lastNetworkIssue = useMemo(() => {
    const last = messages[messages.length - 1]
    if (last?.role === 'assistant' && last.status === 'error' && last.errorDetail === NETWORK_ERROR_MESSAGE) {
      return last
    }
    return null
  }, [messages])

  return (
    <div className="flex h-full min-h-0 flex-col" data-module="arrayan">
      <header className="flex flex-shrink-0 items-center gap-3 border-b border-line bg-surface px-4 py-3.5 sm:px-6">
        <TytoHeaderAvatar />
        <div className="min-w-0 flex-1">
          <h1 className="text-h3 text-ink-900 sm:text-h2">Tyto</h1>
          <p className="hidden truncate text-[12px] text-ink-600 sm:block">
            Solo responde con documentación aprobada
          </p>
        </div>
        <button
          type="button"
          onClick={() => setHistoryOpen(true)}
          aria-label="Lo que pregunté"
          title="Lo que pregunté"
          className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-lg border border-line text-ink-700 transition-colors hover:bg-ink-100 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring"
        >
          <History size={19} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={startNewConversation}
          disabled={sending || historyLoading || messages.length === 0}
          aria-label="Nueva conversación"
          title="Nueva conversación"
          className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-lg border border-line text-ink-700 transition-colors hover:bg-ink-100 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring disabled:cursor-not-allowed disabled:opacity-40"
        >
          <RotateCcw size={18} aria-hidden="true" />
        </button>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto flex max-w-[640px] flex-col gap-4">
          {lastNetworkIssue && (
            <div
              role="alert"
              className="flex items-start gap-2.5 rounded-lg border border-danger-bd bg-danger-bg px-3.5 py-3"
            >
              <WifiOff size={16} className="mt-0.5 flex-shrink-0 text-danger" aria-hidden="true" />
              <p className="text-[13px] font-semibold text-danger">{NETWORK_ERROR_MESSAGE}</p>
            </div>
          )}

          {historyError && (
            <div className="flex items-start gap-2.5 rounded-lg border border-danger-bd bg-danger-bg px-3.5 py-3">
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
            <div className="flex flex-col gap-2.5" aria-hidden="true">
              <div className="ml-auto h-9 w-2/5 animate-pulse rounded-[14px_14px_4px_14px] bg-ink-100" />
              <div className="h-28 w-full animate-pulse rounded-xl bg-ink-100" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center gap-6 pt-4 text-center sm:pt-8">
              <div>
                <h2 className="text-h2 text-ink-900">¿Qué necesitás saber?</h2>
                <p className="mt-1.5 text-body text-ink-600">
                  Preguntale a Tyto sobre cualquier procedimiento aprobado.
                </p>
              </div>
              <TytoSuggestionChips suggestions={suggestions} loading={suggestionsLoading} onAsk={ask} />
            </div>
          ) : (
            <div>
              {messages.map((m) =>
                m.role === 'user' ? (
                  <TytoUserBubble key={m.id} message={m} />
                ) : (
                  <div key={m.id} className="mb-6">
                    <TytoConsultarAnswer message={m} onRetry={ask} />
                  </div>
                )
              )}
            </div>
          )}
          <div ref={threadEndRef} />
        </div>
      </main>

      <TytoConsultarComposer disabled={sending || historyLoading} onSubmit={ask} />

      <TytoHistorySheet
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        sessions={sessions}
        loading={sessionsLoading}
        error={sessionsError}
        onRetry={() => loadSessions(debouncedSearch)}
        searchValue={searchInput}
        onSearchChange={setSearchInput}
        activeSessionId={activeSessionId}
        pendingIds={pendingSessionIds}
        actionError={actionError}
        onDismissActionError={() => setActionError(null)}
        onSelect={resumeSession}
        onRename={renameSession}
        onTogglePin={togglePin}
        onDelete={deleteSession}
      />
    </div>
  )
}
