'use client'

import { useState, useEffect, ChangeEvent } from 'react'
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
  uploadWorkspaceBrandingIcon,
  deleteWorkspaceBrandingIcon,
  updateWorkspaceBranding,
} from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useUserId } from '@/hooks/useUserId'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useCanEditWorkspace, useCanManageUsers } from '@/hooks/useHasPermission'
import { useUserRole } from '@/hooks/useUserRole'
import { createClient } from '@/lib/supabase/client'

export default function WorkspaceSettingsPage() {
  const router = useRouter()
  const params = useParams()
  const { withLoading } = useLoading()
  const userId = useUserId()
  const { selectedWorkspaceId, workspaces, refreshWorkspaces } = useWorkspace()
  const workspaceId = (params?.id as string) || selectedWorkspaceId
  const { hasPermission: canEditWorkspace, loading: loadingEditPerm } = useCanEditWorkspace()
  const { hasPermission: canManageUsers, loading: loadingManagePerm } = useCanManageUsers()
  const { role, loading: loadingRole } = useUserRole()
  const currentWorkspace = workspaces.find((ws) => ws.id === workspaceId) || null
  const workspaceRole = currentWorkspace?.role ?? role
  
  // Verificar si el usuario es superadmin (tiene un workspace de tipo "system")
  const isSuperadmin = workspaces.some(ws => ws.workspace_type === 'system')
  
  // Superadmin tiene acceso a la configuración de cualquier workspace
  const hasAccess = isSuperadmin || canEditWorkspace || workspaceRole === 'owner' || workspaceRole === 'admin'
  const canManageBranding = workspaceRole === 'owner' || workspaceRole === 'creator'

  const [activeTab, setActiveTab] = useState<'general' | 'users' | 'subscription' | 'limits' | 'branding'>('general')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brandingIconUrl, setBrandingIconUrl] = useState<string | null>(null)
  const [brandingPrimaryColor, setBrandingPrimaryColor] = useState('#2563EB')
  const [brandingSecondaryColor, setBrandingSecondaryColor] = useState('#1D4ED8')
  const [brandingSaving, setBrandingSaving] = useState(false)
  const [brandingMessage, setBrandingMessage] = useState<string | null>(null)

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

  const extractBrandingColors = (file: File): Promise<{ primary: string; secondary: string }> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const img = new Image()
        img.onload = () => {
          const canvas = document.createElement('canvas')
          const ctx = canvas.getContext('2d', { willReadFrequently: true })
          if (!ctx) {
            reject(new Error('No se pudo analizar el icono'))
            return
          }

          const maxSize = 64
          const scale = Math.min(maxSize / img.width, maxSize / img.height, 1)
          canvas.width = Math.max(1, Math.round(img.width * scale))
          canvas.height = Math.max(1, Math.round(img.height * scale))
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

          const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const buckets = new Map<string, { count: number; rgb: [number, number, number] }>()

          for (let i = 0; i < data.length; i += 4) {
            const alpha = data[i + 3]
            if (alpha < 64) continue

            const r = data[i]
            const g = data[i + 1]
            const b = data[i + 2]
            const max = Math.max(r, g, b)
            const min = Math.min(r, g, b)
            const saturation = max === 0 ? 0 : (max - min) / max
            const brightness = (r + g + b) / 3

            // Ignorar blancos/grises muy neutros que suelen ser fondo.
            if (brightness > 245 || (saturation < 0.12 && brightness > 210)) continue

            const qr = Math.round(r / 32) * 32
            const qg = Math.round(g / 32) * 32
            const qb = Math.round(b / 32) * 32
            const key = `${qr},${qg},${qb}`
            const existing = buckets.get(key)
            if (existing) {
              existing.count += 1
            } else {
              buckets.set(key, { count: 1, rgb: [qr, qg, qb] })
            }
          }

          const colors = [...buckets.values()].sort((a, b) => b.count - a.count)
          if (colors.length === 0) {
            reject(new Error('No se pudieron detectar colores en el icono'))
            return
          }

          const toHex = ([r, g, b]: [number, number, number]) =>
            `#${[r, g, b].map((value) => Math.max(0, Math.min(255, value)).toString(16).padStart(2, '0')).join('').toUpperCase()}`

          const distance = (a: [number, number, number], b: [number, number, number]) =>
            Math.sqrt(
              ((a[0] - b[0]) ** 2) +
              ((a[1] - b[1]) ** 2) +
              ((a[2] - b[2]) ** 2)
            )

          const primary = colors[0].rgb
          const secondary = colors.find((color) => distance(color.rgb, primary) > 80)?.rgb || colors[Math.min(1, colors.length - 1)].rgb

          resolve({
            primary: toHex(primary),
            secondary: toHex(secondary),
          })
        }
        img.onerror = () => reject(new Error('No se pudo leer el icono'))
        img.src = String(reader.result)
      }
      reader.onerror = () => reject(new Error('No se pudo procesar el icono'))
      reader.readAsDataURL(file)
    })
  }

  useEffect(() => {
    if (workspaceId) {
      loadData()
    }
  }, [workspaceId])

  useEffect(() => {
    setBrandingIconUrl(currentWorkspace?.branding_icon_url || null)
    setBrandingPrimaryColor(currentWorkspace?.branding_primary_color || '#2563EB')
    setBrandingSecondaryColor(currentWorkspace?.branding_secondary_color || '#1D4ED8')
  }, [
    currentWorkspace?.branding_icon_url,
    currentWorkspace?.branding_primary_color,
    currentWorkspace?.branding_secondary_color,
  ])

  useEffect(() => {
    if (loadingEditPerm || loadingRole) return
    if (!hasAccess && canManageBranding) {
      setActiveTab('branding')
    }
  }, [hasAccess, canManageBranding, loadingEditPerm, loadingRole])

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

  const availableTabs = [
    ...(hasAccess ? [
      { id: 'general' as const, label: 'General' },
      { id: 'users' as const, label: 'Usuarios' },
      { id: 'subscription' as const, label: 'Suscripción' },
      { id: 'limits' as const, label: 'Límites y Uso' },
    ] : []),
    ...(canManageBranding ? [{ id: 'branding' as const, label: 'Personalización' }] : []),
  ]

  const hasAnyAccess = hasAccess || canManageBranding

  const handleBrandingFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!workspaceId || !file) return

    if (!['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'].includes(file.type)) {
      setBrandingMessage('Formato no soportado. Usa PNG, JPG, WEBP o SVG.')
      e.target.value = ''
      return
    }

    try {
      setBrandingSaving(true)
      setBrandingMessage(null)
      const [result, extractedColors] = await Promise.all([
        uploadWorkspaceBrandingIcon(workspaceId, file),
        extractBrandingColors(file),
      ])
      setBrandingIconUrl(result.icon_url)
      setBrandingPrimaryColor(extractedColors.primary)
      setBrandingSecondaryColor(extractedColors.secondary)
      await updateWorkspaceBranding(workspaceId, {
        primary_color: extractedColors.primary,
        secondary_color: extractedColors.secondary,
      })
      setBrandingMessage('Icono actualizado correctamente. Los colores se tomaron automaticamente desde la imagen.')
      await refreshWorkspaces()
    } catch (err) {
      setBrandingMessage(err instanceof Error ? err.message : 'No se pudo subir el icono.')
    } finally {
      setBrandingSaving(false)
      e.target.value = ''
    }
  }

  const handleDeleteBrandingIcon = async () => {
    if (!workspaceId) return

    try {
      setBrandingSaving(true)
      setBrandingMessage(null)
      await deleteWorkspaceBrandingIcon(workspaceId)
      setBrandingIconUrl(null)
      setBrandingMessage('Icono eliminado correctamente.')
      await refreshWorkspaces()
    } catch (err) {
      setBrandingMessage(err instanceof Error ? err.message : 'No se pudo eliminar el icono.')
    } finally {
      setBrandingSaving(false)
    }
  }

  const handleSaveBrandingColors = async () => {
    if (!workspaceId) return

    try {
      setBrandingSaving(true)
      setBrandingMessage(null)
      const result = await updateWorkspaceBranding(workspaceId, {
        primary_color: brandingPrimaryColor,
        secondary_color: brandingSecondaryColor,
      })
      setBrandingPrimaryColor(result.primary_color)
      setBrandingSecondaryColor(result.secondary_color)
      setBrandingMessage('Colores guardados correctamente.')
      await refreshWorkspaces()
    } catch (err) {
      setBrandingMessage(err instanceof Error ? err.message : 'No se pudieron guardar los colores.')
    } finally {
      setBrandingSaving(false)
    }
  }

  // Verificar permisos: owner/admin/superadmin ven settings completos; owner/creator ven personalización
  if (!loadingEditPerm && !loadingRole && !hasAnyAccess) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-red-900 mb-2">
              Acceso no autorizado
            </h2>
            <p className="text-red-800 mb-4">
              No tienes permisos para acceder a la configuración del espacio de trabajo.
            </p>
            <p className="text-sm text-red-700 mb-4">
              Solo los roles autorizados pueden acceder a esta página o a la sección de personalización.
            </p>
            <button
              onClick={() => router.push('/workspace')}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-medium"
            >
              Volver al workspace
            </button>
          </div>
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
              {availableTabs.map((tab) => (
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
            {activeTab === 'general' && hasAccess && (
              <div>
                <h2 className="text-xl font-semibold mb-4">Configuración General</h2>
                <p className="text-gray-600">Configuración general del espacio de trabajo (próximamente)</p>
              </div>
            )}

            {/* Branding Tab */}
            {activeTab === 'branding' && canManageBranding && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold mb-2">Personalización</h2>
                  <p className="text-gray-600">
                    Cargá un icono para este cliente. El sistema tomará automaticamente 2 colores principales desde la imagen y podrás ajustarlos manualmente si hace falta.
                  </p>
                </div>

                <div className="rounded-lg border border-gray-200 p-6 bg-gray-50">
                  <div className="flex flex-col md:flex-row md:items-center gap-6">
                    <div className="flex items-center gap-3">
                      <div className="flex h-16 w-16 items-center justify-center rounded-lg border border-gray-200 bg-white overflow-hidden">
                        {brandingIconUrl ? (
                          <img src={brandingIconUrl} alt="Icono del cliente" className="h-14 w-14 object-contain" />
                        ) : (
                          <span className="text-xs text-gray-400 text-center px-2">Sin icono</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-white border border-gray-200">
                          <img src="/margay-logo.png" alt="Logo de Process AI" className="h-10 w-10 object-contain" />
                        </div>
                        <span
                          className="text-xl font-bold"
                          style={
                            brandingPrimaryColor === brandingSecondaryColor
                              ? { color: brandingPrimaryColor }
                              : {
                                  backgroundImage: `linear-gradient(90deg, ${brandingPrimaryColor}, ${brandingSecondaryColor})`,
                                  WebkitBackgroundClip: 'text',
                                  backgroundClip: 'text',
                                  color: 'transparent',
                                }
                          }
                        >
                          Process AI
                        </span>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <label className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-md cursor-pointer disabled:opacity-50">
                        <input
                          type="file"
                          accept=".png,.jpg,.jpeg,.webp,.svg,image/png,image/jpeg,image/webp,image/svg+xml"
                          className="sr-only"
                          onChange={handleBrandingFileChange}
                          disabled={brandingSaving}
                        />
                        {brandingSaving ? 'Guardando...' : 'Cargar icono'}
                      </label>
                      {brandingIconUrl && (
                        <button
                          type="button"
                          onClick={handleDeleteBrandingIcon}
                          className="block px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                          disabled={brandingSaving}
                        >
                          Quitar icono
                        </button>
                      )}
                      <p className="text-xs text-gray-500">
                        Formatos permitidos: PNG, JPG, WEBP o SVG. Tamaño máximo: 2 MB.
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                        <label className="block">
                          <span className="block text-sm font-medium text-gray-700 mb-2">Color principal</span>
                          <div className="flex items-center gap-3">
                            <input
                              type="color"
                              value={brandingPrimaryColor}
                              onChange={(e) => setBrandingPrimaryColor(e.target.value.toUpperCase())}
                              className="h-11 w-14 rounded border border-gray-300 bg-white p-1"
                              disabled={brandingSaving}
                            />
                            <span className="text-sm font-mono text-gray-600">{brandingPrimaryColor}</span>
                          </div>
                        </label>

                        <label className="block">
                          <span className="block text-sm font-medium text-gray-700 mb-2">Color secundario</span>
                          <div className="flex items-center gap-3">
                            <input
                              type="color"
                              value={brandingSecondaryColor}
                              onChange={(e) => setBrandingSecondaryColor(e.target.value.toUpperCase())}
                              className="h-11 w-14 rounded border border-gray-300 bg-white p-1"
                              disabled={brandingSaving}
                            />
                            <span className="text-sm font-mono text-gray-600">{brandingSecondaryColor}</span>
                          </div>
                        </label>
                      </div>

                      <button
                        type="button"
                        onClick={handleSaveBrandingColors}
                        className="inline-flex items-center px-4 py-2 rounded-md text-white font-medium disabled:opacity-50"
                        style={{ backgroundColor: brandingPrimaryColor }}
                        disabled={brandingSaving}
                      >
                        {brandingSaving ? 'Guardando...' : 'Guardar colores'}
                      </button>
                    </div>
                  </div>

                  {brandingMessage && (
                    <p className={`mt-4 text-sm ${brandingMessage.includes('correctamente') ? 'text-green-700' : 'text-red-600'}`}>
                      {brandingMessage}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Users Tab */}
            {activeTab === 'users' && hasAccess && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-semibold">Usuarios e Invitaciones</h2>
                  {canManageUsers && (
                    <button
                      onClick={() => setShowInviteForm(!showInviteForm)}
                      className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md"
                    >
                      {showInviteForm ? 'Cancelar' : '+ Invitar Usuario'}
                    </button>
                  )}
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
                          <option value="owner">Owner</option>
                          <option value="admin">Admin</option>
                          <option value="approver">Approver</option>
                          <option value="creator">Creator</option>
                          <option value="viewer">Viewer</option>
                        </select>
                        {/* Descripción dinámica del rol */}
                        <p className="mt-1 text-xs text-gray-500">
                          {inviteRole === 'owner' && 'Dueño del workspace. Tiene todos los permisos, incluyendo eliminar documentos.'}
                          {inviteRole === 'admin' && 'Puede administrar usuarios y configurar el espacio de trabajo.'}
                          {inviteRole === 'approver' && 'Puede revisar y aprobar procesos.'}
                          {inviteRole === 'creator' && 'Puede crear y editar procesos, pero no aprobarlos.'}
                          {inviteRole === 'viewer' && 'Puede consultar procesos aprobados. Ideal para operarios.'}
                        </p>
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
            {activeTab === 'subscription' && hasAccess && (
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
            {activeTab === 'limits' && hasAccess && (
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

