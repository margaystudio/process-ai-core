'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createWorkspace, WorkspaceCreateRequest, addUserToWorkspace } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserId } from '@/hooks/useUserId'

export default function OnboardingPage() {
  const router = useRouter()
  const userId = useUserId()
  const { refreshWorkspaces } = useWorkspace()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [country, setCountry] = useState('UY')
  const [businessType, setBusinessType] = useState('')
  const [languageStyle, setLanguageStyle] = useState('es_uy_formal')
  const [defaultAudience, setDefaultAudience] = useState('operativo')

  const handleSlugChange = (value: string) => {
    // Generar slug automáticamente desde el nombre
    const autoSlug = value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // Eliminar acentos
      .replace(/[^a-z0-9]+/g, '-') // Reemplazar espacios y caracteres especiales con guiones
      .replace(/^-+|-+$/g, '') // Eliminar guiones al inicio y final
    setSlug(autoSlug)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !slug.trim()) {
      setError('El nombre y el slug son requeridos')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const request: WorkspaceCreateRequest = {
        name: name.trim(),
        slug: slug.trim(),
        country,
        business_type: businessType || undefined,
        language_style: languageStyle,
        default_audience: defaultAudience,
      }

      const workspace = await createWorkspace(request, userId)
      
      // Si hay un usuario, asociarlo al workspace como owner
      if (userId && workspace.id) {
        try {
          await addUserToWorkspace(userId, workspace.id, 'owner')
        } catch (err) {
          console.error('Error agregando usuario al workspace:', err)
          // Continuar aunque falle, el workspace ya está creado
        }
      }

      // Refrescar workspaces y redirigir
      await refreshWorkspaces()
      router.push('/workspace')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear workspace')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-lg shadow-sm p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Bienvenido a Process AI
          </h1>
          <p className="text-gray-600 mb-8">
            Para comenzar, necesitas crear o unirte a un espacio de trabajo (organización/cliente).
          </p>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Nombre del Espacio de Trabajo *
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => {
                  setName(e.target.value)
                  handleSlugChange(e.target.value)
                }}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ej: Mi Empresa"
              />
            </div>

            <div>
              <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-2">
                Identificador (URL) *
              </label>
              <input
                id="slug"
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                pattern="[a-z0-9-]+"
                className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="mi-empresa"
              />
              <p className="mt-1 text-xs text-gray-500">
                Solo letras minúsculas, números y guiones. Se genera automáticamente desde el nombre.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-2">
                  País
                </label>
                <select
                  id="country"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="UY">Uruguay</option>
                  <option value="AR">Argentina</option>
                  <option value="BR">Brasil</option>
                  <option value="CL">Chile</option>
                  <option value="CO">Colombia</option>
                  <option value="MX">México</option>
                  <option value="ES">España</option>
                </select>
              </div>

              <div>
                <label htmlFor="languageStyle" className="block text-sm font-medium text-gray-700 mb-2">
                  Estilo de Idioma
                </label>
                <select
                  id="languageStyle"
                  value={languageStyle}
                  onChange={(e) => setLanguageStyle(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="es_uy_formal">Español UY Formal</option>
                  <option value="es_uy_informal">Español UY Informal</option>
                  <option value="es_ar_formal">Español AR Formal</option>
                  <option value="es_mx_formal">Español MX Formal</option>
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="businessType" className="block text-sm font-medium text-gray-700 mb-2">
                Tipo de Negocio (opcional)
              </label>
              <input
                id="businessType"
                type="text"
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ej: Retail, Manufactura, Servicios"
              />
            </div>

            <div>
              <label htmlFor="defaultAudience" className="block text-sm font-medium text-gray-700 mb-2">
                Audiencia por Defecto
              </label>
              <select
                id="defaultAudience"
                value={defaultAudience}
                onChange={(e) => setDefaultAudience(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="operativo">Operativo</option>
                <option value="gestion">Gestión</option>
              </select>
            </div>

            <div className="pt-4 border-t">
              <button
                type="submit"
                disabled={loading || !name.trim() || !slug.trim()}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {loading ? 'Creando...' : 'Crear Espacio de Trabajo'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

