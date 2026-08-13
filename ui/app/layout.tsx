import type { Metadata } from 'next'
import './globals.css'
import './branding.css'
import { jakarta } from '@/shared/ui/fonts'
import ChromeShell from '@/components/layout/ChromeShell'
import BrandingFavicon from '@/components/layout/BrandingFavicon'
import { WorkspaceProvider } from '@/contexts/WorkspaceContext'
import { LoadingProvider } from '@/contexts/LoadingContext'

export const metadata: Metadata = {
  title: 'Process AI Core',
  description: 'Generación automática de documentación de procesos',
  // Default estático (antes de que `BrandingFavicon` hidrate y, si el workspace activo
  // tiene ícono propio, lo reemplace). Emblema del módulo (arrayán): fondo sólido del
  // acento + glifo blanco — el SVG plano no sirve para favicon, desaparece a 16px.
  icons: {
    icon: [
      { url: '/brand/modules/arrayan-favicon.svg', type: 'image/svg+xml' },
      { url: '/brand/favicon-32.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: '/brand/apple-icon.png',
  },
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
            <ChromeShell>{children}</ChromeShell>
          </WorkspaceProvider>
        </LoadingProvider>
      </body>
    </html>
  )
}

