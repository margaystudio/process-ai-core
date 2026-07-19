'use client'

import { usePathname, useRouter } from 'next/navigation'
import {
  FileText,
  CheckSquare,
  Plus,
  Upload,
  BarChart2,
  Folder,
  List,
  Users,
  Circle,
} from 'lucide-react'
import { AppShell, Topbar, Sidebar, type NavGroup, type TopbarTenant } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUser } from '@/hooks/useUser'
import { createClient } from '@/lib/supabase/client'
import { redirectToHubLogin } from '@/lib/hub-login'
import { clearLocalAuthState } from '@/lib/clear-auth-state'
import { canAdministerWorkspace } from '@/lib/adminGating'

// Páginas fuera del shell del módulo (sin sidebar). El login es del hub (SSO).
const BARE_PREFIXES = ['/login', '/onboarding', '/invitations', '/auth']

function initialsOf(name: string): string {
  const clean = name.trim()
  if (!clean || clean === 'Usuario') return 'U'
  const parts = clean.split(/\s+/)
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
  return clean.slice(0, 2).toUpperCase()
}

export default function ChromeShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { workspaces, selectedWorkspace, selectedWorkspaceId, activeTenantId, platformRoles, setActiveTenantId, currentUser } =
    useWorkspace()
  const user = useUser()

  const isBare = BARE_PREFIXES.some((p) => pathname?.startsWith(p))
  if (isBare) return <>{children}</>

  const displayName = currentUser?.name ?? user?.name ?? user?.email ?? 'Usuario'
  const email = user?.email ?? currentUser?.email ?? ''

  const handleSignOut = async () => {
    try {
      const supabase = createClient()
      await supabase.auth.signOut()
      clearLocalAuthState()
      redirectToHubLogin(false)
    } catch (err) {
      console.error('Error cerrando sesión:', err)
    }
  }

  const go = (path: string) => () => router.push(path)
  const active = (path: string, exact = false) =>
    exact ? pathname === path : Boolean(pathname?.startsWith(path))

  const settingsPath = selectedWorkspaceId
    ? `/workspace/${selectedWorkspaceId}/settings`
    : '/workspace'

  const canAdminister = canAdministerWorkspace({
    platformRoles,
    workspaceRole: selectedWorkspace?.role,
  })

  // Switcher de organización (tenant) en el topbar, como el hub.
  const tenants: TopbarTenant[] = workspaces
    .filter((ws) => ws.tenant_id)
    .map((ws) => ({ id: ws.tenant_id as string, name: ws.name }))

  // Secciones del sidebar — estructura del prototipo
  const groups: NavGroup[] = [
    {
      label: 'Biblioteca',
      items: [
        {
          label: 'Biblioteca',
          icon: <FileText />,
          active: active('/workspace', true),
          onClick: go('/workspace'),
        },
        {
          label: 'Por aprobar',
          icon: <CheckSquare />,
          active: active('/dashboard/approval-queue'),
          onClick: go('/dashboard/approval-queue'),
        },
      ],
    },
    {
      label: 'Crear',
      items: [
        {
          label: 'Nuevo documento',
          icon: <Plus />,
          active: active('/documents/new'),
          onClick: go('/documents/new'),
        },
        {
          label: 'Importar documentación',
          icon: <Upload />,
          // No tiene ruta propia — se abre modal desde Biblioteca
          active: false,
          onClick: go('/workspace'),
        },
      ],
    },
    {
      label: 'Análisis',
      items: [
        {
          label: 'Panel de control',
          icon: <BarChart2 />,
          active: active('/dashboard/view'),
          onClick: go('/dashboard/view'),
        },
      ],
    },
    {
      label: 'Administración',
      items: [
        ...(canAdminister
          ? [
              {
                label: 'Carpetas',
                icon: <Folder />,
                active: active('/folders'),
                onClick: go('/folders'),
              },
            ]
          : []),
        ...(canAdminister
          ? [
              {
                label: 'Tipos de documento',
                icon: <List />,
                active: active('/document-types'),
                onClick: go('/document-types'),
              },
            ]
          : []),
        {
          label: 'Usuarios y roles',
          icon: <Users />,
          active: Boolean(pathname?.includes('/settings')),
          onClick: go(settingsPath),
        },
      ],
    },
    {
      label: 'Asistente',
      items: [
        {
          label: 'Tyto',
          icon: <Circle />,
          // placeholder — pantalla aún no implementada
          active: false,
          onClick: undefined,
        },
      ],
    },
  ]

  return (
    <AppShell
      module="process"
      topbar={
        <Topbar
          module="process"
          title="Process AI"
          user={{ name: displayName, email, initials: initialsOf(displayName) }}
          onLogout={handleSignOut}
          tenants={tenants}
          activeTenantId={activeTenantId ?? undefined}
          onTenantChange={(id) => void setActiveTenantId(id)}
        />
      }
      sidebar={<Sidebar groups={groups} />}
    >
      {children}
    </AppShell>
  )
}
