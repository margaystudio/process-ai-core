import type { Metadata } from 'next'
import './globals.css'
import './branding.css'
import { jakarta } from '@/shared/ui/fonts'
import Header from '@/components/layout/Header'
import BrandingFavicon from '@/components/layout/BrandingFavicon'
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
    <html lang="es" className={jakarta.variable}>
      <body className="min-h-screen bg-ink-50 text-ink-800">
        <LoadingProvider>
          <WorkspaceProvider>
            <BrandingFavicon />
            <Header />
            {children}
          </WorkspaceProvider>
        </LoadingProvider>
      </body>
    </html>
  )
}

