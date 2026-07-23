// components/tyto/TytoComposer.tsx
// Input del hilo. Se deshabilita mientras Tyto está respondiendo (estado enviando).
'use client'

import { useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'

export function TytoComposer({
  disabled,
  onSubmit,
}: {
  disabled: boolean
  onSubmit: (question: string) => void
}) {
  const [value, setValue] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex-shrink-0 border-t border-line bg-surface px-6 py-4">
      <div className="mx-auto flex max-w-[820px] items-center gap-2 rounded-[13px] border-[1.5px] border-line bg-surface-app px-4 py-1.5">
        <label htmlFor="tyto-question" className="sr-only">
          Pregunta para Tyto
        </label>
        <input
          id="tyto-question"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={disabled}
          placeholder="Preguntá sobre cualquier procedimiento…"
          className="h-10 min-w-0 flex-1 bg-transparent text-sm text-ink-800 placeholder:text-ink-400 outline-none disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label="Enviar pregunta"
          className="grid h-10 w-10 flex-shrink-0 place-items-center rounded-[10px] bg-action text-action-on transition-colors hover:bg-action-hover focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-action-ring disabled:cursor-not-allowed disabled:bg-ink-150 disabled:text-ink-400"
        >
          <Send size={17} aria-hidden="true" />
        </button>
      </div>
    </form>
  )
}
