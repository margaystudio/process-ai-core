'use client'

/**
 * Overlay de carga global con el logo del margay girando.
 * 
 * Se muestra cuando hay operaciones en progreso y bloquea la pantalla.
 */

export default function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-[9999] bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white rounded-lg p-8 shadow-xl flex flex-col items-center space-y-4">
        {/* Logo del margay girando */}
        <div className="relative">
          <img
            src="/margay-logo.png"
            alt="Loading..."
            className="h-16 w-16 object-contain animate-spin"
            onError={(e) => {
              // Fallback a SVG si la imagen no existe
              const target = e.target as HTMLImageElement
              target.style.display = 'none'
              const fallback = target.nextElementSibling as HTMLElement
              if (fallback) {
                fallback.style.display = 'block'
              }
            }}
          />
          {/* Fallback SVG de margay girando si la imagen no existe */}
          <svg
            className="h-16 w-16 animate-spin"
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: 'none' }}
          >
            {/* Cabeza del margay */}
            <circle cx="50" cy="40" r="25" fill="#8B7355" stroke="#654321" strokeWidth="2"/>
            {/* Orejas */}
            <path d="M35 25 L30 15 L40 20 Z" fill="#8B7355" stroke="#654321" strokeWidth="1.5"/>
            <path d="M65 25 L70 15 L60 20 Z" fill="#8B7355" stroke="#654321" strokeWidth="1.5"/>
            {/* Ojos */}
            <circle cx="43" cy="38" r="3" fill="#000"/>
            <circle cx="57" cy="38" r="3" fill="#000"/>
            {/* Nariz */}
            <path d="M50 45 L48 50 L52 50 Z" fill="#000"/>
            {/* Manchas características del margay */}
            <ellipse cx="45" cy="50" rx="4" ry="6" fill="#654321" opacity="0.6"/>
            <ellipse cx="55" cy="50" rx="4" ry="6" fill="#654321" opacity="0.6"/>
            <ellipse cx="50" cy="60" rx="5" ry="3" fill="#654321" opacity="0.6"/>
          </svg>
        </div>
        <p className="text-gray-700 font-medium">Procesando...</p>
      </div>
    </div>
  )
}



