import { redirect } from 'next/navigation'

/**
 * process-ai NO tiene login propio: el login es del hub (SSO).
 * Esta ruta es solo un shim de compatibilidad para cualquier referencia interna a
 * `/login` (logout, sesión expirada, links viejos): redirige al hub.
 *
 * El hub muestra el login si no hay sesión y, si la hay, reenvía al módulo según las
 * apps del usuario (Caso B del SSO). Así un logout termina limpio en el hub en vez de
 * en una pantalla de login inexistente.
 */
export default function LoginRedirect() {
  const hub = (process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io').replace(/\/+$/, '')
  redirect(hub)
}
