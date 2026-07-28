import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api-auth', () => ({
  getAuthHeaders: vi.fn().mockResolvedValue({
    'Content-Type': 'application/json',
    Authorization: 'Bearer test-token',
    'X-Active-Tenant-Id': 'tenant-1',
  }),
  authFetch: vi.fn((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init)),
}))

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('semantic API client', () => {
  beforeEach(() => {
    global.fetch = vi.fn()
  })

  it('uploads evidence as multipart while preserving auth and tenant headers', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        status: 'done',
        extracted_text: 'Contenido del proceso',
        metadata: { language: 'es' },
        error: null,
      })
    )

    const { processEvidenceFile } = await import('../api')
    const file = new File(['Contenido del proceso'], 'proceso.txt', {
      type: 'text/plain',
    })

    await processEvidenceFile(file, 'text')

    expect(fetch).toHaveBeenCalledTimes(1)
    const [, request] = vi.mocked(fetch).mock.calls[0]
    const headers = new Headers(request?.headers)
    const formData = request?.body as FormData

    expect(request?.method).toBe('POST')
    expect(headers.get('Content-Type')).toBeNull()
    expect(headers.get('Authorization')).toBe('Bearer test-token')
    expect(headers.get('X-Active-Tenant-Id')).toBe('tenant-1')
    expect(formData).toBeInstanceOf(FormData)
    expect(formData.get('kind')).toBe('text')
    expect((formData.get('file') as File).name).toBe('proceso.txt')
  })

  it('loads relations from the real semantic.py route and filters status locally', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        document_id: 'doc/123',
        groups: [
          {
            relation_type: 'usa',
            items: [
              { id: 'candidate-1', status: 'candidate' },
              { id: 'confirmed-1', status: 'confirmed' },
            ],
          },
          {
            relation_type: 'genera',
            items: [{ id: 'confirmed-2', status: 'confirmed' }],
          },
        ],
      })
    )

    const { getDocumentRelations } = await import('../api')
    const result = await getDocumentRelations('doc/123', 'candidate')

    expect(fetch).toHaveBeenCalledWith(
      `${API_URL}/api/v1/documents/doc%2F123/relations`,
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token',
          'X-Active-Tenant-Id': 'tenant-1',
        }),
      })
    )
    expect(result.groups).toEqual([
      {
        relation_type: 'usa',
        items: [{ id: 'candidate-1', status: 'candidate' }],
      },
    ])
  })

  it('uses the exact methods, paths, queries and payloads for semantic actions', async () => {
    const mockFetch = vi.mocked(fetch)
    mockFetch.mockImplementation(async () => jsonResponse({}))

    const {
      suggestDocumentRelations,
      confirmRelation,
      rejectRelation,
      editRelation,
      searchKnowledgeObjects,
      createKnowledgeObject,
      mergeKnowledgeObject,
      getDocumentImpact,
    } = await import('../api')

    await suggestDocumentRelations('doc-1')
    await confirmRelation('rel-1')
    await rejectRelation('rel-2')
    await editRelation('rel-3', {
      relation_type: 'requiere',
      target_type: 'sistema',
      target_id: 'ko-1',
    })
    await searchKnowledgeObjects({ type: 'sistema', q: ' SAP ERP ' })
    await createKnowledgeObject({
      type: 'sistema',
      canonical_name: 'SAP ERP',
      description: 'Sistema de gestión',
    })
    await mergeKnowledgeObject('ko-duplicate', { into_id: 'ko-canonical' })
    await getDocumentImpact('doc-1')

    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      `${API_URL}/api/v1/documents/doc-1/relations/suggest`,
      expect.objectContaining({ method: 'POST', body: '{}' })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      `${API_URL}/api/v1/relations/rel-1/confirm`,
      expect.objectContaining({ method: 'POST', body: '{}' })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      3,
      `${API_URL}/api/v1/relations/rel-2/reject`,
      expect.objectContaining({ method: 'POST', body: '{}' })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      4,
      `${API_URL}/api/v1/relations/rel-3`,
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          relation_type: 'requiere',
          target_type: 'sistema',
          target_id: 'ko-1',
        }),
      })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      5,
      `${API_URL}/api/v1/knowledge-objects?type=sistema&q=SAP+ERP`,
      expect.any(Object)
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      6,
      `${API_URL}/api/v1/knowledge-objects`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          type: 'sistema',
          canonical_name: 'SAP ERP',
          description: 'Sistema de gestión',
        }),
      })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      7,
      `${API_URL}/api/v1/knowledge-objects/ko-duplicate/merge`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ into_id: 'ko-canonical' }),
      })
    )
    expect(mockFetch).toHaveBeenNthCalledWith(
      8,
      `${API_URL}/api/v1/documents/doc-1/impact`,
      expect.any(Object)
    )
  })

  it('loads the paginated workspace inbox with relation and folder filters', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      jsonResponse({
        items: [],
        total: 0,
        page: 2,
        page_size: 25,
        total_pages: 0,
      })
    )

    const { getWorkspaceRelations } = await import('../api')
    const result = await getWorkspaceRelations({
      status: 'candidate',
      type: 'requiere',
      folder_id: 'folder/ops',
      page: 2,
      page_size: 25,
    })

    expect(fetch).toHaveBeenCalledWith(
      `${API_URL}/api/v1/relations?status=candidate&page=2&page_size=25&type=requiere&folder_id=folder%2Fops`,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
    expect(result).toEqual({
      items: [],
      total: 0,
      page: 2,
      page_size: 25,
      total_pages: 0,
    })
  })
})
