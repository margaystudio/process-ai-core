import { describe, expect, it } from 'vitest'
import {
  TIPO_DOCUMENTAL_POR_DEFECTO,
  consecuenciaImportacion,
  resolverTipoPorDefecto,
  tipoEfectivoDeFila,
  tipoRequiereAprobacion,
} from '@/lib/importDocumentType'
import type { DocumentType, FolderGovernance } from '@/lib/api'

function governance(value: string | null, origin: FolderGovernance['default_document_type']['origin'] = 'base'): FolderGovernance {
  return {
    default_document_type: { value, origin, from: null },
    tyto_enabled: { value: null, origin: 'base', from: null },
    allow_document_override: { value: true, origin: 'personalizado' },
  }
}

function documentType(key: string, aprobacion: boolean): DocumentType {
  return {
    id: `dt-${key}`,
    key,
    label: key,
    prompt_text: null,
    behaviors: { aprobacion },
    is_active: true,
    sort_order: 0,
    origin: 'default',
    icon: null,
    color: null,
  }
}

describe('resolverTipoPorDefecto', () => {
  it('usa el default_document_type de la carpeta (o el heredado) cuando lo hay', () => {
    expect(resolverTipoPorDefecto(governance('presupuesto', 'heredado'))).toBe('presupuesto')
  })

  it('cae al tipo por defecto del backend si la carpeta no define nada', () => {
    expect(resolverTipoPorDefecto(governance(null))).toBe(TIPO_DOCUMENTAL_POR_DEFECTO)
  })

  it('cae al tipo por defecto del backend si todavía no hay gobierno (sin carpeta elegida)', () => {
    expect(resolverTipoPorDefecto(null)).toBe(TIPO_DOCUMENTAL_POR_DEFECTO)
    expect(resolverTipoPorDefecto(undefined)).toBe(TIPO_DOCUMENTAL_POR_DEFECTO)
  })
})

describe('tipoEfectivoDeFila', () => {
  it('usa el override de la fila si el usuario lo pisó', () => {
    expect(tipoEfectivoDeFila('presupuesto', 'procedimiento')).toBe('presupuesto')
  })

  it('cae al default del lote si la fila no tiene override', () => {
    expect(tipoEfectivoDeFila(null, 'procedimiento')).toBe('procedimiento')
    expect(tipoEfectivoDeFila(undefined, 'procedimiento')).toBe('procedimiento')
  })
})

describe('tipoRequiereAprobacion', () => {
  const tipos = [documentType('procedimiento', true), documentType('manual_externo', false)]

  it('lee el behavior aprobacion del tipo', () => {
    expect(tipoRequiereAprobacion('procedimiento', tipos)).toBe(true)
    expect(tipoRequiereAprobacion('manual_externo', tipos)).toBe(false)
  })

  it('asume que requiere aprobación si el tipo no está (todavía no cargó o no existe)', () => {
    expect(tipoRequiereAprobacion('inexistente', tipos)).toBe(true)
    expect(tipoRequiereAprobacion('procedimiento', [])).toBe(true)
  })
})

describe('consecuenciaImportacion', () => {
  it('describe la consecuencia en palabras de quien usa la pantalla', () => {
    expect(consecuenciaImportacion(true)).toBe('Va a pedir aprobación antes de quedar vigente')
    expect(consecuenciaImportacion(false)).toBe('Va a quedar vigente y consultable de inmediato')
  })
})
