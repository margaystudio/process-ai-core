import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Switch } from '../Switch'

describe('Switch', () => {
  it('renderiza con role="switch"', () => {
    render(<Switch checked={false} onCheckedChange={() => {}} aria-label="Notificaciones" />)
    expect(screen.getByRole('switch')).toBeInTheDocument()
  })

  it('aria-checked refleja el estado checked', () => {
    const { rerender } = render(
      <Switch checked={false} onCheckedChange={() => {}} aria-label="x" />,
    )
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'false')

    rerender(<Switch checked={true} onCheckedChange={() => {}} aria-label="x" />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
  })

  it('Space dispara onCheckedChange con el valor invertido', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onCheckedChange={onChange} aria-label="x" />)
    fireEvent.keyDown(screen.getByRole('switch'), { key: ' ' })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('Enter dispara onCheckedChange con el valor invertido', () => {
    const onChange = vi.fn()
    render(<Switch checked={true} onCheckedChange={onChange} aria-label="x" />)
    fireEvent.keyDown(screen.getByRole('switch'), { key: 'Enter' })
    expect(onChange).toHaveBeenCalledWith(false)
  })

  it('no dispara onCheckedChange cuando está disabled', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onCheckedChange={onChange} disabled aria-label="x" />)
    const sw = screen.getByRole('switch')
    fireEvent.keyDown(sw, { key: ' ' })
    fireEvent.click(sw)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('asocia el label visible al control', () => {
    render(<Switch id="notif" checked={false} onCheckedChange={() => {}} label="Recibir avisos" />)
    // El label visible existe y el switch es accesible por ese nombre.
    expect(screen.getByText('Recibir avisos')).toBeInTheDocument()
    expect(screen.getByRole('switch')).toHaveAttribute('id', 'notif')
  })
})
