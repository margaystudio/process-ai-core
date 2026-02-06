'use client'

interface StatusFilterChipsProps {
  selectedStatus: string | null
  onStatusChange: (status: string | null) => void
}

const statusOptions = [
  { value: null, label: 'Todos' },
  { value: 'pending_validation', label: 'Pendiente' },
  { value: 'draft', label: 'Borrador' },
  { value: 'approved', label: 'Aprobado' },
  { value: 'rejected', label: 'Rechazado' },
]

export default function StatusFilterChips({ selectedStatus, onStatusChange }: StatusFilterChipsProps) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {statusOptions.map((option) => (
        <button
          key={option.value || 'all'}
          onClick={() => onStatusChange(option.value)}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
            selectedStatus === option.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          {option.label}
        </button>
      ))}
      {selectedStatus && (
        <button
          onClick={() => onStatusChange(null)}
          className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800 underline"
        >
          Limpiar filtro
        </button>
      )}
    </div>
  )
}
