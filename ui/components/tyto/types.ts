// components/tyto/types.ts
// Tipos del hilo de chat de Tyto (Fase B). El contrato de datos (TytoQueryResult,
// TytoSource, TytoSegment) vive en lib/api.ts — acá solo el estado de UI del hilo.
import type { TytoQueryResult } from '@/lib/api'

export type TytoAssistantStatus = 'streaming' | 'answered' | 'refused' | 'error'

export interface TytoUserMessage {
  id: string
  role: 'user'
  question: string
}

export interface TytoAssistantMessage {
  id: string
  role: 'assistant'
  /** Pregunta que originó esta respuesta — permite reintentar sin perder contexto. */
  question: string
  status: TytoAssistantStatus
  /**
   * Texto a mostrar: mientras streamea es la prosa formándose (con marcadores
   * [Sn] inline); en `answered` es `result.answer`; en `refused` es el
   * `refusal_reason`. En `error` no se usa (se muestra `errorDetail`).
   */
  text: string
  result?: TytoQueryResult
  errorDetail?: string
}

export type TytoMessage = TytoUserMessage | TytoAssistantMessage
