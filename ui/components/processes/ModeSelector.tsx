interface ModeSelectorProps {
  value: 'operativo' | 'gestion'
  onChange: (value: 'operativo' | 'gestion') => void
}

export default function ModeSelector({ value, onChange }: ModeSelectorProps) {
  return (
    <div>
      <label htmlFor="mode" className="block text-sm font-medium text-gray-700 mb-2">
        Modo del Documento *
      </label>
      <select
        id="mode"
        name="mode"
        value={value}
        onChange={(e) => onChange(e.target.value as 'operativo' | 'gestion')}
        required
        className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      >
        <option value="operativo">Operativo (pistero)</option>
        <option value="gestion">Gestión / Dueños</option>
      </select>
      <p className="mt-1 text-sm text-gray-500">
        {value === 'operativo' 
          ? 'Documento corto y práctico para ejecución'
          : 'Documento completo con controles y métricas'}
      </p>
    </div>
  )
}

