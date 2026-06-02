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
      className={`rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${className}`}
      role="status"
    >
      <p>{WORKSPACE_PROFILE_BANNER_MESSAGE}</p>
      <Link
        href={settingsUrl}
        className="inline-flex shrink-0 items-center justify-center rounded-md bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-200 border border-amber-300"
      >
        {canEditSettings ? 'Completar configuración' : 'Ver configuración'}
      </Link>
    </div>
  )
}
