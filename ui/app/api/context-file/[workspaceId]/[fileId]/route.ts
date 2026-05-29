/**
 * Proxy para visualizar archivos de contexto (PDF, etc.) con Content-Disposition: inline.
 * Usa la sesión de Supabase para autenticarse con el backend.
 */

import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ workspaceId: string; fileId: string }> }
) {
  const { workspaceId, fileId } = await params

  if (!workspaceId || !fileId) {
    return NextResponse.json({ error: 'Parámetros inválidos' }, { status: 400 })
  }

  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()

  if (!session?.access_token) {
    return NextResponse.json({ error: 'No autenticado' }, { status: 401 })
  }

  const backendUrl = `${API_URL}/api/v1/workspaces/${workspaceId}/context-files/${fileId}/view`

  const res = await fetch(backendUrl, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
  })

  if (!res.ok) {
    return NextResponse.json(
      { error: res.status === 404 ? 'Archivo no encontrado' : 'Error al cargar' },
      { status: res.status }
    )
  }

  const buffer = await res.arrayBuffer()
  const contentType = res.headers.get('content-type') || 'application/octet-stream'
  const contentDisposition = res.headers.get('content-disposition') || 'inline'

  const newHeaders = new Headers()
  newHeaders.set('Content-Type', contentType)
  newHeaders.set('Content-Disposition', contentDisposition)
  newHeaders.set('Cache-Control', 'no-store')

  return new NextResponse(buffer, {
    status: 200,
    headers: newHeaders,
  })
}
