/**
 * Tests de la función pura extractColorsFromPixels.
 * No requiere DOM — corre en entorno node (vitest env: node).
 */
import { describe, it, expect } from 'vitest'
import { extractColorsFromPixels } from '../extractBrandingColors'

/**
 * Construye un array RGBA plano con N repeticiones del color dado + alpha.
 */
function pixelsOf(
  r: number,
  g: number,
  b: number,
  alpha = 255,
  count = 10
): number[] {
  const arr: number[] = []
  for (let i = 0; i < count; i++) {
    arr.push(r, g, b, alpha)
  }
  return arr
}

describe('extractColorsFromPixels', () => {
  it('devuelve el color dominante como primario', () => {
    // 20 píxeles rojos + 5 azules
    const pixels = [...pixelsOf(200, 0, 0, 255, 20), ...pixelsOf(0, 0, 200, 255, 5)]
    const { primary } = extractColorsFromPixels(pixels)
    // El bucket rojo (qr=192,qg=0,qb=0) → hex #C00000
    expect(primary).toBe('#C00000')
  })

  it('devuelve un secundario distinto (distancia > 80) cuando existe', () => {
    // Rojo dominante + azul como secundario (distancia euclídea ≫ 80)
    const pixels = [...pixelsOf(200, 0, 0, 255, 20), ...pixelsOf(0, 0, 200, 255, 5)]
    const { primary, secondary } = extractColorsFromPixels(pixels)
    expect(primary).not.toBe(secondary)
    // El secundario debe ser azul cuantizado
    expect(secondary).toBe('#0000C0')
  })

  it('usa el segundo bucket más frecuente como secundario cuando no hay contraste suficiente', () => {
    // Dos tonos de rojo muy parecidos (distancia < 80 entre ellos)
    const pixels = [
      ...pixelsOf(200, 0, 0, 255, 20), // bucket #C00000
      ...pixelsOf(220, 10, 10, 255, 5), // bucket #DC0000 — distancia ~ 21
    ]
    const { primary, secondary } = extractColorsFromPixels(pixels)
    expect(primary).toBe('#C00000')
    // No hay candidato con distancia > 80, cae en colors[1].
    // 220 cuantizado: round(220/32)*32 = 7*32 = 224 = 0xE0
    expect(secondary).toBe('#E00000')
  })

  it('ignora píxeles transparentes (alpha < 64)', () => {
    const pixels = [
      ...pixelsOf(255, 0, 0, 0, 10),  // transparentes → ignorados
      ...pixelsOf(0, 200, 0, 255, 5), // verdes opacos
    ]
    const { primary } = extractColorsFromPixels(pixels)
    expect(primary.startsWith('#00')).toBe(true) // el canal rojo es ~0
  })

  it('ignora blancos/grises muy neutros (posibles fondos)', () => {
    const pixels = [
      ...pixelsOf(255, 255, 255, 255, 50), // blanco puro → filtrado
      ...pixelsOf(0, 100, 200, 255, 5),    // azul saturado → pasa
    ]
    const { primary } = extractColorsFromPixels(pixels)
    // El primario no debe ser blanco
    expect(primary).not.toBe('#FFFFFF')
    expect(primary).not.toBe('#E0E0E0')
  })

  it('lanza si no quedan colores válidos después del filtrado', () => {
    // Solo píxeles blancos neutros que se filtran
    const pixels = pixelsOf(255, 255, 255, 255, 10)
    expect(() => extractColorsFromPixels(pixels)).toThrow(
      'No se pudieron detectar colores en el icono'
    )
  })

  it('maneja un único color disponible (primario = secundario del fallback)', () => {
    const pixels = pixelsOf(100, 50, 200, 255, 5)
    const { primary, secondary } = extractColorsFromPixels(pixels)
    // Solo un bucket → secondary = colors[min(1, 0)] = colors[0] = primary
    expect(primary).toBe(secondary)
  })

  it('acepta Uint8ClampedArray además de Array<number>', () => {
    const arr = new Uint8ClampedArray([200, 0, 0, 255, 200, 0, 0, 255])
    const { primary } = extractColorsFromPixels(arr)
    expect(primary).toBe('#C00000')
  })
})
