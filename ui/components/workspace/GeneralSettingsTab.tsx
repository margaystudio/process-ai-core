'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  getWorkspace,
  updateWorkspaceSettings,
  getCatalogOptions,
  CatalogOption,
  WorkspaceSettingsUpdateRequest,
} from '@/lib/api'
import { isWorkspaceProfileIncomplete } from '@/lib/workspaceProfile'
import WorkspaceProfileBanner from '@/components/workspace/WorkspaceProfileBanner'

const COUNTRY_OPTIONS = [
  { value: 'UY', label: 'Uruguay' },
  { value: 'AR', label: 'Argentina' },
  { value: 'BR', label: 'Brasil' },
  { value: 'CL', label: 'Chile' },
  { value: 'CO', label: 'Colombia' },
  { value: 'MX', label: 'México' },
  { value: 'ES', label: 'España' },
]

const FALLBACK_LANGUAGE_STYLES = [
  { value: 'es_uy_formal', label: 'Español uruguayo formal' },
  { value: 'es_uy_informal', label: 'Español uruguayo informal' },
  { value: 'es_ar_formal', label: 'Español argentino formal' },
  { value: 'es_mx_formal', label: 'Español mexicano formal' },
]

const FALLBACK_AUDIENCES = [
  { value: 'operativo', label: 'Operativo' },
  { value: 'gestion', label: 'Gestión' },
]

const FALLBACK_DETAIL_LEVELS = [
  { value: 'breve', label: 'Breve' },
  { value: 'estandar', label: 'Estándar' },
  { value: 'detallado', label: 'Detallado' },
  { value: 'mixto', label: 'Mixto' },
]

type GeneralSettingsTabProps = {
  workspaceId: string
  canEdit: boolean
  hubUrl?: string
}

function catalogToOptions(items: CatalogOption[]): { value: string; label: string }[] {
  return items.map((o) => ({ value: o.value, label: o.label }))
}

function ensureOptionInList(
  options: { value: string; label: string }[],
  value: string | null | undefined
): { value: string; label: string }[] {
  if (!value) return options
  if (options.some((o) => o.value === value)) return options
  return [{ value, label: value }, ...options]
}

export default function GeneralSettingsTab({
  workspaceId,
  canEdit,
  hubUrl,
}: GeneralSettingsTabProps) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [tenantId, setTenantId] = useState<string | null>(null)

  const [country, setCountry] = useState('UY')
  const [businessType, setBusinessType] = useState('')
  const [languageStyle, setLanguageStyle] = useState('es_uy_formal')
  const [defaultAudience, setDefaultAudience] = useState('operativo')
  const [defaultDetailLevel, setDefaultDetailLevel] = useState('estandar')
  const [contextText, setContextText] = useState('')
  const [description, setDescription] = useState('')

  const [businessTypeOptions, setBusinessTypeOptions] = useState<{ value: string; label: string }[]>([])
  const [languageStyleOptions, setLanguageStyleOptions] = useState(FALLBACK_LANGUAGE_STYLES)
  const [audienceOptions, setAudienceOptions] = useState(FALLBACK_AUDIENCES)
  const [detailLevelOptions, setDetailLevelOptions] = useState(FALLBACK_DETAIL_LEVELS)

  const [profileIncomplete, setProfileIncomplete] = useState(false)

  const loadWorkspace = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ws, businessTypes, languageStyles, audiences, detailLevels] = await Promise.all([
        getWorkspace(workspaceId),
        getCatalogOptions('business_type').catch(() => []),
        getCatalogOptions('language_style').catch(() => []),
        getCatalogOptions('audience').catch(() => []),
        getCatalogOptions('detail_level').catch(() => []),
      ])

      setName(ws.name)
      setSlug(ws.slug)
      setTenantId(ws.tenant_id ?? null)
      setCountry(ws.country || 'UY')
      setBusinessType(ws.business_type || '')
      setLanguageStyle(ws.language_style || 'es_uy_formal')
      setDefaultAudience(ws.default_audience || 'operativo')
      setDefaultDetailLevel(ws.default_detail_level || 'estandar')
      setContextText(ws.context_text || '')
      setDescription(ws.description || '')

      const btOpts = catalogToOptions(businessTypes)
      setBusinessTypeOptions(ensureOptionInList(btOpts, ws.business_type))
      setLanguageStyleOptions(
        ensureOptionInList(
          languageStyles.length ? catalogToOptions(languageStyles) : FALLBACK_LANGUAGE_STYLES,
          ws.language_style
        )
      )
      setAudienceOptions(
        ensureOptionInList(
          audiences.length ? catalogToOptions(audiences) : FALLBACK_AUDIENCES,
          ws.default_audience
        )
      )
      setDetailLevelOptions(
        ensureOptionInList(
          detailLevels.length ? catalogToOptions(detailLevels) : FALLBACK_DETAIL_LEVELS,
          ws.default_detail_level
        )
      )

      setProfileIncomplete(isWorkspaceProfileIncomplete(ws))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar la configuración')
    } finally {
      setLoading(false)
    }
  }, [workspaceId])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    setSuccess(null)
    setError(null)
  }, [workspaceId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canEdit) return

    setSaving(true)
    setError(null)
    setSuccess(null)

    const payload: WorkspaceSettingsUpdateRequest = {
      country,
      business_type: businessType || '',
      language_style: languageStyle,
      default_audience: defaultAudience,
      default_detail_level: defaultDetailLevel,
      context_text: contextText,
      description: description,
    }

    try {
      const updated = await updateWorkspaceSettings(workspaceId, payload)
      setCountry(updated.country || 'UY')
      setBusinessType(updated.business_type || '')
      setLanguageStyle(updated.language_style || 'es_uy_formal')
      setDefaultAudience(updated.default_audience || 'operativo')
      setDefaultDetailLevel(updated.default_detail_level || 'estandar')
      setContextText(updated.context_text || '')
      setDescription(updated.description || '')
      setProfileIncomplete(isWorkspaceProfileIncomplete(updated))
      setSuccess('Configuración guardada correctamente.')
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('workspaceProfileUpdated', { detail: { workspaceId } }))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p className="text-gray-500 text-sm">Cargando configuración...</p>
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-2">Configuración General</h2>
      <p className="text-gray-600 text-sm mb-6">
        Preferencias del módulo Process AI para la generación de documentos. El nombre de la
        organización se gestiona en el hub de workspace.
      </p>

      {profileIncomplete && (
        <WorkspaceProfileBanner
          workspaceId={workspaceId}
          canEditSettings={canEdit}
          className="mb-4"
        />
      )}

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8 max-w-2xl">
        <section className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-800">Organización</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Nombre</label>
              <input
                type="text"
                value={name}
                readOnly
                className="w-full px-3 py-2 border border-gray-200 rounded-md bg-white text-gray-700 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Identificador (slug)</label>
              <input
                type="text"
                value={slug}
                readOnly
                className="w-full px-3 py-2 border border-gray-200 rounded-md bg-white text-gray-700 text-sm font-mono"
              />
            </div>
          </div>
          {tenantId && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Tenant ID</label>
              <input
                type="text"
                value={tenantId}
                readOnly
                className="w-full px-3 py-2 border border-gray-200 rounded-md bg-white text-gray-500 text-xs font-mono"
              />
            </div>
          )}
          {hubUrl && (
            <p className="text-xs text-gray-500">
              <a
                href={hubUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Abrir hub de workspace
              </a>
              {' '}
              para cambiar el nombre de la organización.
            </p>
          )}
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-800">Preferencias de documentación</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-1">
                País
              </label>
              <select
                id="country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                disabled={!canEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              >
                {COUNTRY_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="languageStyle" className="block text-sm font-medium text-gray-700 mb-1">
                Estilo de idioma
              </label>
              <select
                id="languageStyle"
                value={languageStyle}
                onChange={(e) => setLanguageStyle(e.target.value)}
                disabled={!canEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              >
                {languageStyleOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="businessType" className="block text-sm font-medium text-gray-700 mb-1">
              Tipo de negocio
            </label>
            {businessTypeOptions.length > 0 ? (
              <select
                id="businessType"
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                disabled={!canEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              >
                <option value="">— Sin especificar —</option>
                {businessTypeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="businessType"
                type="text"
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                disabled={!canEdit}
                placeholder="Ej: estaciones_servicio"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              />
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="defaultAudience" className="block text-sm font-medium text-gray-700 mb-1">
                Audiencia por defecto
              </label>
              <select
                id="defaultAudience"
                value={defaultAudience}
                onChange={(e) => setDefaultAudience(e.target.value)}
                disabled={!canEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              >
                {audienceOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="defaultDetailLevel" className="block text-sm font-medium text-gray-700 mb-1">
                Nivel de detalle por defecto
              </label>
              <select
                id="defaultDetailLevel"
                value={defaultDetailLevel}
                onChange={(e) => setDefaultDetailLevel(e.target.value)}
                disabled={!canEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
              >
                {detailLevelOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-800">Contexto para la IA</h3>
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              Descripción corta (opcional)
            </label>
            <input
              id="description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={!canEdit}
              maxLength={500}
              placeholder="Ej: Red de estaciones de servicio en Uruguay"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
            />
          </div>
          <div>
            <label htmlFor="contextText" className="block text-sm font-medium text-gray-700 mb-1">
              Contexto del negocio
            </label>
            <textarea
              id="contextText"
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              disabled={!canEdit}
              rows={6}
              maxLength={8000}
              placeholder="Rubro, turnos, regulaciones, vocabulario interno, qué evitar en la redacción..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm disabled:bg-gray-100"
            />
            <p className="mt-1 text-xs text-gray-500">
              Se usa al generar procesos y recetas. Los documentos nuevos heredan audiencia y detalle
              configurados arriba; se pueden ajustar por documento.
            </p>
          </div>
        </section>

        {canEdit ? (
          <div className="pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        ) : (
          <p className="text-sm text-gray-500">
            Solo los roles owner o creator pueden editar esta configuración.
          </p>
        )}
      </form>
    </div>
  )
}
