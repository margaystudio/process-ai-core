'use client'

import Link from 'next/link'
import {
  WORKSPACE_PROFILE_BANNER_MESSAGE,
  workspaceSettingsGeneralUrl,
} from '@/lib/workspaceProfile'

type WorkspaceProfileBannerProps = {
  workspaceId: string
  canEditSettings?: boolean
  className?: string
}

export default function WorkspaceProfileBanner({
  workspaceId,
  canEditSettings = true,
  className = '',
}: WorkspaceProfileBannerProps) {
  const settingsUrl = workspaceSettingsGeneralUrl(workspaceId)

  return (
    <div
      className={`rounded-md border border-warning-bd bg-warning-bg px-4 py-3 text-sm text-warning flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${className}`}
      role="status"
    >
      <p>{WORKSPACE_PROFILE_BANNER_MESSAGE}</p>
      <Link
        href={settingsUrl}
        className="inline-flex shrink-0 items-center justify-center rounded-md bg-warning-bg px-3 py-1.5 text-sm font-medium text-warning hover:bg-warning-bg border border-warning-bd"
      >
        {canEditSettings ? 'Completar configuración' : 'Ver configuración'}
      </Link>
    </div>
  )
}
