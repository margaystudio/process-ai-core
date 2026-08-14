// Setup global de vitest para tests de DOM.
// Agrega los matchers de jest-dom (toBeInTheDocument, toHaveAttribute, etc.)
// y limpia el DOM entre tests.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(async () => {
  cleanup()
  // `useCapabilities` guarda un store compartido a nivel de módulo (a propósito,
  // ver el comentario en el hook) para que `refreshCapabilities()` notifique a
  // todos los consumidores montados. Eso lo hace sobrevivir entre los `it()` de
  // un mismo archivo si no se resetea acá: el segundo test heredaría las
  // capabilities cacheadas del primero aunque cambie el mock de getMyCapabilities.
  //
  // Import DINÁMICO a propósito (no un `import` estático arriba del archivo):
  // si este setup importara `hooks/useCapabilities` de forma estática, lo
  // evaluaría ANTES que los `vi.mock('@/contexts/WorkspaceContext', ...)` de
  // cada test (que se hoistean al tope de SU propio archivo, no del setup) —
  // el hook quedaría con el `useWorkspace` real cacheado y los mocks de los
  // tests dejarían de tener efecto. Al diferir el import a este callback, para
  // entonces el módulo ya se resolvió (si corresponde) contra los mocks del
  // test en curso.
  const { __resetCapabilitiesStoreForTests } = await import('./hooks/useCapabilities')
  __resetCapabilitiesStoreForTests()
})
