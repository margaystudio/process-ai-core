/**
 * Redirige /processes/new → /documents/new (nueva ruta canónica del flujo de alta).
 * Mantenida para compatibilidad con bookmarks y links externos.
 */
import { redirect } from 'next/navigation'

export default function ProcessesNewRedirect() {
  redirect('/documents/new')
}
