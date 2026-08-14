import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useTytoVoiceRecorder, formatVoiceSeconds } from '@/hooks/useTytoVoiceRecorder'
import { transcribeTytoAudio } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  transcribeTytoAudio: vi.fn(),
}))

/** Doble mínimo de MediaRecorder: arranca/para y dispara los mismos eventos
 *  (`ondataavailable`, `onstop`) que el hook escucha en el navegador real. */
class FakeMediaRecorder {
  static isTypeSupported = vi.fn(() => true)
  state: 'inactive' | 'recording' = 'inactive'
  mimeType: string
  ondataavailable: ((e: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null

  constructor(
    public stream: MediaStream,
    options?: { mimeType?: string }
  ) {
    this.mimeType = options?.mimeType ?? 'audio/webm'
  }

  start() {
    this.state = 'recording'
  }

  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['audio'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

function fakeStream(): MediaStream {
  const track = { stop: vi.fn() }
  return { getTracks: () => [track] } as unknown as MediaStream
}

function installSupportedBrowser() {
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder)
  const getUserMedia = vi.fn().mockResolvedValue(fakeStream())
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  return { getUserMedia }
}

describe('formatVoiceSeconds', () => {
  it('formatea m:ss con segundos en dos dígitos', () => {
    expect(formatVoiceSeconds(0)).toBe('0:00')
    expect(formatVoiceSeconds(9)).toBe('0:09')
    expect(formatVoiceSeconds(65)).toBe('1:05')
  })
})

describe('useTytoVoiceRecorder', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sin MediaRecorder/getUserMedia en el navegador, arranca "unsupported" (el botón no debe pintarse)', () => {
    vi.stubGlobal('navigator', {})
    const { result } = renderHook(() => useTytoVoiceRecorder(vi.fn()))
    expect(result.current.supported).toBe(false)
    expect(result.current.status).toBe('unsupported')
  })

  it('graba, transcribe y entrega el texto SIN preguntar sola', async () => {
    installSupportedBrowser()
    vi.mocked(transcribeTytoAudio).mockResolvedValue({ text: '¿Cómo cierro la caja?' })
    const onTranscribed = vi.fn()
    const { result } = renderHook(() => useTytoVoiceRecorder(onTranscribed))

    expect(result.current.status).toBe('idle')

    await act(async () => {
      result.current.start()
    })
    await waitFor(() => expect(result.current.status).toBe('recording'))

    act(() => {
      result.current.stop()
    })

    await waitFor(() => expect(result.current.status).toBe('idle'))
    expect(transcribeTytoAudio).toHaveBeenCalledTimes(1)
    // Se sube un File (no un Blob pelado): el backend espera multipart `file`.
    expect(transcribeTytoAudio.mock.calls[0][0]).toBeInstanceOf(File)
    // El texto llega listo para poblar el campo — el hook nunca dispara la pregunta.
    expect(onTranscribed).toHaveBeenCalledWith('¿Cómo cierro la caja?')
  })

  it('cancelar descarta la grabación: no transcribe y no llama a onTranscribed', async () => {
    installSupportedBrowser()
    const onTranscribed = vi.fn()
    const { result } = renderHook(() => useTytoVoiceRecorder(onTranscribed))

    await act(async () => {
      result.current.start()
    })
    await waitFor(() => expect(result.current.status).toBe('recording'))

    act(() => {
      result.current.cancel()
    })

    await waitFor(() => expect(result.current.status).toBe('idle'))
    expect(transcribeTytoAudio).not.toHaveBeenCalled()
    expect(onTranscribed).not.toHaveBeenCalled()
  })

  it('permiso de micrófono denegado deja un estado propio, distinto de un error genérico', async () => {
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder)
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException('nope', 'NotAllowedError'))
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })

    const { result } = renderHook(() => useTytoVoiceRecorder(vi.fn()))

    await act(async () => {
      result.current.start()
    })

    await waitFor(() => expect(result.current.status).toBe('permission-denied'))
  })

  it('si el navegador no tiene micrófono disponible (NotFoundError), es un error genérico y no "unsupported"', async () => {
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder)
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException('nope', 'NotFoundError'))
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })

    const { result } = renderHook(() => useTytoVoiceRecorder(vi.fn()))

    await act(async () => {
      result.current.start()
    })

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.errorMessage).toMatch(/micrófono/i)
  })

  it('si la transcripción falla por red, el mensaje es el de "sin conexión", no el genérico', async () => {
    installSupportedBrowser()
    vi.mocked(transcribeTytoAudio).mockRejectedValue(new TypeError('Failed to fetch'))
    const { result } = renderHook(() => useTytoVoiceRecorder(vi.fn()))

    await act(async () => {
      result.current.start()
    })
    await waitFor(() => expect(result.current.status).toBe('recording'))

    act(() => {
      result.current.stop()
    })

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.errorMessage).toMatch(/no hay conexión/i)
  })

  it('dismissError vuelve a "idle" y limpia el mensaje', async () => {
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder as unknown as typeof MediaRecorder)
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException('nope', 'NotFoundError'))
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })

    const { result } = renderHook(() => useTytoVoiceRecorder(vi.fn()))
    await act(async () => {
      result.current.start()
    })
    await waitFor(() => expect(result.current.status).toBe('error'))

    act(() => {
      result.current.dismissError()
    })
    expect(result.current.status).toBe('idle')
    expect(result.current.errorMessage).toBeNull()
  })
})
