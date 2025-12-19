interface OptionalFieldsProps {
  audience: string
  detailLevel: string
  formality: string
  onAudienceChange: (value: string) => void
  onDetailLevelChange: (value: string) => void
  onFormalityChange: (value: string) => void
}

export default function OptionalFields({
  audience,
  detailLevel,
  formality,
  onAudienceChange,
  onDetailLevelChange,
  onFormalityChange,
}: OptionalFieldsProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-900">Campos Opcionales</h3>
      <p className="text-sm text-gray-500">
        Estos campos ayudan a personalizar el documento. Si los dejás vacíos, se usarán los valores por defecto.
      </p>

      <div>
        <label htmlFor="audience" className="block text-sm font-medium text-gray-700 mb-2">
          Audiencia
        </label>
        <input
          type="text"
          id="audience"
          name="audience"
          value={audience}
          onChange={(e) => onAudienceChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          placeholder="Ej: direccion, operativo, rrhh"
        />
      </div>

      <div>
        <label htmlFor="detail_level" className="block text-sm font-medium text-gray-700 mb-2">
          Nivel de Detalle
        </label>
        <select
          id="detail_level"
          name="detail_level"
          value={detailLevel}
          onChange={(e) => onDetailLevelChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Seleccionar...</option>
          <option value="breve">Breve</option>
          <option value="estandar">Estándar</option>
          <option value="detallado">Detallado</option>
        </select>
      </div>

      <div>
        <label htmlFor="formality" className="block text-sm font-medium text-gray-700 mb-2">
          Formalidad
        </label>
        <select
          id="formality"
          name="formality"
          value={formality}
          onChange={(e) => onFormalityChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          <option value="">Seleccionar...</option>
          <option value="baja">Baja</option>
          <option value="media">Media</option>
          <option value="alta">Alta</option>
        </select>
      </div>
    </div>
  )
}

