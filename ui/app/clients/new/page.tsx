'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createWorkspace, getCatalogOptions, createCatalogOption, CatalogOption } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

export default function NewClientPage() {
  const router = useRouter()
  const { refreshWorkspaces } = useWorkspace()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)

  // Campos del formulario
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [country, setCountry] = useState('UY')
  const [businessType, setBusinessType] = useState('')
  const [languageStyle, setLanguageStyle] = useState('')
  const [defaultAudience, setDefaultAudience] = useState('')
  const [contextText, setContextText] = useState('')

  // Opciones del catálogo
  const [businessTypeOptions, setBusinessTypeOptions] = useState<CatalogOption[]>([])
  const [languageStyleOptions, setLanguageStyleOptions] = useState<CatalogOption[]>([])
  const [audienceOptions, setAudienceOptions] = useState<CatalogOption[]>([])
  const [loadingCatalog, setLoadingCatalog] = useState(true)

  // Estado para agregar nuevo tipo de negocio
  const [showAddBusinessType, setShowAddBusinessType] = useState(false)
  const [newBusinessTypeLabel, setNewBusinessTypeLabel] = useState('')
  const [creatingBusinessType, setCreatingBusinessType] = useState(false)

  // Función para agregar nuevo tipo de negocio
  const handleAddBusinessType = async () => {
    if (!newBusinessTypeLabel.trim()) return
    setCreatingBusinessType(true)
    setError(null)
    try {
      const newOption = await createCatalogOption({
        domain: 'business_type',
        label: newBusinessTypeLabel.trim(),
      })
      // Agregar la nueva opción a la lista
      setBusinessTypeOptions([...businessTypeOptions, newOption])
      // Seleccionar la nueva opción
      setBusinessType(newOption.value)
      // Ocultar el formulario de agregar
      setShowAddBusinessType(false)
      setNewBusinessTypeLabel('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear tipo de negocio')
    } finally {
      setCreatingBusinessType(false)
    }
  }

  // Cargar opciones del catálogo
  useEffect(() => {
    async function loadCatalog() {
      try {
        const [businessTypes, languageStyles, audiences] = await Promise.all([
          getCatalogOptions('business_type').catch(() => []),
          getCatalogOptions('language_style').catch(() => []),
          getCatalogOptions('audience').catch(() => []),
        ])

        setBusinessTypeOptions(businessTypes)
        setLanguageStyleOptions(languageStyles)
        setAudienceOptions(audiences)

        // Establecer valores por defecto si hay opciones
        if (languageStyles.length > 0 && !languageStyle) {
          setLanguageStyle(languageStyles[0].value)
        }
        if (audiences.length > 0 && !defaultAudience) {
          setDefaultAudience(audiences[0].value)
        }
      } catch (err) {
        console.error('Error cargando catálogo:', err)
      } finally {
        setLoadingCatalog(false)
      }
    }

    loadCatalog()
  }, [])

  // Generar slug automáticamente desde el nombre
  const handleNameChange = (value: string) => {
    setName(value)
    // Generar slug automático (solo si el slug está vacío o coincide con el nombre anterior)
    if (!slug || slug === name.toLowerCase().replace(/\s+/g, '-')) {
      const autoSlug = value
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '') // Eliminar acentos
        .replace(/[^a-z0-9\s-]/g, '') // Eliminar caracteres especiales
        .trim()
        .replace(/\s+/g, '-') // Reemplazar espacios con guiones
        .replace(/-+/g, '-') // Eliminar guiones múltiples
      setSlug(autoSlug)
    }
  }

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)
    setResult(null)

    try {
      const response = await createWorkspace({
        name,
        slug,
        country,
        business_type: businessType || undefined,
        language_style: languageStyle,
        default_audience: defaultAudience,
        context_text: contextText || undefined,
      })

      setResult(response)
      
      // Refrescar workspaces para que aparezca el nuevo
      await refreshWorkspaces()
      
      // Redirigir inmediatamente
      router.push('/clients')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white rounded-lg shadow-sm p-8">
          <h1 className="text-3xl font-bold mb-6">Nuevo Cliente</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Nombre */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Nombre de la Organización *
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Ej: Empresa XYZ S.A."
              />
            </div>

            {/* Slug */}
            <div>
              <label htmlFor="slug" className="block text-sm font-medium text-gray-700 mb-2">
                Identificador (URL) *
              </label>
              <input
                type="text"
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                pattern="[a-z0-9\-]+"
                className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white font-mono text-sm"
                placeholder="empresa-xyz"
              />
              <p className="mt-1 text-sm text-gray-500">
                Solo letras minúsculas, números y guiones. Se genera automáticamente desde el nombre.
              </p>
            </div>

            {/* País */}
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
                <option value="UY">Uruguay (UY)</option>
                <option value="AR">Argentina (AR)</option>
                <option value="BR">Brasil (BR)</option>
                <option value="CL">Chile (CL)</option>
                <option value="PY">Paraguay (PY)</option>
              </select>
            </div>

            {/* Tipo de Negocio */}
            <div>
              <label htmlFor="business_type" className="block text-sm font-medium text-gray-700 mb-2">
                Tipo de Negocio
              </label>
              {loadingCatalog ? (
                <div className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-100 animate-pulse">
                  Cargando opciones...
                </div>
              ) : showAddBusinessType ? (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newBusinessTypeLabel}
                      onChange={(e) => setNewBusinessTypeLabel(e.target.value)}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Ej: Tecnología, Software, Consultoría"
                      disabled={creatingBusinessType}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && newBusinessTypeLabel.trim() && !creatingBusinessType) {
                          e.preventDefault()
                          handleAddBusinessType()
                        } else if (e.key === 'Escape') {
                          setShowAddBusinessType(false)
                          setNewBusinessTypeLabel('')
                        }
                      }}
                    />
                    <button
                      type="button"
                      onClick={handleAddBusinessType}
                      disabled={creatingBusinessType || !newBusinessTypeLabel.trim()}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {creatingBusinessType ? 'Creando...' : 'Agregar'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setShowAddBusinessType(false)
                        setNewBusinessTypeLabel('')
                      }}
                      disabled={creatingBusinessType}
                      className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              ) : (
                <select
                  id="business_type"
                  value={businessType}
                  onChange={(e) => {
                    if (e.target.value === '__add_new__') {
                      setShowAddBusinessType(true)
                    } else {
                      setBusinessType(e.target.value)
                    }
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Seleccionar...</option>
                  {businessTypeOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                  <option value="__add_new__" className="text-blue-600 font-medium">
                    + Agregar nuevo tipo de negocio...
                  </option>
                </select>
              )}
            </div>

            {/* Valores por Defecto */}
            <div className="pt-6 border-t">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Valores por Defecto</h3>
              <p className="text-sm text-gray-500 mb-4">
                Estos valores se usarán como predeterminados al crear procesos para este cliente.
              </p>

              <div className="space-y-4">
                <div>
                  <label htmlFor="default_audience" className="block text-sm font-medium text-gray-700 mb-2">
                    Audiencia
                  </label>
                  {loadingCatalog ? (
                    <div className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-100 animate-pulse">
                      Cargando...
                    </div>
                  ) : (
                    <select
                      id="default_audience"
                      value={defaultAudience}
                      onChange={(e) => setDefaultAudience(e.target.value)}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      {audienceOptions.length === 0 && <option value="">Cargando...</option>}
                      {audienceOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                <div>
                  <label htmlFor="language_style" className="block text-sm font-medium text-gray-700 mb-2">
                    Estilo de Idioma
                  </label>
                  {loadingCatalog ? (
                    <div className="w-full px-4 py-2 border border-gray-300 rounded-md bg-gray-100 animate-pulse">
                      Cargando...
                    </div>
                  ) : (
                    <select
                      id="language_style"
                      value={languageStyle}
                      onChange={(e) => setLanguageStyle(e.target.value)}
                      required
                      className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      {languageStyleOptions.length === 0 && <option value="">Cargando...</option>}
                      {languageStyleOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            </div>

            {/* Contexto */}
            <div>
              <label htmlFor="context_text" className="block text-sm font-medium text-gray-700 mb-2">
                Contexto del Negocio (opcional)
              </label>
              <textarea
                id="context_text"
                value={contextText}
                onChange={(e) => setContextText(e.target.value)}
                rows={4}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Información adicional sobre el negocio que ayudará a generar mejores documentos..."
              />
            </div>

            {/* Botones */}
            <div className="pt-6 border-t">
              <div className="flex gap-4">
                <button
                  type="submit"
                  disabled={isSubmitting || !name.trim() || !slug.trim()}
                  className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  {isSubmitting ? 'Creando...' : 'Crear Cliente'}
                </button>
                
                <a
                  href="/"
                  className="px-6 py-3 border border-gray-300 rounded-md hover:bg-gray-50 font-medium"
                >
                  Cancelar
                </a>
              </div>
            </div>
          </form>

          {error && (
            <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-700">
              <p className="font-semibold">Error</p>
              <p className="text-sm mt-1">{error}</p>
            </div>
          )}

          {result && (
            <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
              <p className="font-semibold text-green-800">¡Cliente creado exitosamente!</p>
              <p className="text-sm text-green-700 mt-2">ID: {result.id}</p>
              <p className="text-sm text-green-700">Slug: {result.slug}</p>
              <p className="text-sm text-green-600 mt-2">Redirigiendo a la lista de clientes...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

