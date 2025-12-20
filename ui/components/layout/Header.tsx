'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'

export default function Header() {
  const pathname = usePathname()
  const { workspaces, selectedWorkspaceId, setSelectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const isActive = (path: string) => {
    if (path === '/') {
      return pathname === '/'
    }
    return pathname?.startsWith(path)
  }

  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo y título */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center space-x-3">
              <div className="flex-shrink-0">
                <span className="text-2xl font-bold text-blue-600">Process AI</span>
              </div>
            </Link>
          </div>

          {/* Navegación principal - Desktop */}
          <nav className="hidden md:flex items-center space-x-1">
            <Link
              href="/"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/') && pathname === '/'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              Inicio
            </Link>
            <Link
              href="/workspace"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/workspace')
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              Documentos
            </Link>
            <Link
              href="/processes/new"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/processes')
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              Nuevo Proceso
            </Link>
            <Link
              href="/clients/new"
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive('/clients')
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              Nuevo Cliente
            </Link>
          </nav>

          {/* Selector de workspace y menú móvil */}
          <div className="flex items-center space-x-4">
            {workspaces.length > 0 && selectedWorkspaceId && (
              <div className="hidden lg:block">
                <select
                  value={selectedWorkspaceId}
                  onChange={(e) => setSelectedWorkspaceId(e.target.value || null)}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                  title="Seleccionar workspace"
                >
                  {workspaces.map((ws) => (
                    <option key={ws.id} value={ws.id}>
                      {ws.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            
            {/* Botón menú móvil */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-md text-gray-700 hover:bg-gray-100"
              aria-label="Toggle menu"
            >
              <svg
                className="h-6 w-6"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                {mobileMenuOpen ? (
                  <path d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Menú móvil */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 py-4">
            <nav className="flex flex-col space-y-1">
              <Link
                href="/"
                onClick={() => setMobileMenuOpen(false)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/') && pathname === '/'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                Inicio
              </Link>
              <Link
                href="/workspace"
                onClick={() => setMobileMenuOpen(false)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/workspace')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                Documentos
              </Link>
              <Link
                href="/processes/new"
                onClick={() => setMobileMenuOpen(false)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/processes')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                Nuevo Proceso
              </Link>
              <Link
                href="/clients/new"
                onClick={() => setMobileMenuOpen(false)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive('/clients')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                Nuevo Cliente
              </Link>
              {workspaces.length > 0 && selectedWorkspaceId && (
                <div className="px-4 py-2">
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Workspace
                  </label>
                  <select
                    value={selectedWorkspaceId}
                    onChange={(e) => setSelectedWorkspaceId(e.target.value || null)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                  >
                    {workspaces.map((ws) => (
                      <option key={ws.id} value={ws.id}>
                        {ws.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}

