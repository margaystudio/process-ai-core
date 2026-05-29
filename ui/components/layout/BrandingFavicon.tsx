'use client'

import { useEffect } from 'react'
import { useWorkspace } from '@/contexts/WorkspaceContext'

const DEFAULT_FAVICON = '/margay-logo.png'

function ensureIconLink(rel: string) {
  let link = document.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null
  if (!link) {
    link = document.createElement('link')
    link.rel = rel
    document.head.appendChild(link)
  }
  return link
}

export default function BrandingFavicon() {
  const { selectedWorkspace } = useWorkspace()

  useEffect(() => {
    const faviconHref = selectedWorkspace?.branding_icon_url || DEFAULT_FAVICON
    const iconLink = ensureIconLink('icon')
    const shortcutLink = ensureIconLink('shortcut icon')

    iconLink.href = faviconHref
    shortcutLink.href = faviconHref
    iconLink.type = faviconHref.endsWith('.svg') ? 'image/svg+xml' : 'image/png'
    shortcutLink.type = iconLink.type
  }, [selectedWorkspace?.branding_icon_url])

  return null
}
