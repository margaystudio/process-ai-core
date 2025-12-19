interface ProcessNameInputProps {
  value: string
  onChange: (value: string) => void
}

export default function ProcessNameInput({ value, onChange }: ProcessNameInputProps) {
  return (
    <div>
      <label htmlFor="process_name" className="block text-sm font-medium text-gray-700 mb-2">
        Nombre del Proceso *
      </label>
      <input
        type="text"
        id="process_name"
        name="process_name"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        placeholder="Ej: Recepción de mercadería"
      />
    </div>
  )
}

