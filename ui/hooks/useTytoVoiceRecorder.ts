'use client'

// hooks/useTytoVoiceRecorder.ts
// Graba una pregunta por voz y la transcribe (`POST /tyto/transcribe`). Nunca
// pregunta sola: `onTranscribed` solo deja el texto en el campo — confirmar o
// corregir y enviar es de quien usa el hook (pantalla /consultar).
import { useCallback, useEffect, useRef, useState } from 'react'
import { transcribeTytoAudio } from '@/lib/api'
import { isNetworkError, NETWORK_ERROR_MESSAGE } from '@/lib/networkError'

export type TytoVoiceStatus =
  | 'unsupported'
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'transcribing'
  | 'permission-denied'
  | 'error'

export interface UseTytoVoiceRecorderResult {
  status: TytoVoiceStatus
  /** Segundos transcurridos desde que empezó a grabar (se resetea por grabación). */
  seconds: number
  errorMessage: string | null
  /** `false` en un navegador sin MediaRecorder/getUserMedia: quien consume el hook
   *  no debe pintar el botón de micrófono en absoluto (no uno roto). */
  supported: boolean
  start: () => void
  /** Corta la grabación y dispara la transcripción. */
  stop: () => void
  /** Corta y descarta: no se transcribe nada. */
  cancel: () => void
  dismissError: () => void
}

const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4',
  'audio/ogg;codecs=opus',
  'audio/ogg',
]

/** Mapeo laxo a las extensiones que acepta el backend (.webm .mp4 .m4a .mp3 .wav .ogg .aac). */
const EXT_BY_MIME_FRAGMENT: Array<[string, string]> = [
  ['webm', 'webm'],
  ['mp4', 'm4a'],
  ['ogg', 'ogg'],
  ['wav', 'wav'],
  ['mpeg', 'mp3'],
  ['aac', 'aac'],
]

function supportsRecording(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  )
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined' || typeof MediaRecorder.isTypeSupported !== 'function') {
    return undefined
  }
  return MIME_CANDIDATES.find((candidate) => {
    try {
      return MediaRecorder.isTypeSupported(candidate)
    } catch {
      return false
    }
  })
}

function extFromMime(mime: string): string {
  const match = EXT_BY_MIME_FRAGMENT.find(([fragment]) => mime.includes(fragment))
  return match ? match[1] : 'webm'
}

function isPermissionDenied(err: unknown): boolean {
  if (err instanceof DOMException) {
    return (
      err.name === 'NotAllowedError' ||
      err.name === 'PermissionDeniedError' ||
      err.name === 'SecurityError'
    )
  }
  return false
}

/** `m:ss`, igual que el resto de las grabaciones del sistema (evidencias). */
export function formatVoiceSeconds(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function useTytoVoiceRecorder(onTranscribed: (text: string) => void): UseTytoVoiceRecorderResult {
  const supported = supportsRecording()

  const [status, setStatus] = useState<TytoVoiceStatus>(supported ? 'idle' : 'unsupported')
  const [seconds, setSeconds] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const discardRef = useRef(false)
  const mountedRef = useRef(true)
  const onTranscribedRef = useRef(onTranscribed)
  onTranscribedRef.current = onTranscribed

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
  }, [])

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const transcribe = useCallback(async (blob: Blob, mime: string) => {
    if (mountedRef.current) setStatus('transcribing')
    try {
      const file = new File([blob], `pregunta.${extFromMime(mime)}`, { type: mime })
      const { text } = await transcribeTytoAudio(file)
      if (!mountedRef.current) return
      const trimmed = text.trim()
      setStatus('idle')
      if (trimmed) onTranscribedRef.current(trimmed)
    } catch (err) {
      if (!mountedRef.current) return
      setStatus('error')
      setErrorMessage(
        isNetworkError(err)
          ? NETWORK_ERROR_MESSAGE
          : err instanceof Error
          ? err.message
          : 'No se pudo transcribir el audio.'
      )
    }
  }, [])

  const start = useCallback(async () => {
    if (!supported) {
      setStatus('unsupported')
      return
    }
    setErrorMessage(null)
    discardRef.current = false
    setStatus('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      streamRef.current = stream
      chunksRef.current = []
      const mimeType = pickMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      recorderRef.current = recorder

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stopStream()
        clearTimer()
        if (discardRef.current) {
          discardRef.current = false
          if (mountedRef.current) setStatus('idle')
          return
        }
        const type = recorder.mimeType || mimeType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type })
        void transcribe(blob, type)
      }

      recorder.start()
      setSeconds(0)
      setStatus('recording')
      timerRef.current = setInterval(() => {
        setSeconds((s) => s + 1)
      }, 1000)
    } catch (err) {
      stopStream()
      if (!mountedRef.current) return
      if (isPermissionDenied(err)) {
        setStatus('permission-denied')
      } else {
        setStatus('error')
        setErrorMessage('No se pudo acceder al micrófono. Probá de nuevo o escribí la pregunta.')
      }
    }
  }, [clearTimer, stopStream, supported, transcribe])

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    }
  }, [])

  const cancel = useCallback(() => {
    discardRef.current = true
    clearTimer()
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
    } else {
      stopStream()
      setStatus('idle')
    }
  }, [clearTimer, stopStream])

  const dismissError = useCallback(() => {
    setStatus('idle')
    setErrorMessage(null)
  }, [])

  // Al desmontar (navegación fuera de /consultar a mitad de grabación): cortar
  // el micrófono de verdad. Sin esto el ícono de "usando el micrófono" del
  // navegador queda prendido en una pantalla que ya no se ve.
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      clearTimer()
      if (recorderRef.current?.state === 'recording') {
        discardRef.current = true
        recorderRef.current.stop()
      }
      stopStream()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { status, seconds, errorMessage, supported, start, stop, cancel, dismissError }
}
