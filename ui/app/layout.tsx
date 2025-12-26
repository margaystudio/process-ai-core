import type { Metadata } from 'next'
import './globals.css'
import Header from '@/components/layout/Header'
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'
import { LoadingProvider } from '@/contexts/LoadingContext'

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
      <body className="min-h-screen bg-gray-50">
        <LoadingProvider>
          <WorkspaceProvider>
            <Header />
            {children}
          </WorkspaceProvider>
        </LoadingProvider>
      </body>
    </html>
  )
}

