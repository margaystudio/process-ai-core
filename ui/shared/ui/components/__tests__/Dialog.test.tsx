import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Dialog } from '../Dialog'

describe('Dialog', () => {
  it('renderiza role="dialog" con aria-modal cuando open=true', () => {
    render(
      <Dialog open onClose={() => {}} title="Confirmar">
        <p>Contenido</p>
      </Dialog>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    // Título enlazado por aria-labelledby.
    expect(dialog).toHaveAttribute('aria-labelledby')
    expect(screen.getByRole('heading', { name: 'Confirmar' })).toBeInTheDocument()
  })

  it('no renderiza nada cuando open=false', () => {
    render(
      <Dialog open={false} onClose={() => {}} title="Confirmar">
        <p>Contenido</p>
      </Dialog>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('cierra con Esc (llama onClose)', () => {
    const onClose = vi.fn()
    render(
      <Dialog open onClose={onClose} title="Confirmar">
        <p>Contenido</p>
      </Dialog>,
    )
    // El listener de Escape está en document; el evento burbujea desde el dialog.
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('hace focus trap: Tab desde el último foco vuelve al primero', () => {
    render(
      <Dialog open onClose={() => {}} aria-labelledby="h">
        <h2 id="h">T</h2>
        <button>Primero</button>
        <button>Último</button>
      </Dialog>,
    )
    const first = screen.getByRole('button', { name: 'Primero' })
    const last = screen.getByRole('button', { name: 'Último' })

    last.focus()
    expect(last).toHaveFocus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(first).toHaveFocus()
  })

  it('focus trap inverso: Shift+Tab desde el primero va al último', () => {
    render(
      <Dialog open onClose={() => {}} aria-labelledby="h">
        <h2 id="h">T</h2>
        <button>Primero</button>
        <button>Último</button>
      </Dialog>,
    )
    const first = screen.getByRole('button', { name: 'Primero' })
    const last = screen.getByRole('button', { name: 'Último' })

    first.focus()
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(last).toHaveFocus()
  })
})
