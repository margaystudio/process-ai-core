import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Plugin React: transforma JSX/TSX de los componentes (el tsconfig usa jsx:preserve
  // para Next, así que el transform de tests lo maneja este plugin).
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  test: {
    // jsdom habilita render + DOM/ARIA para los primitivos del design system.
    // Los tests de lógica pura (lib/**) corren igual bajo jsdom.
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['lib/**/*.test.ts', 'shared/ui/**/*.test.tsx'],
  },
})
