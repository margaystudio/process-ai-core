'use client'

import { useState, useEffect, useCallback, ChangeEvent } from 'react'
import { useRouter, useParams } from 'next/navigation'
import {
  listOperationalRoles,
  createOperationalRole,
  deleteOperationalRole,
  getWorkspaceMembers,
  assignOperationalRolesToMembership,
  listFolders,
  getFolderPermissions,
  updateFolderPermissions,
  OperationalRoleResponse,
  WorkspaceMember,
  Folder,
  FolderPermissionsResponse,
  uploadWorkspaceBrandingIcon,
  deleteWorkspaceBrandingIcon,
  updateWorkspaceBranding,
} from '@/lib/api'
import { useLoading } from '@/contexts/LoadingContext'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useCanEditWorkspace, useCanManageUsers } from '@/hooks/useHasPermission'
import { useUserRole } from '@/hooks/useUserRole'
import { canAdministerWorkspace } from '@/lib/adminGating'
import { extractBrandingColors } from '@/lib/extractBrandingColors'
import GeneralSettingsTab from '@/components/workspace/GeneralSettingsTab'
import UsersSettingsTab from '@/components/workspace/UsersSettingsTab'
import RolesSettingsTab from '@/components/workspace/RolesSettingsTab'
import FoldersSettingsTab from '@/components/workspace/FoldersSettingsTab'
import SubscriptionSettingsTab from '@/components/workspace/SubscriptionSettingsTab'
import LimitsSettingsTab from '@/components/workspace/LimitsSettingsTab'
import BrandingSettingsTab from '@/components/workspace/BrandingSettingsTab'

const DEFAULT_PRIMARY_BRAND_COLOR = '#2563EB'
const DEFAULT_SECONDARY_BRAND_COLOR = '#1D4ED8'

type ActiveTab = 'general' | 'users' | 'subscription' | 'limits' | 'roles' | 'folders' | 'branding'

export default function WorkspaceSettingsPage() {
  const router = useRouter()
  const params = useParams()
  const { withLoading } = useLoading()
  const { selectedWorkspaceId, workspaces, platformRoles, refreshWorkspaces, activeTenantId } =
    useWorkspace()
  const paramWorkspaceId = params?.id as string | undefined
  const workspaceId = selectedWorkspaceId || paramWorkspaceId || null

  useEffect(() => {
    if (!selectedWorkspaceId || !paramWorkspaceId || paramWorkspaceId === selectedWorkspaceId) {
      return
    }
    const search = typeof window !== 'undefined' ? window.location.search : ''
    router.replace(`/workspace/${selectedWorkspaceId}/settings${search}`)
  }, [selectedWorkspaceId, paramWorkspaceId, router])

  useEffect(() => {
    setError(null)
    setBrandingMessage(null)
    setOperationalRoles([])
    setMembers([])
    setFolders([])
    setEditingMemberId(null)
    setFolderPermissionsModal(null)
  }, [workspaceId, activeTenantId])

  const { hasPermission: canEditWorkspace, loading: loadingEditPerm } = useCanEditWorkspace()
  const { hasPermission: canManageUsers, loading: loadingManagePerm } = useCanManageUsers()
  const { role, loading: loadingRole } = useUserRole()
  const currentWorkspace = workspaces.find((ws) => ws.id === workspaceId) || null
  const workspaceRole = currentWorkspace?.role ?? role
  // Históricamente creator solo accede a branding, salvo que tenga workspace.edit.
  const generalAccessRole = workspaceRole === 'creator' ? null : workspaceRole

  const hasAccess = canAdministerWorkspace({
    platformRoles,
    workspaceRole: generalAccessRole,
    canEditWorkspace,
  })
  const canManageBranding = workspaceRole === 'owner' || workspaceRole === 'creator'
  const canEditGeneralSettings = canAdministerWorkspace({
    platformRoles,
    workspaceRole,
  })
  const hubUrl = process.env.NEXT_PUBLIC_HUB_URL

  const [activeTab, setActiveTab] = useState<ActiveTab>('general')

  useEffect(() => {
    if (typeof window === 'undefined') return
    const tab = new URLSearchParams(window.location.search).get('tab')
    if (tab === 'general' && hasAccess) {
      setActiveTab('general')
    }
  }, [hasAccess])

  const [error, setError] = useState<string | null>(null)

  // Branding state
  const [brandingIconUrl, setBrandingIconUrl] = useState<string | null>(null)
  const [brandingPrimaryColor, setBrandingPrimaryColor] = useState(DEFAULT_PRIMARY_BRAND_COLOR)
  const [brandingSecondaryColor, setBrandingSecondaryColor] = useState(DEFAULT_SECONDARY_BRAND_COLOR)
  const [brandingSaving, setBrandingSaving] = useState(false)
  const [brandingMessage, setBrandingMessage] = useState<string | null>(null)

  // Roles operativos + miembros (compartido entre tabs users/roles/folders)
  const [operationalRoles, setOperationalRoles] = useState<OperationalRoleResponse[]>([])
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleDescription, setNewRoleDescription] = useState('')
  const [editingMemberId, setEditingMemberId] = useState<string | null>(null)
  const [memberRoleIds, setMemberRoleIds] = useState<string[]>([])

  // Carpetas y permisos
  const [folders, setFolders] = useState<Folder[]>([])
  const [folderPermissionsModal, setFolderPermissionsModal] = useState<{
    folder: Folder
    perms: FolderPermissionsResponse
  } | null>(null)
  const [folderPermsInherit, setFolderPermsInherit] = useState(true)
  const [folderPermsRoleIds, setFolderPermsRoleIds] = useState<string[]>([])

  const reloadFolders = useCallback(async () => {
    if (!workspaceId) {
      setFolders([])
      return
    }
    try {
      const data = await listFolders(workspaceId)
      setFolders(data)
    } catch {
      setFolders([])
    }
  }, [workspaceId])

  useEffect(() => {
    if (workspaceId && (activeTab === 'users' || activeTab === 'roles' || activeTab === 'folders')) {
      void loadOperationalRolesAndMembers()
    }
    // Solo debe recargar cuando cambia `workspaceId`/`activeTab` — la función
    // no está memoizada (se recrea cada render) y agregarla dispararía un
    // refetch en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, activeTab])

  useEffect(() => {
    if (workspaceId && activeTab === 'folders') {
      void reloadFolders()
    }
  }, [workspaceId, activeTab, reloadFolders])

  useEffect(() => {
    setBrandingIconUrl(currentWorkspace?.branding_icon_url || null)
    setBrandingPrimaryColor(currentWorkspace?.branding_primary_color || DEFAULT_PRIMARY_BRAND_COLOR)
    setBrandingSecondaryColor(currentWorkspace?.branding_secondary_color || DEFAULT_SECONDARY_BRAND_COLOR)
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

  const loadOperationalRolesAndMembers = async () => {
    if (!workspaceId) return
    try {
      const [rolesData, membersData] = await Promise.all([
        listOperationalRoles(workspaceId),
        getWorkspaceMembers(workspaceId),
      ])
      setOperationalRoles(rolesData)
      setMembers(membersData.members || [])
    } catch (err) {
      console.error('Error cargando roles operativos o miembros:', err)
    }
  }

  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId || !newRoleName.trim()) return
    await withLoading(async () => {
      try {
        await createOperationalRole(workspaceId, {
          name: newRoleName.trim(),
          description: newRoleDescription.trim() || undefined,
        })
        setNewRoleName('')
        setNewRoleDescription('')
        await loadOperationalRolesAndMembers()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al crear rol')
      }
    })
  }

  const handleDeleteRole = async (roleId: string) => {
    try {
      await deleteOperationalRole(roleId)
      await loadOperationalRolesAndMembers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al eliminar')
    }
  }

  const handleSaveMemberRoles = async () => {
    if (!editingMemberId) return
    await withLoading(async () => {
      try {
        await assignOperationalRolesToMembership(editingMemberId, memberRoleIds)
        setEditingMemberId(null)
        await loadOperationalRolesAndMembers()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al guardar roles')
      }
    })
  }

  const openMemberEdit = (member: WorkspaceMember) => {
    setEditingMemberId(member.membership_id)
    setMemberRoleIds([...member.operational_role_ids])
  }

  const openFolderPermissions = async (folder: Folder) => {
    try {
      const perms = await getFolderPermissions(folder.id)
      setFolderPermissionsModal({ folder, perms })
      setFolderPermsInherit(perms.inherits_permissions)
      setFolderPermsRoleIds(perms.operational_role_ids || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar permisos')
    }
  }

  const saveFolderPermissions = async () => {
    if (!folderPermissionsModal) return
    try {
      await updateFolderPermissions(folderPermissionsModal.folder.id, {
        inherits_permissions: folderPermsInherit,
        operational_role_ids: folderPermsInherit ? undefined : folderPermsRoleIds,
      })
      setFolderPermissionsModal(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar permisos')
    }
  }

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
      setBrandingPrimaryColor(DEFAULT_PRIMARY_BRAND_COLOR)
      setBrandingSecondaryColor(DEFAULT_SECONDARY_BRAND_COLOR)
      setBrandingMessage('Icono eliminado correctamente. Se restauraron los colores predeterminados.')
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

  if (!workspaceId) {
    return (
      <div className="min-h-screen bg-ink-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-ink-600">Espacio de trabajo no seleccionado</p>
        </div>
      </div>
    )
  }

  const availableTabs = [
    ...(hasAccess
      ? [
          { id: 'general' as const, label: 'General' },
          { id: 'users' as const, label: 'Usuarios' },
          { id: 'roles' as const, label: 'Roles operativos' },
          { id: 'folders' as const, label: 'Carpetas' },
          { id: 'subscription' as const, label: 'Suscripción' },
          { id: 'limits' as const, label: 'Límites y Uso' },
        ]
      : []),
    ...(canManageBranding ? [{ id: 'branding' as const, label: 'Personalización' }] : []),
  ]

  const hasAnyAccess = hasAccess || canManageBranding

  if (!loadingEditPerm && !loadingRole && !hasAnyAccess) {
    return (
      <div className="min-h-screen bg-ink-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-danger-bg border border-danger-bd rounded-lg p-6">
            <h2 className="text-xl font-semibold text-danger mb-2">
              Acceso no autorizado
            </h2>
            <p className="text-danger mb-4">
              No tienes permisos para acceder a la configuración del espacio de trabajo.
            </p>
            <p className="text-sm text-danger mb-4">
              Solo los roles autorizados pueden acceder a esta página o a la sección de personalización.
            </p>
            <button
              onClick={() => router.push('/workspace')}
              className="px-4 py-2 bg-danger text-white rounded-md hover:bg-danger font-medium"
            >
              Volver al workspace
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-ink-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-h1 text-ink-900">Configuración del Espacio de Trabajo</h1>
          <p className="mt-2 text-sm text-ink-600">
            Gestiona la configuración, usuarios, suscripción y límites del espacio de trabajo
          </p>
        </div>

        {error && (
          <div
            className="mb-4 bg-danger-bg border border-danger-bd text-danger px-4 py-3 rounded relative"
            role="alert"
          >
            <span className="block sm:inline">{error}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-white shadow rounded-lg mb-6">
          <div className="border-b border-ink-200">
            <nav className="flex -mb-px">
              {availableTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as ActiveTab)}
                  className={`${
                    activeTab === tab.id
                      ? 'border-accent text-accent'
                      : 'border-transparent text-ink-500 hover:text-ink-700 hover:border-ink-300'
                  } whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'general' && hasAccess && workspaceId && (
              <GeneralSettingsTab
                key={workspaceId}
                workspaceId={workspaceId}
                canEdit={canEditGeneralSettings}
                hubUrl={hubUrl}
              />
            )}

            {activeTab === 'users' && hasAccess && (
              <UsersSettingsTab
                members={members}
                operationalRoles={operationalRoles}
                canManageUsers={canManageUsers}
                editingMemberId={editingMemberId}
                memberRoleIds={memberRoleIds}
                onOpenMemberEdit={openMemberEdit}
                onMemberRoleIdsChange={setMemberRoleIds}
                onSaveMemberRoles={handleSaveMemberRoles}
                onCancelEdit={() => setEditingMemberId(null)}
              />
            )}

            {activeTab === 'roles' && (
              <RolesSettingsTab
                workspaceId={workspaceId}
                operationalRoles={operationalRoles}
                newRoleName={newRoleName}
                newRoleDescription={newRoleDescription}
                onNewRoleNameChange={setNewRoleName}
                onNewRoleDescriptionChange={setNewRoleDescription}
                onCreateRole={handleCreateRole}
                onDeleteRole={handleDeleteRole}
                onGoToUsers={() => setActiveTab('users')}
              />
            )}

            {activeTab === 'folders' && workspaceId && (
              <FoldersSettingsTab
                workspaceId={workspaceId}
                folders={folders}
                operationalRoles={operationalRoles}
                folderPermissionsModal={folderPermissionsModal}
                folderPermsInherit={folderPermsInherit}
                folderPermsRoleIds={folderPermsRoleIds}
                onFoldersChange={reloadFolders}
                onOpenFolderPermissions={openFolderPermissions}
                onFolderPermsInheritChange={setFolderPermsInherit}
                onFolderPermsRoleIdsChange={setFolderPermsRoleIds}
                onSaveFolderPermissions={saveFolderPermissions}
                onCloseFolderPermissionsModal={() => setFolderPermissionsModal(null)}
              />
            )}

            {activeTab === 'subscription' && hasAccess && workspaceId && (
              <SubscriptionSettingsTab workspaceId={workspaceId} />
            )}

            {activeTab === 'limits' && hasAccess && workspaceId && (
              <LimitsSettingsTab workspaceId={workspaceId} />
            )}

            {activeTab === 'branding' && canManageBranding && (
              <BrandingSettingsTab
                brandingIconUrl={brandingIconUrl}
                brandingPrimaryColor={brandingPrimaryColor}
                brandingSecondaryColor={brandingSecondaryColor}
                brandingSaving={brandingSaving}
                brandingMessage={brandingMessage}
                onFileChange={handleBrandingFileChange}
                onDeleteIcon={handleDeleteBrandingIcon}
                onPrimaryColorChange={setBrandingPrimaryColor}
                onSecondaryColorChange={setBrandingSecondaryColor}
                onSaveColors={handleSaveBrandingColors}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
