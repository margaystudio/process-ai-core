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
  MessageCircle,
  Network,
} from 'lucide-react'
import { PlatformShell, type NavGroup } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUser } from '@/hooks/useUser'
import { useCanManageWorkspace } from '@/hooks/useHasPermission'
import { createClient } from '@/lib/supabase/client'
import { redirectToHubLogin } from '@/lib/hub-login'
import { clearLocalAuthState } from '@/lib/clear-auth-state'
import { MODULO_ACTUAL, hubUrl, modulosParaSwitcher } from '@/lib/modules'

// Páginas fuera del shell del módulo (sin sidebar). El login es del hub (SSO).
const BARE_PREFIXES = ['/login', '/invitations', '/auth']

export default function ChromeShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { workspaces, selectedWorkspaceId, activeTenantId, setActiveTenantId, currentUser, modules } =
    useWorkspace()
  const user = useUser()
  // Hook: debe llamarse siempre, antes del early return de abajo (páginas "bare").
  const { canManage: canAdminister } = useCanManageWorkspace()

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

  // Cliente activo de ESTE módulo (tenant, no confundir con el switcher de módulos):
  // vive en cookie propia (active_tenant_id / X-Active-Tenant-Id), no en la URL.
  const tenants = workspaces
    .filter((ws) => ws.tenant_id)
    .map((ws) => ({ id: ws.tenant_id as string, name: ws.name, slug: ws.slug }))
  const tenant = tenants.find((t) => t.id === activeTenantId)

  // Secciones del sidebar — estructura del prototipo. `href` (además de `onClick`)
  // habilita abrir un ítem en pestaña nueva con ⌘/Ctrl+clic o el botón del medio
  // (margay-ui 0.15.0); el clic normal lo sigue resolviendo la navegación client-side.
  const nav: NavGroup[] = [
    {
      label: 'Biblioteca',
      items: [
        {
          label: 'Biblioteca',
          icon: <FileText />,
          href: '/workspace',
          active: active('/workspace', true),
          onClick: go('/workspace'),
        },
        {
          label: 'Por aprobar',
          icon: <CheckSquare />,
          href: '/dashboard/approval-queue',
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
          href: '/documents/new',
          active: active('/documents/new'),
          onClick: go('/documents/new'),
        },
        ...(canAdminister
          ? [
              {
                label: 'Importar documentación',
                icon: <Upload />,
                href: '/import',
                active: active('/import'),
                onClick: go('/import'),
              },
            ]
          : []),
      ],
    },
    {
      label: 'Análisis',
      items: [
        {
          label: 'Panel de control',
          icon: <BarChart2 />,
          href: '/dashboard/view',
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
                href: '/folders',
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
                href: '/document-types',
                active: active('/document-types'),
                onClick: go('/document-types'),
              },
            ]
          : []),
        ...(canAdminister
          ? [
              {
                label: 'Relaciones',
                icon: <Network />,
                href: '/relations',
                active: active('/relations'),
                onClick: go('/relations'),
              },
            ]
          : []),
        {
          label: 'Usuarios y roles',
          icon: <Users />,
          href: settingsPath,
          active: Boolean(pathname?.includes('/settings')),
          onClick: go(settingsPath),
        },
      ],
    },
    {
      // Tyto es para cualquier staff autenticado del workspace (mismo gate que
      // el backend: sync_workspace_access), no un permiso de administración —
      // por eso este grupo NO usa canAdminister, a diferencia de "Administración".
      label: 'Asistente',
      items: [
        {
          label: 'Tyto',
          icon: <MessageCircle />,
          href: '/tyto',
          active: active('/tyto'),
          onClick: go('/tyto'),
        },
      ],
    },
  ]

  return (
    <PlatformShell
      module={MODULO_ACTUAL}
      modules={modulosParaSwitcher(modules)}
      tenant={tenant}
      tenants={tenants}
      user={{ displayName, email, avatarUrl: user?.avatarUrl ?? undefined }}
      hubUrl={hubUrl()}
      nav={nav}
      onLogout={handleSignOut}
      // El cliente activo de este módulo vive en cookie/contexto, no en la URL: sin
      // este handler el shell no ofrecería selector de cliente.
      onTenantChange={(t) => void setActiveTenantId(t.id)}
    >
      {children}
    </PlatformShell>
  )
}
