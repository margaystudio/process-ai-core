'use client'

import { useState, useEffect } from 'react'
import { useRouter, useParams } from 'next/navigation'
import {
  getWorkspaceSubscription,
  getWorkspaceLimits,
  listSubscriptionPlans,
  SubscriptionPlanResponse,
  WorkspaceSubscriptionResponse,
  WorkspaceLimitsResponse,
  listWorkspaceInvitations,
  InvitationResponse,
  createWorkspaceInvitation,
} from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { createClient } from '@/lib/supabase/client'

export default function WorkspaceSettingsPage() {
  const router = useRouter()
  const params = useParams()
  const { withLoading } = useLoading()
  const userId = useUserId()
  const { selectedWorkspaceId } = useWorkspace()
  const workspaceId = (params?.id as string) || selectedWorkspaceId

  const [activeTab, setActiveTab] = useState<'general' | 'users' | 'subscription' | 'limits'>('general')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Subscription data
  const [subscription, setSubscription] = useState<WorkspaceSubscriptionResponse | null>(null)
  const [limits, setLimits] = useState<WorkspaceLimitsResponse | null>(null)
  const [availablePlans, setAvailablePlans] = useState<SubscriptionPlanResponse[]>([])

  // Invitations data
  const [invitations, setInvitations] = useState<InvitationResponse[]>([])
  const [showInviteForm, setShowInviteForm] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('creator')
  const [inviteMessage, setInviteMessage] = useState('')
  const [lastInvitationUrl, setLastInvitationUrl] = useState<string | null>(null)

  useEffect(() => {
    if (workspaceId) {
      loadData()
    }
  }, [workspaceId])

  const loadData = async () => {
    if (!workspaceId) return

    await withLoading(async () => {
      try {
        setLoading(true)
        setError(null)

        // Load subscription and limits
        const [subData, limitsData, plansData, invitationsData] = await Promise.all([
          getWorkspaceSubscription(workspaceId).catch(() => null),
          getWorkspaceLimits(workspaceId).catch(() => null),
          listSubscriptionPlans('b2b'),
          loadInvitations(),
        ])

        setSubscription(subData)
        setLimits(limitsData)
        setAvailablePlans(plansData)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error cargando datos')
      } finally {
        setLoading(false)
      }
    })
  }

  const loadInvitations = async () => {
    if (!workspaceId) return []

    try {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token || ''

      const data = await listWorkspaceInvitations(workspaceId, undefined, token)
      setInvitations(data)
      return data
    } catch (err) {
      console.error('Error cargando invitaciones:', err)
      return []
    }
  }

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId || !inviteEmail.trim()) {
      setError('Email es requerido')
      return
    }

    await withLoading(async () => {
      try {
        setError(null)

        const supabase = createClient()
        const { data: { session } } = await supabase.auth.getSession()
        const token = session?.access_token || ''

        // Necesitamos obtener el role_id del rol seleccionado
        // Por ahora, usamos un endpoint que acepta role_name
        // TODO: Implementar endpoint que acepte role_name o crear helper para obtener role_id

        const invitation = await createWorkspaceInvitation(
          workspaceId,
          {
            email: inviteEmail.trim(),
            role_name: inviteRole, // Usar role_name en lugar de role_id
            message: inviteMessage || undefined,
          },
          token
        )

        // Guardar el link de invitación
        if (invitation.invitation_url) {
          setLastInvitationUrl(invitation.invitation_url)
        }

        // Reset form
        setInviteEmail('')
        setInviteMessage('')
        setShowInviteForm(false)

        // Reload invitations
        await loadInvitations()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al crear invitación')
      }
    })
  }

  if (!workspaceId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Espacio de trabajo no seleccionado</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Configuración del Espacio de Trabajo</h1>
          <p className="mt-2 text-sm text-gray-600">
            Gestiona la configuración, usuarios, suscripción y límites del espacio de trabajo
          </p>
        </div>

        {error && (
          <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              {[
                { id: 'general', label: 'General' },
                { id: 'users', label: 'Usuarios' },
                { id: 'subscription', label: 'Suscripción' },
                { id: 'limits', label: 'Límites y Uso' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {/* General Tab */}
            {activeTab === 'general' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Configuración General</h2>
                <p className="text-gray-600">Configuración general del espacio de trabajo (próximamente)</p>
              </div>
            )}

            {/* Users Tab */}
            {activeTab === 'users' && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-semibold">Usuarios e Invitaciones</h2>
                  <button
                    onClick={() => setShowInviteForm(!showInviteForm)}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
                  >
                    {showInviteForm ? 'Cancelar' : '+ Invitar Usuario'}
                  </button>
                </div>

                {showInviteForm && (
                  <div className="bg-gray-50 rounded-lg p-4 mb-6">
                    <form onSubmit={handleInviteUser} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Email del Usuario *
                        </label>
                        <input
                          type="email"
                          value={inviteEmail}
                          onChange={(e) => setInviteEmail(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                          required
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Rol
                        </label>
                        <select
                          value={inviteRole}
                          onChange={(e) => setInviteRole(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="creator">Creator</option>
                          <option value="approver">Approver</option>
                          <option value="viewer">Viewer</option>
                          <option value="admin">Admin</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Mensaje (opcional)
                        </label>
                        <textarea
                          value={inviteMessage}
                          onChange={(e) => setInviteMessage(e.target.value)}
                          rows={3}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                        />
                      </div>

                      <div className="flex justify-end">
                        <button
                          type="submit"
                          className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
                        >
                          Enviar Invitación
                        </button>
                      </div>
                    </form>
                  </div>
                )}

                {lastInvitationUrl && (
                  <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm font-medium text-blue-900 mb-2">
                      ✅ Invitación creada exitosamente
                    </p>
                    <p className="text-xs text-blue-700 mb-3">
                      Copiá este link y enviáselo al usuario invitado (el sistema de emails aún no está configurado):
                    </p>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value={lastInvitationUrl}
                        className="flex-1 px-3 py-2 bg-white border border-blue-300 rounded-md text-sm font-mono"
                      />
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(lastInvitationUrl)
                          alert('Link copiado al portapapeles')
                        }}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md"
                      >
                        Copiar
                      </button>
                      <button
                        onClick={() => setLastInvitationUrl(null)}
                        className="px-3 py-2 text-blue-600 hover:text-blue-800 text-sm"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                )}

                <div className="space-y-4">
                  <h3 className="text-lg font-medium">Invitaciones Pendientes</h3>
                  {invitations.filter((inv) => inv.status === 'pending').length === 0 ? (
                    <p className="text-gray-500">No hay invitaciones pendientes</p>
                  ) : (
                    <div className="divide-y divide-gray-200">
                      {invitations
                        .filter((inv) => inv.status === 'pending')
                        .map((invitation) => (
                          <div key={invitation.id} className="py-4 border-b border-gray-200 last:border-b-0">
                            <div className="flex items-start justify-between gap-4">
                              <div className="flex-1">
                                <p className="font-medium">{invitation.email}</p>
                                <p className="text-sm text-gray-500">
                                  Rol: {invitation.role_name} • Expira: {new Date(invitation.expires_at).toLocaleDateString()}
                                </p>
                                {invitation.invitation_url && (
                                  <div className="mt-3 flex items-center gap-2">
                                    <input
                                      type="text"
                                      readOnly
                                      value={invitation.invitation_url}
                                      className="flex-1 px-3 py-1.5 bg-gray-50 border border-gray-300 rounded-md text-xs font-mono"
                                    />
                                    <button
                                      onClick={() => {
                                        navigator.clipboard.writeText(invitation.invitation_url!)
                                        alert('Link copiado al portapapeles')
                                      }}
                                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md whitespace-nowrap"
                                    >
                                      Copiar Link
                                    </button>
                                  </div>
                                )}
                              </div>
                              <span className="px-3 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800 whitespace-nowrap">
                                Pendiente
                              </span>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}

                  <h3 className="text-lg font-medium mt-6">Invitaciones Aceptadas</h3>
                  {invitations.filter((inv) => inv.status === 'accepted').length === 0 ? (
                    <p className="text-gray-500">No hay invitaciones aceptadas</p>
                  ) : (
                    <div className="divide-y divide-gray-200">
                      {invitations
                        .filter((inv) => inv.status === 'accepted')
                        .map((invitation) => (
                          <div key={invitation.id} className="py-4">
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium">{invitation.email}</p>
                                <p className="text-sm text-gray-500">
                                  Rol: {invitation.role_name} • Aceptada: {invitation.accepted_at ? new Date(invitation.accepted_at).toLocaleDateString() : 'N/A'}
                                </p>
                              </div>
                              <span className="px-3 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                                Aceptada
                              </span>
                            </div>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Subscription Tab */}
            {activeTab === 'subscription' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Suscripción</h2>
                {subscription ? (
                  <div className="space-y-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h3 className="font-medium mb-2">Plan Actual</h3>
                      <p className="text-2xl font-bold">{subscription.plan.display_name}</p>
                      <p className="text-sm text-gray-600">{subscription.plan.description}</p>
                    </div>

                    <div>
                      <h3 className="font-medium mb-2">Período Actual</h3>
                      <p className="text-sm text-gray-600">
                        Desde: {new Date(subscription.current_period_start).toLocaleDateString()}
                      </p>
                      <p className="text-sm text-gray-600">
                        Hasta: {new Date(subscription.current_period_end).toLocaleDateString()}
                      </p>
                    </div>

                    <div>
                      <h3 className="font-medium mb-2">Estado</h3>
                      <span
                        className={`px-3 py-1 text-xs font-medium rounded-full ${
                          subscription.status === 'active'
                            ? 'bg-green-100 text-green-800'
                            : subscription.status === 'trial'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-red-100 text-red-800'
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
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200'
                            }`}
                          >
                            <h4 className="font-semibold">{plan.display_name}</h4>
                            <p className="text-sm text-gray-600 mt-1">{plan.description}</p>
                            <p className="text-lg font-bold mt-2">
                              ${plan.price_monthly}/mes
                            </p>
                            {plan.id === subscription.plan_id && (
                              <span className="text-xs text-blue-600 font-medium">Plan Actual</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-gray-600">No hay suscripción activa</p>
                )}
              </div>
            )}

            {/* Limits Tab */}
            {activeTab === 'limits' && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Límites y Uso Actual</h2>
                {limits ? (
                  <div className="space-y-6">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <h3 className="font-medium mb-2">Plan: {limits.plan_display_name}</h3>
                      <p className="text-sm text-gray-600">{limits.plan_name}</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Usuarios */}
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Usuarios</h4>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">Usados</span>
                          <span className="font-semibold">
                            {limits.current_usage.current_users_count}
                            {limits.limits.max_users !== null && ` / ${limits.limits.max_users}`}
                          </span>
                        </div>
                        {limits.limits.max_users !== null && (
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
                              style={{
                                width: `${limits.limits.max_users ? Math.min((limits.current_usage.current_users_count / limits.limits.max_users) * 100, 100) : 0}%`,
                              }}
                            />
                          </div>
                        )}
                        <p className={`text-xs mt-2 ${limits.can_create_users ? 'text-green-600' : 'text-red-600'}`}>
                          {limits.can_create_users ? '✓ Puede agregar usuarios' : '✗ Límite alcanzado'}
                        </p>
                      </div>

                      {/* Documentos */}
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Documentos</h4>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">Creados</span>
                          <span className="font-semibold">
                            {limits.current_usage.current_documents_count}
                            {limits.limits.max_documents !== null && ` / ${limits.limits.max_documents}`}
                          </span>
                        </div>
                        {limits.limits.max_documents !== null && (
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
                              style={{
                                width: `${limits.limits.max_documents ? Math.min((limits.current_usage.current_documents_count / limits.limits.max_documents) * 100, 100) : 0}%`,
                              }}
                            />
                          </div>
                        )}
                        <p className={`text-xs mt-2 ${limits.can_create_documents ? 'text-green-600' : 'text-red-600'}`}>
                          {limits.can_create_documents ? '✓ Puede crear documentos' : '✗ Límite alcanzado'}
                        </p>
                      </div>

                      {/* Documentos este mes */}
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Documentos este Mes</h4>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">Creados</span>
                          <span className="font-semibold">
                            {limits.current_usage.current_documents_this_month}
                            {limits.limits.max_documents_per_month !== null && ` / ${limits.limits.max_documents_per_month}`}
                          </span>
                        </div>
                        {limits.limits.max_documents_per_month !== null && (
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
                              style={{
                                width: `${limits.limits.max_documents_per_month ? Math.min((limits.current_usage.current_documents_this_month / limits.limits.max_documents_per_month) * 100, 100) : 0}%`,
                              }}
                            />
                          </div>
                        )}
                        <p className={`text-xs mt-2 ${limits.can_create_documents_this_month ? 'text-green-600' : 'text-red-600'}`}>
                          {limits.can_create_documents_this_month ? '✓ Puede crear documentos' : '✗ Límite mensual alcanzado'}
                        </p>
                      </div>

                      {/* Almacenamiento */}
                      <div className="border rounded-lg p-4">
                        <h4 className="font-medium mb-2">Almacenamiento</h4>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-gray-600">Usado</span>
                          <span className="font-semibold">
                            {limits.current_usage.current_storage_gb.toFixed(2)} GB
                            {limits.limits.max_storage_gb !== null && ` / ${limits.limits.max_storage_gb} GB`}
                          </span>
                        </div>
                        {limits.limits.max_storage_gb !== null && (
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full"
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
                  <p className="text-gray-600">No hay información de límites disponible</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

