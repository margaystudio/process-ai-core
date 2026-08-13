/** @type {import('next').NextConfig} */

// Orígenes a los que el navegador tiene que poder hablarle: la API del módulo y
// Supabase (auth). Son NEXT_PUBLIC_* y por lo tanto están disponibles en build,
// que es cuando se hornean estas cabeceras.
const API_URL = process.env.NEXT_PUBLIC_API_URL || ''
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const HUB_URL = process.env.NEXT_PUBLIC_HUB_URL || ''

const connectSrc = ["'self'", API_URL, SUPABASE_URL, HUB_URL].filter(Boolean).join(' ')

/**
 * Content-Security-Policy: la red de contención del XSS.
 *
 * El cuerpo de un documento es HTML que escriben los usuarios y que se le
 * muestra a otro (el aprobador). El saneo con DOMPurify (`lib/sanitizeHtml.ts`)
 * es la barrera principal; esto es la segunda, para el día que aparezca un
 * bypass del sanitizador o un `dangerouslySetInnerHTML` nuevo sin saneo.
 *
 * Sobre `unsafe-inline` en script-src: el App Router de Next 14 inyecta el
 * payload de hidratación en tags `<script>` inline sin nonce (el soporte de
 * nonce requiere middleware que reescriba cada respuesta, incompatible con las
 * rutas estáticas prerenderizadas de este módulo). Sin `unsafe-inline` la app
 * no hidrata. Se acota el daño con el resto: `object-src 'none'`,
 * `base-uri 'self'` (evita secuestrar rutas relativas) y `frame-ancestors
 * 'none'` (evita clickjacking). Cuando este módulo pase a Next 15 con nonces,
 * sacar el `unsafe-inline`.
 *
 * `style-src` con `unsafe-inline`: Tailwind y los estilos inline de Next lo
 * necesitan. El riesgo de CSS inline es bajo y el sanitizador ya elimina el
 * atributo `style` del contenido de documento.
 *
 * `img-src` con `data:` y `blob:`: el QR y los previews de PDF (que se sirven
 * como blob URL tras un fetch autenticado) los necesitan.
 */
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "frame-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // lucide-react se importa como barrel en decenas de archivos (incluido el
    // layout raíz). Next 14.0 no lo optimiza por defecto: sin esto, cada import
    // arrastra el barrel completo (peor en dev: compilación por-módulo).
    optimizePackageImports: ['lucide-react'],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          // El navegador no adivina el tipo: un archivo servido como imagen no
          // se ejecuta como HTML aunque su contenido lo parezca.
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ]
  },
}

module.exports = nextConfig
