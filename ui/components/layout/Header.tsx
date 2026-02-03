'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState, useRef, useEffect } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUser } from '@/hooks/useUser'
import { createClient } from '@/lib/supabase/client'

export default function Header() {
  const pathname = usePathname()
  const router = useRouter()
  const { workspaces, selectedWorkspaceId, setSelectedWorkspaceId, selectedWorkspace } = useWorkspace()
  const user = useUser()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  // Rutas públicas donde no se muestra el usuario ni la navegación completa
  const isPublicRoute = pathname?.startsWith('/login') || pathname?.startsWith('/auth')

  // Verificar si el usuario es superadmin (tiene un workspace de tipo "system")
  const isSuperadmin = workspaces.some(ws => ws.workspace_type === 'system')

  const isActive = (path: string) => {
    return pathname?.startsWith(path)
  }

  // Cerrar menú de usuario al hacer click fuera
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }

    if (userMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [userMenuOpen])

  // Cerrar sesión
  const handleSignOut = async () => {
    try {
      const supabase = createClient()
      await supabase.auth.signOut()
      localStorage.removeItem('local_user_id')
      router.push('/login')
    } catch (err) {
      console.error('Error cerrando sesión:', err)
    }
  }

  // Obtener iniciales del usuario para avatar
  const getUserInitials = () => {
    if (user?.name) {
      const parts = user.name.split(' ')
      if (parts.length >= 2) {
        return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
      }
      return user.name.substring(0, 2).toUpperCase()
    }
    if (user?.email) {
      return user.email.substring(0, 2).toUpperCase()
    }
    return 'U'
  }

  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo y título */}
          <div className="flex items-center">
            <Link href="/workspace" className="flex items-center space-x-3">
              <div className="flex-shrink-0 flex items-center">
                <img
                  src="/margay-logo.png"
                  alt="Margay Logo"
                  className="h-10 w-10 object-contain"
                  onError={(e) => {
                    // Fallback a SVG si la imagen no existe
                    const target = e.target as HTMLImageElement
                    target.style.display = 'none'
                    const fallback = target.nextElementSibling as HTMLElement
                    if (fallback) {
                      fallback.style.display = 'block'
                    }
                  }}
                />
                {/* Fallback SVG de margay si la imagen no existe */}
                <svg
                  className="h-10 w-10"
                  viewBox="0 0 100 100"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  style={{ display: 'none' }}
                >
                  {/* Cabeza del margay */}
                  <circle cx="50" cy="40" r="25" fill="#8B7355" stroke="#654321" strokeWidth="2"/>
                  {/* Orejas */}
                  <path d="M35 25 L30 15 L40 20 Z" fill="#8B7355" stroke="#654321" strokeWidth="1.5"/>
                  <path d="M65 25 L70 15 L60 20 Z" fill="#8B7355" stroke="#654321" strokeWidth="1.5"/>
                  {/* Ojos */}
                  <circle cx="43" cy="38" r="3" fill="#000"/>
                  <circle cx="57" cy="38" r="3" fill="#000"/>
                  {/* Nariz */}
                  <path d="M50 45 L48 50 L52 50 Z" fill="#000"/>
                  {/* Manchas características del margay */}
                  <ellipse cx="45" cy="50" rx="4" ry="6" fill="#654321" opacity="0.6"/>
                  <ellipse cx="55" cy="50" rx="4" ry="6" fill="#654321" opacity="0.6"/>
                  <ellipse cx="50" cy="60" rx="5" ry="3" fill="#654321" opacity="0.6"/>
                </svg>
              </div>
              <span className="text-2xl font-bold text-blue-600">Process AI</span>
            </Link>
          </div>

          {/* Navegación principal - Desktop (solo en rutas privadas) */}
          {!isPublicRoute && (
            <nav className="hidden md:flex items-center space-x-1">
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
              {isSuperadmin && (
                <Link
                  href="/clients"
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive('/clients')
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  Clientes
                </Link>
              )}
            </nav>
          )}

          {/* Selector de workspace, menú de usuario y menú móvil */}
          <div className="flex items-center space-x-4">
            {!isPublicRoute && workspaces.length > 0 && selectedWorkspaceId && (
              <div className="hidden lg:flex items-center space-x-2">
                <select
                  value={selectedWorkspaceId}
                  onChange={(e) => setSelectedWorkspaceId(e.target.value || null)}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                  title="Seleccionar espacio de trabajo"
                >
                  {workspaces.map((ws) => (
                    <option key={ws.id} value={ws.id}>
                      {ws.name}
                    </option>
                  ))}
                </select>
                <Link
                  href={`/workspace/${selectedWorkspaceId}/settings`}
                  className="p-1.5 text-gray-600 hover:text-blue-600 hover:bg-gray-100 rounded-md transition-colors"
                  title="Configuración del espacio de trabajo"
                >
                  <svg
                    className="h-5 w-5"
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </Link>
              </div>
            )}

            {/* Menú de usuario - Desktop (solo en rutas privadas) */}
            {!isPublicRoute && user && (
              <div className="hidden md:block relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-2 px-3 py-2 rounded-md hover:bg-gray-100 transition-colors"
                  aria-label="Menú de usuario"
                >
                  {user.avatarUrl ? (
                    <img
                      src={user.avatarUrl}
                      alt={user.name || user.email || 'Usuario'}
                      className="h-8 w-8 rounded-full"
                    />
                  ) : (
                    <div className="h-8 w-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
                      {getUserInitials()}
                    </div>
                  )}
                  <span className="text-sm font-medium text-gray-700 hidden lg:block">
                    {user.name || user.email || 'Usuario'}
                  </span>
                  <svg
                    className={`h-4 w-4 text-gray-500 transition-transform ${userMenuOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {/* Dropdown del menú de usuario */}
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50">
                    <div className="py-1">
                      <div className="px-4 py-3 border-b border-gray-200">
                        <p className="text-sm font-medium text-gray-900">
                          {user.name || 'Usuario'}
                        </p>
                        <p className="text-sm text-gray-500 truncate">
                          {user.email}
                        </p>
                      </div>
                      {selectedWorkspaceId && (
                        <Link
                          href={`/workspace/${selectedWorkspaceId}/settings`}
                          onClick={() => setUserMenuOpen(false)}
                          className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                        >
                          Configuración del espacio de trabajo
                        </Link>
                      )}
                      <button
                        onClick={handleSignOut}
                        className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
                      >
                        Cerrar sesión
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
            
            {/* Botón menú móvil (solo en rutas privadas) */}
            {!isPublicRoute && (
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
            )}
          </div>
        </div>

        {/* Menú móvil (solo en rutas privadas) */}
        {!isPublicRoute && mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 py-4">
            <nav className="flex flex-col space-y-1">
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
              {isSuperadmin && (
                <Link
                  href="/clients"
                  onClick={() => setMobileMenuOpen(false)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive('/clients')
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  Clientes
                </Link>
              )}
              {workspaces.length > 0 && selectedWorkspaceId && (
                <div className="px-4 py-2 space-y-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Espacio de trabajo
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
                  <Link
                    href={`/workspace/${selectedWorkspaceId}/settings`}
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  >
                    <svg
                      className="h-4 w-4"
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span>Configuración</span>
                  </Link>
                </div>
              )}
              {user && (
                <div className="px-4 py-3 border-t border-gray-200">
                  <div className="flex items-center space-x-3 mb-3">
                    {user.avatarUrl ? (
                      <img
                        src={user.avatarUrl}
                        alt={user.name || user.email || 'Usuario'}
                        className="h-10 w-10 rounded-full"
                      />
                    ) : (
                      <div className="h-10 w-10 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
                        {getUserInitials()}
                      </div>
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {user.name || 'Usuario'}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {user.email}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="w-full px-4 py-2 text-sm text-left text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  >
                    Cerrar sesión
                  </button>
                </div>
              )}
            </nav>
          </div>
        )}
      </div>
    </header>
  )
}

