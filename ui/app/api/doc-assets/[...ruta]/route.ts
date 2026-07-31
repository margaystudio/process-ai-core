/**
 * Proxy autenticado para los archivos EMBEBIDOS en el contenido de un documento.
 *
 * PRINCIPIO: nada que el navegador pida por su cuenta lleva una credencial en la
 * dirección.
 *
 * Una `<img src="...">` la dispara el navegador solo: ningún JavaScript puede
 * ponerle un header `Authorization`. La solución anterior era firmar la URL, y
 * eso convertía el enlace en un PORTADOR — la API validaba la firma pero no
 * sabía QUIÉN la presentaba, así que no podía aplicar el permiso por carpeta.
 * Cualquiera con el enlace (una captura de pantalla, el historial, "copiar
 * dirección de la imagen") veía material de una carpeta que tenía denegada.
 *
 * Este route handler es la plomería que arregla eso: el front SÍ es del mismo
 * origen que el navegador, así que la `<img>` le manda la cookie de sesión. Acá
 * se valida la sesión, se saca el access token y se llama a la API con
 * `Authorization: Bearer`. La API, que ahora sabe quién pide, verifica el permiso
 * sobre la carpeta del documento — que es lo que de verdad cierra el agujero.
 * Un proxy que solo reenviara, sin ese chequeo del otro lado, no arreglaría nada.
 *
 * Para un archivo suelto que el usuario abre a propósito (un PDF), el patrón es
 * otro: lo pide la pantalla con fetch + Authorization y lo muestra desde un blob
 * URL. Ver el principio completo en api/routes/documents/_helpers.py.
 */

import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Formas de ruta que este proxy acepta reenviar, ancladas de punta a punta.
 *
 * Es una lista blanca y no una validación negativa a propósito: sin ella, esto
 * sería un proxy abierto a cualquier endpoint de la API con la sesión del
 * usuario — incluidos los de escritura, y con el método que el atacante elija.
 * Solo estas tres familias, y solo GET.
 */
const RUTAS_PERMITIDAS = [
  // Assets de una versión: las imágenes que traía adentro un PDF importado.
  /^api\/v1\/documents\/[^/]+\/versions\/[^/]+\/assets\/[^/]+$/,
  // Imágenes subidas desde el editor manual.
  /^api\/v1\/documents\/[^/]+\/editor-images\/[^/]+$/,
  // Assets de un run (capturas de video, evidencia) referenciados por el markdown.
  /^api\/v1\/artifacts\/[^/]+\/assets\/.+$/,
]

/** Headers de la respuesta de la API que se reenvían al navegador. */
const HEADERS_REENVIADOS = [
  'content-type',
  'content-length',
  'content-disposition',
  'cache-control',
  'etag',
]

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ ruta: string[] }> }
) {
  const { ruta } = await params
  const path = ruta.map(encodeURIComponent).join('/')

  if (!RUTAS_PERMITIDAS.some((patron) => patron.test(ruta.join('/')))) {
    return NextResponse.json({ error: 'Ruta no permitida' }, { status: 404 })
  }

  // 401 y NO un redirect al login: el consumidor es una etiqueta <img>, no una
  // navegación. Un 302 acá le devolvería el HTML del login como si fuera la
  // imagen, y el navegador mostraría un ícono roto sin ninguna pista del motivo.
  const supabase = await createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session?.access_token) {
    return NextResponse.json({ error: 'No autenticado' }, { status: 401 })
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  }
  // El tenant activo llega como query param `t` porque una <img> no puede
  // mandar el header que usa el resto de la app. No es una credencial: es el
  // selector de tenant, y la API igual verifica membresía y permiso del usuario
  // autenticado. Sin esto, alguien con varios tenants resolvería el workspace
  // equivocado y su propia imagen le daría 404.
  const tenantId = request.nextUrl.searchParams.get('t')
  if (tenantId) headers['X-Active-Tenant-Id'] = tenantId

  // Revalidación condicional: si el navegador ya tiene la imagen, este
  // round-trip termina en un 304 sin cuerpo. Es lo que hace que verificar el
  // permiso en CADA pedido siga siendo barato.
  const ifNoneMatch = request.headers.get('if-none-match')
  if (ifNoneMatch) headers['If-None-Match'] = ifNoneMatch

  let upstream: Response
  try {
    upstream = await fetch(`${API_URL}/${path}`, {
      headers,
      // El proxy no cachea nada por su cuenta: la respuesta de la API ya trae su
      // propio Cache-Control (`private, no-cache`), y cachear del lado del
      // servidor Next serviría la imagen de un usuario a otro.
      cache: 'no-store',
    })
  } catch {
    return NextResponse.json({ error: 'No se pudo obtener el archivo' }, { status: 502 })
  }

  const responseHeaders = new Headers()
  for (const nombre of HEADERS_REENVIADOS) {
    const valor = upstream.headers.get(nombre)
    if (valor) responseHeaders.set(nombre, valor)
  }

  if (!upstream.ok || upstream.status === 304 || !upstream.body) {
    // Sin cuerpo: 304, o un error cuyo detalle no vale la pena reenviar (el
    // status es lo informativo; el JSON de error de la API no lo ve nadie
    // dentro de una <img>).
    return new NextResponse(null, { status: upstream.status, headers: responseHeaders })
  }

  // STREAMING: se pasa el ReadableStream tal cual, sin `arrayBuffer()`. Una
  // captura de pantalla de un manual pesa megabytes, y bufferearla acá pondría
  // el documento entero en memoria del servidor Next por cada imagen y cada
  // usuario concurrente.
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}
