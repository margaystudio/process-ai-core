import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Process AI Core',
  description: 'Generación automática de documentación de procesos',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  )
}

