import { describe, expect, it } from 'vitest'
import {
  evidenceChips,
  type Evidence,
} from '../../components/documents/wizard/data'

function baseEvidence(overrides: Partial<Evidence>): Evidence {
  return {
    id: 'e-1',
    tipo: 'Audio',
    fileType: 'audio',
    title: 'Test',
    file: new File([''], 'test.mp3'),
    processingStatus: 'done',
    ...overrides,
  }
}

describe('evidenceChips', () => {
  it('returns empty while processing', () => {
    expect(
      evidenceChips(baseEvidence({ processingStatus: 'processing' })),
    ).toEqual([])
  })

  it('builds audio badges from real metadata', () => {
    expect(
      evidenceChips(
        baseEvidence({
          metadata: { language: 'ES', duration_seconds: 92 },
        }),
      ),
    ).toEqual(['Audio transcripto', 'Idioma: ES', '1:32'])
  })

  it('builds PDF badges with pages and OCR flag', () => {
    expect(
      evidenceChips(
        baseEvidence({
          tipo: 'PDF',
          fileType: 'text',
          metadata: { pages: 42, used_ocr: false, language: 'ES' },
        }),
      ),
    ).toEqual(['Texto extraído', 'PDF procesado', '42 págs', 'Idioma: ES'])
  })

  it('shows OCR badge for scanned PDF', () => {
    expect(
      evidenceChips(
        baseEvidence({
          tipo: 'PDF',
          fileType: 'text',
          metadata: { pages: 8, used_ocr: true },
        }),
      ),
    ).toContain('OCR completado')
  })

  it('shows sin texto for image with no_text status', () => {
    expect(
      evidenceChips(
        baseEvidence({
          tipo: 'Imagen',
          fileType: 'image',
          processingStatus: 'no_text',
        }),
      ),
    ).toEqual(['Sin texto detectado', '1 imagen'])
  })
})
