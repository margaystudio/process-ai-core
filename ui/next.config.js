/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // lucide-react se importa como barrel en decenas de archivos (incluido el
    // layout raíz). Next 14.0 no lo optimiza por defecto: sin esto, cada import
    // arrastra el barrel completo (peor en dev: compilación por-módulo).
    optimizePackageImports: ['lucide-react'],
  },
}

module.exports = nextConfig



