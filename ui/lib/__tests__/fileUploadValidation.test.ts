/**
 * Tests para validación de subida de archivos.
 * Ejecutar con: npx vitest run lib/__tests__/fileUploadValidation.test.ts
 */
import { describe, it, expect } from 'vitest'
import {
  getFileExtension,
  fileMatchesType,
  isFileOverSize,
  formatFileSize,
  MAX_FILE_SIZE_BYTES,
  type FileType,
} from '../fileUploadValidation'

describe('getFileExtension', () => {
  it('returns extension in lowercase', () => {
    expect(getFileExtension('audio.m4a')).toBe('.m4a')
    expect(getFileExtension('Doc.PDF')).toBe('.pdf')
  })
  it('returns empty string when no extension', () => {
    expect(getFileExtension('sinExtension')).toBe('')
  })
})

describe('fileMatchesType', () => {
  const makeFile = (name: string, size = 1000) => new File([new Blob(['x'])], name, { type: 'application/octet-stream' })

  it('accepts audio extensions for type audio', () => {
    expect(fileMatchesType(makeFile('a.m4a'), 'audio')).toBe(true)
    expect(fileMatchesType(makeFile('a.mp3'), 'audio')).toBe(true)
    expect(fileMatchesType(makeFile('a.wav'), 'audio')).toBe(true)
    expect(fileMatchesType(makeFile('a.mp4'), 'audio')).toBe(false)
  })
  it('accepts document extensions for type text', () => {
    expect(fileMatchesType(makeFile('a.txt'), 'text')).toBe(true)
    expect(fileMatchesType(makeFile('a.md'), 'text')).toBe(true)
    expect(fileMatchesType(makeFile('a.pdf'), 'text')).toBe(false)
  })
  it('accepts image extensions for type image', () => {
    expect(fileMatchesType(makeFile('a.png'), 'image')).toBe(true)
    expect(fileMatchesType(makeFile('a.JPEG'), 'image')).toBe(true)
    expect(fileMatchesType(makeFile('a.gif'), 'image')).toBe(false)
  })
  it('accepts video extensions for type video', () => {
    expect(fileMatchesType(makeFile('a.mp4'), 'video')).toBe(true)
    expect(fileMatchesType(makeFile('a.mov'), 'video')).toBe(true)
    expect(fileMatchesType(makeFile('a.m4a'), 'video')).toBe(false)
  })
})

describe('isFileOverSize', () => {
  it('returns false when file is under limit', () => {
    const file = new File([new Blob(['x'])], 'small.txt', { type: 'text/plain' })
    expect(file.size).toBeLessThanOrEqual(MAX_FILE_SIZE_BYTES)
    expect(isFileOverSize(file)).toBe(false)
  })
  it('returns true when file exceeds limit', () => {
    const file = new File([new Blob(['x'])], 'big.bin', { type: 'application/octet-stream' })
    Object.defineProperty(file, 'size', { value: MAX_FILE_SIZE_BYTES + 1, configurable: true })
    expect(isFileOverSize(file)).toBe(true)
  })
  it('returns false when file equals limit', () => {
    const file = new File([new Blob(['x'])], 'exact.bin', { type: 'application/octet-stream' })
    Object.defineProperty(file, 'size', { value: MAX_FILE_SIZE_BYTES, configurable: true })
    expect(isFileOverSize(file)).toBe(false)
  })
})

describe('formatFileSize', () => {
  it('formats MB for large files', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1.00 MB')
    expect(formatFileSize(25 * 1024 * 1024)).toBe('25.00 MB')
  })
  it('formats KB for smaller files', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB')
    expect(formatFileSize(500)).toBe('0.5 KB')
  })
})
