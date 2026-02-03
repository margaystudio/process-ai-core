'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createB2BWorkspace, listAllWorkspaces, WorkspaceResponse } from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import { createClient } from '@/lib/supabase/client'

export default function SuperadminPage() {
  const router = useRouter()
  const { withLoading } = useLoading()
  const userId = useUserId()
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Form state
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [country, setCountry] = useState('UY')
  const [businessType, setBusinessType] = useState('')
  const [languageStyle, setLanguageStyle] = useState('es_uy_formal')
  const [defaultAudience, setDefaultAudience] = useState('operativo')
  const [contextText, setContextText] = useState('')
  const [planName, setPlanName] = useState('b2b_trial')
  const [adminEmail, setAdminEmail] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    loadWorkspaces()
  }, [])

  const loadWorkspaces = async () => {
    try {
      setLoading(true)
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token || ''

      const data = await listAllWorkspaces('organization', token)
      setWorkspaces(data)
    } catch (err) {
      console.error('Error cargando workspaces:', err)
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const handleSlugChange = (value: string) => {
    const autoSlug = value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
    setSlug(autoSlug)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!name.trim() || !slug.trim() || !adminEmail.trim()) {
      setError('Nombre, slug y email del admin son requeridos')
      return
    }

    await withLoading(async () => {
      try {
        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token || ''

        await createB2BWorkspace(
          {
            name: name.trim(),
            slug: slug.trim(),
            country,
            business_type: businessType || undefined,
            language_style: languageStyle,
            default_audience: defaultAudience,
            context_text: contextText || undefined,
            plan_name: planName,
            admin_email: adminEmail.trim(),
            message: message || undefined,
          },
          token
        )

        // Reset form
        setName('')
        setSlug('')
        setBusinessType('')
        setContextText('')
        setAdminEmail('')
        setMessage('')
        setShowCreateForm(false)

        // Reload workspaces
        await loadWorkspaces()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al crear workspace')
      }
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Panel de Superadmin</h1>
          <p className="mt-2 text-sm text-gray-600">
            Gestiona espacios de trabajo B2B, asigna planes de suscripción e invita administradores
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        <div className="mb-6">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
          >
            {showCreateForm ? 'Cancelar' : '+ Crear Espacio de Trabajo B2B'}
          </button>
        </div>

        {showCreateForm && (
          <div className="bg-white shadow rounded-lg p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">Crear Espacio de Trabajo B2B</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nombre de la Organización *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value)
                      handleSlugChange(e.target.value)
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Slug (URL) *
                  </label>
                  <input
                    type="text"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    País
                  </label>
                  <input
                    type="text"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tipo de Negocio
                  </label>
                  <input
                    type="text"
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Plan de Suscripción
                  </label>
                  <select
                    value={planName}
                    onChange={(e) => setPlanName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="b2b_trial">Trial B2B</option>
                    <option value="b2b_starter">Starter B2B</option>
                    <option value="b2b_professional">Professional B2B</option>
                    <option value="b2b_enterprise">Enterprise B2B</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email del Admin *
                  </label>
                  <input
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Mensaje de Invitación (opcional)
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50"
                >
                  Crear Espacio de Trabajo e Invitar Admin
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">Espacios de Trabajo B2B</h2>
          </div>
          {loading ? (
            <div className="p-6 text-center text-gray-500">Cargando...</div>
          ) : workspaces.length === 0 ? (
            <div className="p-6 text-center text-gray-500">No hay espacios de trabajo B2B</div>
          ) : (
            <div className="divide-y divide-gray-200">
              {workspaces.map((workspace) => (
                <div key={workspace.id} className="p-6 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{workspace.name}</h3>
                      <p className="text-sm text-gray-500">Slug: {workspace.slug}</p>
                      <p className="text-xs text-gray-400">
                        Creado: {new Date(workspace.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => router.push(`/workspace/${workspace.id}/settings`)}
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                      >
                        Configurar
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


