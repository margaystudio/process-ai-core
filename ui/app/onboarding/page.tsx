'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardBody, Input, Field, Button } from '@/shared/ui/components'
import { createWorkspace, WorkspaceCreateRequest, addUserToWorkspace } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUserId } from '@/hooks/useUserId'

const selectClass =
  'h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800 transition-colors focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring'

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
      .replace(/[̀-ͯ]/g, '') // Eliminar acentos
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
    <div className="min-h-screen bg-ink-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center gap-3">
          <img src="/brand/margay-icon-48.png" alt="" className="h-9 w-9 rounded-md" />
          <span className="text-sm font-semibold text-ink-600">Process AI · Plataforma Margay</span>
        </div>
        <Card>
          <CardBody className="p-8">
            <h1 className="mb-2 text-h1 text-ink-900">Bienvenido a Process AI</h1>
            <p className="mb-8 text-body text-ink-600">
              Para comenzar, necesitás crear o unirte a un espacio de trabajo (organización/cliente).
            </p>

            {error && (
              <div className="mb-6 rounded-md border border-danger-bd bg-danger-bg p-4 text-sm text-danger">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <Field label="Nombre del espacio de trabajo *">
                <Input
                  id="name"
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                    handleSlugChange(e.target.value)
                  }}
                  required
                  placeholder="Ej: Mi Empresa"
                />
              </Field>

              <div>
                <Field label="Identificador (URL) *">
                  <Input
                    id="slug"
                    type="text"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                    required
                    pattern="[a-z0-9\-]+"
                    placeholder="mi-empresa"
                  />
                </Field>
                <p className="mt-1 text-xs text-ink-500">
                  Solo letras minúsculas, números y guiones. Se genera automáticamente desde el nombre.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="País">
                  <select
                    id="country"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    className={selectClass}
                  >
                    <option value="UY">Uruguay</option>
                    <option value="AR">Argentina</option>
                    <option value="BR">Brasil</option>
                    <option value="CL">Chile</option>
                    <option value="CO">Colombia</option>
                    <option value="MX">México</option>
                    <option value="ES">España</option>
                  </select>
                </Field>

                <Field label="Estilo de idioma">
                  <select
                    id="languageStyle"
                    value={languageStyle}
                    onChange={(e) => setLanguageStyle(e.target.value)}
                    className={selectClass}
                  >
                    <option value="es_uy_formal">Español UY Formal</option>
                    <option value="es_uy_informal">Español UY Informal</option>
                    <option value="es_ar_formal">Español AR Formal</option>
                    <option value="es_mx_formal">Español MX Formal</option>
                  </select>
                </Field>
              </div>

              <Field label="Tipo de negocio (opcional)">
                <Input
                  id="businessType"
                  type="text"
                  value={businessType}
                  onChange={(e) => setBusinessType(e.target.value)}
                  placeholder="Ej: Retail, Manufactura, Servicios"
                />
              </Field>

              <Field label="Audiencia por defecto">
                <select
                  id="defaultAudience"
                  value={defaultAudience}
                  onChange={(e) => setDefaultAudience(e.target.value)}
                  className={selectClass}
                >
                  <option value="operativo">Operativo</option>
                  <option value="gestion">Gestión</option>
                </select>
              </Field>

              <div className="border-t border-ink-200 pt-4">
                <Button
                  type="submit"
                  variant="create"
                  className="w-full"
                  disabled={loading || !name.trim() || !slug.trim()}
                >
                  {loading ? 'Creando...' : 'Crear espacio de trabajo'}
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
