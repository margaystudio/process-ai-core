'use client'

import { useEffect, useMemo } from 'react'
import type { CSSProperties } from 'react'
import type { WorkspaceResponse } from '@/lib/api'

const DEFAULT_PRIMARY_BRAND_COLOR = '#2563EB'

function hexToRgb(hex: string) {
  const normalized = hex.replace('#', '')
  const value = normalized.length === 3
    ? normalized.split('').map((char) => char + char).join('')
    : normalized
  const int = Number.parseInt(value, 16)

  return {
    r: (int >> 16) & 255,
    g: (int >> 8) & 255,
    b: int & 255,
  }
}

export function useBrandingTheme(workspace: WorkspaceResponse | null) {
  const primaryBrandColor = workspace?.branding_primary_color || DEFAULT_PRIMARY_BRAND_COLOR
  const secondaryBrandColor = workspace?.branding_secondary_color || primaryBrandColor

  const brandTextStyle = useMemo<CSSProperties>(() => {
    if (primaryBrandColor === secondaryBrandColor) {
      return { color: primaryBrandColor }
    }

    return {
      backgroundImage: `linear-gradient(90deg, ${primaryBrandColor}, ${secondaryBrandColor})`,
      WebkitBackgroundClip: 'text',
      backgroundClip: 'text',
      color: 'transparent',
    }
  }, [primaryBrandColor, secondaryBrandColor])

  useEffect(() => {
    const root = document.documentElement
    const primary = hexToRgb(primaryBrandColor)
    const secondary = hexToRgb(secondaryBrandColor)

    root.style.setProperty('--brand-primary', primaryBrandColor)
    root.style.setProperty('--brand-secondary', secondaryBrandColor)
    root.style.setProperty('--brand-primary-soft', `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.12)`)
    root.style.setProperty('--brand-primary-soft-strong', `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.18)`)
    root.style.setProperty('--brand-primary-soft-subtle', `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.08)`)
    root.style.setProperty('--brand-primary-border', `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.32)`)
    root.style.setProperty('--brand-focus-ring', `rgba(${primary.r}, ${primary.g}, ${primary.b}, 0.35)`)
    root.style.setProperty('--brand-secondary-soft', `rgba(${secondary.r}, ${secondary.g}, ${secondary.b}, 0.14)`)
  }, [primaryBrandColor, secondaryBrandColor])

  return {
    primaryBrandColor,
    secondaryBrandColor,
    brandTextStyle,
  }
}
