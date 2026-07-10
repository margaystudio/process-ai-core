// Setup global de vitest para tests de DOM.
// Agrega los matchers de jest-dom (toBeInTheDocument, toHaveAttribute, etc.)
// y limpia el DOM entre tests.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
