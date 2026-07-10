'use client'

import {
  getWorkspaceLimits,
  listSubscriptionPlans,
  WorkspaceLimitsResponse,
} from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useEffect, useState } from 'react'

type LimitsSettingsTabProps = {
  workspaceId: string
}

export default function LimitsSettingsTab({ workspaceId }: LimitsSettingsTabProps) {
  const { withLoading } = useLoading()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [limits, setLimits] = useState<WorkspaceLimitsResponse | null>(null)

  useEffect(() => {
    const load = async () => {
      await withLoading(async () => {
        try {
          setLoading(true)
          setError(null)
          const limitsData = await getWorkspaceLimits(workspaceId).catch(() => null)
          setLimits(limitsData)
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Error cargando datos')
        } finally {
          setLoading(false)
        }
      })
    }
    void load()
  }, [workspaceId])

  if (loading) {
    return <p className="text-ink-600">Cargando...</p>
  }

  if (error) {
    return (
      <div className="bg-danger-bg border border-danger-bd text-danger px-4 py-3 rounded" role="alert">
        {error}
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">Límites y Uso Actual</h2>
      {limits ? (
        <div className="space-y-6">
          <div className="bg-ink-50 rounded-lg p-4">
            <h3 className="font-medium mb-2">Plan: {limits.plan_display_name}</h3>
            <p className="text-sm text-ink-600">{limits.plan_name}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Usuarios */}
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Usuarios</h4>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-ink-600">Usados</span>
                <span className="font-semibold">
                  {limits.current_usage.current_users_count}
                  {limits.limits.max_users !== null && ` / ${limits.limits.max_users}`}
                </span>
              </div>
              {limits.limits.max_users !== null && (
                <div className="w-full bg-ink-200 rounded-full h-2">
                  <div
                    className="bg-action h-2 rounded-full"
                    style={{
                      width: `${limits.limits.max_users ? Math.min((limits.current_usage.current_users_count / limits.limits.max_users) * 100, 100) : 0}%`,
                    }}
                  />
                </div>
              )}
              <p className={`text-xs mt-2 ${limits.can_create_users ? 'text-success' : 'text-danger'}`}>
                {limits.can_create_users ? 'Puede agregar usuarios' : 'Límite alcanzado'}
              </p>
            </div>

            {/* Documentos */}
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Documentos</h4>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-ink-600">Creados</span>
                <span className="font-semibold">
                  {limits.current_usage.current_documents_count}
                  {limits.limits.max_documents !== null && ` / ${limits.limits.max_documents}`}
                </span>
              </div>
              {limits.limits.max_documents !== null && (
                <div className="w-full bg-ink-200 rounded-full h-2">
                  <div
                    className="bg-action h-2 rounded-full"
                    style={{
                      width: `${limits.limits.max_documents ? Math.min((limits.current_usage.current_documents_count / limits.limits.max_documents) * 100, 100) : 0}%`,
                    }}
                  />
                </div>
              )}
              <p className={`text-xs mt-2 ${limits.can_create_documents ? 'text-success' : 'text-danger'}`}>
                {limits.can_create_documents ? 'Puede crear documentos' : 'Límite alcanzado'}
              </p>
            </div>

            {/* Documentos este mes */}
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Documentos este Mes</h4>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-ink-600">Creados</span>
                <span className="font-semibold">
                  {limits.current_usage.current_documents_this_month}
                  {limits.limits.max_documents_per_month !== null && ` / ${limits.limits.max_documents_per_month}`}
                </span>
              </div>
              {limits.limits.max_documents_per_month !== null && (
                <div className="w-full bg-ink-200 rounded-full h-2">
                  <div
                    className="bg-action h-2 rounded-full"
                    style={{
                      width: `${limits.limits.max_documents_per_month ? Math.min((limits.current_usage.current_documents_this_month / limits.limits.max_documents_per_month) * 100, 100) : 0}%`,
                    }}
                  />
                </div>
              )}
              <p className={`text-xs mt-2 ${limits.can_create_documents_this_month ? 'text-success' : 'text-danger'}`}>
                {limits.can_create_documents_this_month ? 'Puede crear documentos' : 'Límite mensual alcanzado'}
              </p>
            </div>

            {/* Almacenamiento */}
            <div className="border rounded-lg p-4">
              <h4 className="font-medium mb-2">Almacenamiento</h4>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-ink-600">Usado</span>
                <span className="font-semibold">
                  {limits.current_usage.current_storage_gb.toFixed(2)} GB
                  {limits.limits.max_storage_gb !== null && ` / ${limits.limits.max_storage_gb} GB`}
                </span>
              </div>
              {limits.limits.max_storage_gb !== null && (
                <div className="w-full bg-ink-200 rounded-full h-2">
                  <div
                    className="bg-action h-2 rounded-full"
                    style={{
                      width: `${limits.limits.max_storage_gb ? Math.min((limits.current_usage.current_storage_gb / limits.limits.max_storage_gb) * 100, 100) : 0}%`,
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-ink-600">No hay información de límites disponible</p>
      )}
    </div>
  )
}
