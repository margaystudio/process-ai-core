import { describe, it, expect } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { Tabs, TabsContent, type TabItem } from '../Tabs'

const ITEMS: TabItem[] = [
  { value: 'general', label: 'General' },
  { value: 'usuarios', label: 'Usuarios' },
  { value: 'roles', label: 'Roles' },
]

/** Wrapper controlado: mantiene el estado para que selección/foco reflejen la realidad. */
function ControlledTabs({ initial = 'general' }: { initial?: string }) {
  const [value, setValue] = useState(initial)
  return (
    <Tabs id="settings" value={value} onValueChange={setValue} items={ITEMS}>
      <TabsContent id="settings" value="general" current={value}>
        Panel General
      </TabsContent>
      <TabsContent id="settings" value="usuarios" current={value}>
        Panel Usuarios
      </TabsContent>
      <TabsContent id="settings" value="roles" current={value}>
        Panel Roles
      </TabsContent>
    </Tabs>
  )
}

describe('Tabs', () => {
  it('renderiza tablist con tabs y un tabpanel', () => {
    render(<ControlledTabs />)
    expect(screen.getByRole('tablist')).toBeInTheDocument()
    expect(screen.getAllByRole('tab')).toHaveLength(3)
    // Solo el panel activo es visible (los otros tienen hidden).
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Panel General')
  })

  it('aria-selected marca el tab activo y aria-controls encadena al panel', () => {
    render(<ControlledTabs />)
    const [general, usuarios] = screen.getAllByRole('tab')
    expect(general).toHaveAttribute('aria-selected', 'true')
    expect(usuarios).toHaveAttribute('aria-selected', 'false')
    // aria-controls apunta al id del panel correspondiente.
    expect(general).toHaveAttribute('aria-controls', 'settings-panel-general')
  })

  it('ArrowRight mueve la selección (y el foco) al siguiente tab', () => {
    render(<ControlledTabs />)
    const tabs = screen.getAllByRole('tab')
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' })
    expect(screen.getAllByRole('tab')[1]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getAllByRole('tab')[1]).toHaveFocus()
  })

  it('ArrowLeft cicla al último desde el primero', () => {
    render(<ControlledTabs />)
    const tabs = screen.getAllByRole('tab')
    fireEvent.keyDown(tabs[0], { key: 'ArrowLeft' })
    expect(screen.getAllByRole('tab')[2]).toHaveAttribute('aria-selected', 'true')
  })

  it('Home y End van al primero y al último', () => {
    render(<ControlledTabs initial="usuarios" />)
    let tabs = screen.getAllByRole('tab')
    fireEvent.keyDown(tabs[1], { key: 'End' })
    expect(screen.getAllByRole('tab')[2]).toHaveAttribute('aria-selected', 'true')

    tabs = screen.getAllByRole('tab')
    fireEvent.keyDown(tabs[2], { key: 'Home' })
    expect(screen.getAllByRole('tab')[0]).toHaveAttribute('aria-selected', 'true')
  })

  it('el tab activo tiene tabIndex 0 y los inactivos -1 (roving focus)', () => {
    render(<ControlledTabs />)
    const [general, usuarios, roles] = screen.getAllByRole('tab')
    expect(general).toHaveAttribute('tabindex', '0')
    expect(usuarios).toHaveAttribute('tabindex', '-1')
    expect(roles).toHaveAttribute('tabindex', '-1')
  })
})
