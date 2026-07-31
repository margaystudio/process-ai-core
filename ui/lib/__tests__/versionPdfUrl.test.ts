import { describe, expect, it } from 'vitest'

import {
  getVersionFrozenPdfUrl,
  getVersionPdfUrl,
  getVersionPreviewPdfUrl,
  isFrozenVersionStatus,
} from '@/lib/api'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

describe('selección de endpoint de PDF por estado de versión', () => {
  it('APPROVED usa el artefacto congelado (no regenera)', () => {
    expect(getVersionPdfUrl('doc-1', 'ver-1', 'APPROVED')).toBe(
      `${API_URL}/api/v1/documents/doc-1/versions/ver-1/pdf`
    )
    expect(getVersionPdfUrl('doc-1', 'ver-1', 'APPROVED')).toBe(
      getVersionFrozenPdfUrl('doc-1', 'ver-1')
    )
  })

  it.each(['DRAFT', 'IN_REVIEW', 'REJECTED'])('%s usa el preview regenerado', (status) => {
    expect(getVersionPdfUrl('doc-1', 'ver-1', status)).toBe(
      getVersionPreviewPdfUrl('doc-1', 'ver-1')
    )
    expect(getVersionPdfUrl('doc-1', 'ver-1', status)).toContain('/preview-pdf')
  })

  it('OBSOLETE va al preview: el backend redirige si esa versión sí quedó congelada', () => {
    // Pedirle el congelado directo daría 404 en las que nunca se aprobaron.
    expect(getVersionPdfUrl('doc-1', 'ver-1', 'OBSOLETE')).toBe(
      getVersionPreviewPdfUrl('doc-1', 'ver-1')
    )
  })

  it('sin estado conocido cae al preview (comportamiento previo)', () => {
    expect(getVersionPdfUrl('doc-1', 'ver-1')).toBe(getVersionPreviewPdfUrl('doc-1', 'ver-1'))
    expect(getVersionPdfUrl('doc-1', 'ver-1', null)).toBe(
      getVersionPreviewPdfUrl('doc-1', 'ver-1')
    )
  })

  it('isFrozenVersionStatus solo marca APPROVED como inmutable', () => {
    expect(isFrozenVersionStatus('APPROVED')).toBe(true)
    for (const status of ['DRAFT', 'IN_REVIEW', 'REJECTED', 'OBSOLETE', undefined, null]) {
      expect(isFrozenVersionStatus(status)).toBe(false)
    }
  })

  it('las URLs congelada y de preview son endpoints distintos', () => {
    expect(getVersionFrozenPdfUrl('doc-1', 'ver-1')).not.toBe(
      getVersionPreviewPdfUrl('doc-1', 'ver-1')
    )
  })
})
