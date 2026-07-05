import { describe, expect, it } from 'vitest'
import {
  evidenceChips,
  type Evidence,
  type EvidenceChip,
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

/** Helpers para construir chips esperados con menos ruido. */
const s = (label: string): EvidenceChip => ({ label, variant: 'success' })
const n = (label: string): EvidenceChip => ({ label, variant: 'neutral' })

describe('evidenceChips', () => {
  it('returns empty while processing', () => {
    expect(
      evidenceChips(baseEvidence({ processingStatus: 'processing' })),
    ).toEqual([])
  })

  it('returns empty on error', () => {
    expect(
      evidenceChips(baseEvidence({ processingStatus: 'error' })),
    ).toEqual([])
  })

  it('builds audio badges from real metadata', () => {
    expect(
      evidenceChips(
        baseEvidence({
          metadata: { language: 'ES', duration_seconds: 92 },
        }),
      ),
    ).toEqual([s('Audio transcripto'), s('Idioma: ES'), s('1:32')])
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
    ).toEqual([s('Texto extraído'), s('PDF procesado'), s('42 págs'), s('Idioma: ES')])
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
    ).toContainEqual(s('OCR completado'))
  })

  it('shows sin texto for image with no_text status — neutral variant', () => {
    expect(
      evidenceChips(
        baseEvidence({
          tipo: 'Imagen',
          fileType: 'image',
          processingStatus: 'no_text',
        }),
      ),
    ).toEqual([n('Sin texto detectado'), n('1 imagen')])
  })

  it('shows sin audio for audio with no_text status — neutral variant', () => {
    expect(
      evidenceChips(
        baseEvidence({ processingStatus: 'no_text' }),
      ),
    ).toEqual([n('Sin audio detectado')])
  })

  it('shows sin texto for PDF with no_text status — neutral variant', () => {
    expect(
      evidenceChips(
        baseEvidence({
          tipo: 'PDF',
          fileType: 'text',
          processingStatus: 'no_text',
        }),
      ),
    ).toEqual([n('Sin texto detectado')])
  })
})
