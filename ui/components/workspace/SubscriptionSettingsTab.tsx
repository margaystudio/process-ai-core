'use client'

import {
  getWorkspaceSubscription,
  getWorkspaceLimits,
  listSubscriptionPlans,
  SubscriptionPlanResponse,
  WorkspaceSubscriptionResponse,
  WorkspaceLimitsResponse,
} from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useEffect, useState } from 'react'

type SubscriptionSettingsTabProps = {
  workspaceId: string
}

export default function SubscriptionSettingsTab({ workspaceId }: SubscriptionSettingsTabProps) {
  const { withLoading } = useLoading()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [subscription, setSubscription] = useState<WorkspaceSubscriptionResponse | null>(null)
  const [availablePlans, setAvailablePlans] = useState<SubscriptionPlanResponse[]>([])

  useEffect(() => {
    const load = async () => {
      await withLoading(async () => {
        try {
          setLoading(true)
          setError(null)
          const [subData, plansData] = await Promise.all([
            getWorkspaceSubscription(workspaceId).catch(() => null),
            listSubscriptionPlans('b2b'),
          ])
          setSubscription(subData)
          setAvailablePlans(plansData)
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
      <h2 className="text-xl font-semibold mb-4">Suscripción</h2>
      {subscription ? (
        <div className="space-y-4">
          <div className="bg-ink-50 rounded-lg p-4">
            <h3 className="font-medium mb-2">Plan Actual</h3>
            <p className="text-2xl font-bold">{subscription.plan.display_name}</p>
            <p className="text-sm text-ink-600">{subscription.plan.description}</p>
          </div>

          <div>
            <h3 className="font-medium mb-2">Período Actual</h3>
            <p className="text-sm text-ink-600">
              Desde: {new Date(subscription.current_period_start).toLocaleDateString()}
            </p>
            <p className="text-sm text-ink-600">
              Hasta: {new Date(subscription.current_period_end).toLocaleDateString()}
            </p>
          </div>

          <div>
            <h3 className="font-medium mb-2">Estado</h3>
            <span
              className={`px-3 py-1 text-xs font-medium rounded-full ${
                subscription.status === 'active'
                  ? 'bg-success-bg text-success-fg'
                  : subscription.status === 'trial'
                  ? 'bg-accent-tint text-accent-ink'
                  : 'bg-danger-bg text-danger'
              }`}
            >
              {subscription.status}
            </span>
          </div>

          <div>
            <h3 className="font-medium mb-2">Planes Disponibles</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availablePlans.map((plan) => (
                <div
                  key={plan.id}
                  className={`border rounded-lg p-4 ${
                    plan.id === subscription.plan_id
                      ? 'border-accent bg-accent-tint'
                      : 'border-ink-200'
                  }`}
                >
                  <h4 className="font-semibold">{plan.display_name}</h4>
                  <p className="text-sm text-ink-600 mt-1">{plan.description}</p>
                  <p className="text-lg font-bold mt-2">${plan.price_monthly}/mes</p>
                  {plan.id === subscription.plan_id && (
                    <span className="text-xs text-accent font-medium">Plan Actual</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-ink-600">No hay suscripción activa</p>
      )}
    </div>
  )
}
