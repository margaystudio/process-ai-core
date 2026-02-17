/**
 * Helpers para validación del modal de subida de archivos.
 * Usado por FileUploadModal y por tests.
 */

export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024 // 25 MB

export type FileType = 'audio' | 'video' | 'image' | 'text'

const EXTENSIONS_BY_TYPE: Record<FileType, string[]> = {
  audio: ['.m4a', '.mp3', '.wav'],
  text: ['.txt', '.md'],
  image: ['.png', '.jpg', '.jpeg', '.webp'],
  video: ['.mp4', '.mov', '.mkv'],
}

export function getFileExtension(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

export function fileMatchesType(file: File, fileType: FileType): boolean {
  const ext = getFileExtension(file.name)
  const allowed = EXTENSIONS_BY_TYPE[fileType] ?? []
  return allowed.some((e) => e.toLowerCase() === ext)
}

export function isFileOverSize(file: File): boolean {
  return file.size > MAX_FILE_SIZE_BYTES
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }
  return `${(bytes / 1024).toFixed(1)} KB`
}
