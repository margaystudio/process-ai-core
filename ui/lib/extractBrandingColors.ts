/**
 * Utilidad de extracción de colores dominantes desde un icono de branding.
 *
 * La función pura `extractColorsFromPixels` trabaja solo con el array de píxeles
 * (Uint8ClampedArray o Array<number> en formato RGBA) y se puede testear en node
 * sin DOM.
 *
 * El wrapper `extractBrandingColors` recibe un File, carga la imagen en un canvas
 * del browser y delega en la función pura.
 */

export type BrandingColors = { primary: string; secondary: string }

/** Convierte un triplete RGB a hex mayúscula ej: "#2A4FFF" */
function toHex([r, g, b]: [number, number, number]): string {
  return (
    '#' +
    [r, g, b]
      .map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, '0'))
      .join('')
      .toUpperCase()
  )
}

function distance(a: [number, number, number], b: [number, number, number]): number {
  return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)
}

/**
 * Función pura — sin acceso a DOM.
 *
 * @param pixels  Array plano de bytes en formato RGBA (longitud múltiplo de 4).
 *                Acepta Uint8ClampedArray o Array<number> para facilitar tests.
 * @returns       Colores primario y secundario en hex, o lanza si no hay colores.
 */
export function extractColorsFromPixels(
  pixels: Uint8ClampedArray | number[]
): BrandingColors {
  const buckets = new Map<string, { count: number; rgb: [number, number, number] }>()

  for (let i = 0; i < pixels.length; i += 4) {
    const alpha = pixels[i + 3]
    if (alpha < 64) continue

    const r = pixels[i]
    const g = pixels[i + 1]
    const b = pixels[i + 2]
    const max = Math.max(r, g, b)
    const min = Math.min(r, g, b)
    const saturation = max === 0 ? 0 : (max - min) / max
    const brightness = (r + g + b) / 3

    // Ignorar blancos/grises muy neutros que suelen ser fondo.
    if (brightness > 245 || (saturation < 0.12 && brightness > 210)) continue

    const qr = Math.round(r / 32) * 32
    const qg = Math.round(g / 32) * 32
    const qb = Math.round(b / 32) * 32
    const key = `${qr},${qg},${qb}`
    const existing = buckets.get(key)
    if (existing) {
      existing.count += 1
    } else {
      buckets.set(key, { count: 1, rgb: [qr, qg, qb] })
    }
  }

  const colors = [...buckets.values()].sort((a, b) => b.count - a.count)
  if (colors.length === 0) {
    throw new Error('No se pudieron detectar colores en el icono')
  }

  const primary = colors[0].rgb
  const secondary =
    colors.find((c) => distance(c.rgb, primary) > 80)?.rgb ||
    colors[Math.min(1, colors.length - 1)].rgb

  return { primary: toHex(primary), secondary: toHex(secondary) }
}

/**
 * Wrapper con plomería DOM: carga el File en un canvas escalado a 64×64
 * y delega en `extractColorsFromPixels`.
 */
export function extractBrandingColors(file: File): Promise<BrandingColors> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        if (!ctx) {
          reject(new Error('No se pudo analizar el icono'))
          return
        }

        const maxSize = 64
        const scale = Math.min(maxSize / img.width, maxSize / img.height, 1)
        canvas.width = Math.max(1, Math.round(img.width * scale))
        canvas.height = Math.max(1, Math.round(img.height * scale))
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

        const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height)

        try {
          resolve(extractColorsFromPixels(data))
        } catch (err) {
          reject(err)
        }
      }
      img.onerror = () => reject(new Error('No se pudo leer el icono'))
      img.src = String(reader.result)
    }
    reader.onerror = () => reject(new Error('No se pudo procesar el icono'))
    reader.readAsDataURL(file)
  })
}
