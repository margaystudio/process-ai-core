/**
 * Tests para API de contenido editable (edición manual Tiptap).
 * Ejecutar con: npx vitest run lib/__tests__/editableContent.test.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api-auth', () => ({
  getAccessToken: vi.fn().mockResolvedValue('test-token'),
}))

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

describe('getEditableContent', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('calls GET /documents/:id/editable and returns html', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        version_id: 'v1',
        version_number: 1,
        html: '<p>Hello</p>',
        updated_at: '2025-01-01T12:00:00Z',
      }),
    } as Response)

    const { getEditableContent } = await import('../api')
    const result = await getEditableContent('doc-123')

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_URL}/api/v1/documents/doc-123/editable`,
      expect.objectContaining({ method: 'GET' })
    )
    expect(result.html).toBe('<p>Hello</p>')
    expect(result.version_id).toBe('v1')
  })
})

describe('saveEditableContent', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('calls PUT /documents/:id/editable with content_html', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        version_id: 'v1',
        version_number: 1,
        updated_at: '2025-01-01T12:05:00Z',
      }),
    } as Response)

    const { saveEditableContent } = await import('../api')
    const result = await saveEditableContent('doc-123', '<p>Updated</p>')

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_URL}/api/v1/documents/doc-123/editable`,
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ content_html: '<p>Updated</p>' }),
      })
    )
    expect(result.updated_at).toBe('2025-01-01T12:05:00Z')
  })
})
