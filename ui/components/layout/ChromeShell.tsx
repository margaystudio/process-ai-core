'use client'

import { usePathname, useRouter } from 'next/navigation'
import {
  FileText,
  ListChecks,
  ClipboardList,
  Eye,
  Plus,
  FlaskConical,
  BookOpen,
  Settings,
  UserCircle,
  Building2,
} from 'lucide-react'
import { AppShell, Topbar, Sidebar, type NavGroup } from '@/shared/ui/components'
import { useWorkspace } from '@/contexts/WorkspaceContext'
import { useUser } from '@/hooks/useUser'
import { createClient } from '@/lib/supabase/client'

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
  const {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    activeTenantId,
    setActiveTenantId,
    currentUser,
  } = useWorkspace()
  const user = useUser()

  const isBare = BARE_PREFIXES.some((p) => pathname?.startsWith(p))
  if (isBare) return <>{children}</>

  const displayName = currentUser?.name ?? user?.name ?? user?.email ?? 'Usuario'
  const email = user?.email ?? currentUser?.email ?? ''

  const handleSignOut = async () => {
    try {
      const supabase = createClient()
      await supabase.auth.signOut()
      localStorage.removeItem('local_user_id')
      router.push('/login')
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

  const groups: NavGroup[] = [
    {
      label: 'Documentos',
      items: [
        { label: 'Documentos', icon: <FileText />, active: active('/workspace', true), onClick: go('/workspace') },
        { label: 'Cola de aprobación', icon: <ListChecks />, active: active('/dashboard/approval-queue'), onClick: go('/dashboard/approval-queue') },
        { label: 'Por revisar', icon: <ClipboardList />, active: active('/dashboard/to-review'), onClick: go('/dashboard/to-review') },
        { label: 'Vista', icon: <Eye />, active: active('/dashboard/view'), onClick: go('/dashboard/view') },
      ],
    },
    {
      label: 'Crear',
      items: [
        { label: 'Nuevo proceso', icon: <Plus />, active: active('/processes/new'), onClick: go('/processes/new') },
        { label: 'Recetas', icon: <FlaskConical />, active: active('/recipes'), onClick: go('/recipes/new') },
      ],
    },
    {
      label: 'Cuenta',
      items: [
        { label: 'Contexto', icon: <BookOpen />, active: active('/workspace/context'), onClick: go('/workspace/context') },
        { label: 'Configuración', icon: <Settings />, active: Boolean(pathname?.includes('/settings')), onClick: go(settingsPath) },
        { label: 'Mi perfil', icon: <UserCircle />, active: active('/profile'), onClick: go('/profile') },
      ],
    },
  ]

  // Switcher de organización (tenant) — solo si el usuario tiene más de una.
  if (workspaces.length > 1) {
    groups.push({
      label: 'Organización',
      items: workspaces.map((ws) => ({
        label: ws.name,
        icon: <Building2 />,
        active: ws.tenant_id === activeTenantId,
        onClick: ws.tenant_id ? () => void setActiveTenantId(ws.tenant_id as string) : undefined,
      })),
    })
  }

  return (
    <AppShell
      module="process"
      topbar={
        <Topbar
          module="process"
          title="Process AI"
          user={{ name: displayName, email, initials: initialsOf(displayName) }}
          onLogout={handleSignOut}
        />
      }
      sidebar={
        <Sidebar
          account={selectedWorkspace?.name ? { name: selectedWorkspace.name } : undefined}
          groups={groups}
        />
      }
    >
      {children}
    </AppShell>
  )
}
