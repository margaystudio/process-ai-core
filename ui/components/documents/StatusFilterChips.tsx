'use client'

import { cn } from '@/shared/ui/cn'

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
    <div className="flex flex-wrap gap-2">
      {statusOptions.map((option) => (
        <button
          key={option.value || 'all'}
          onClick={() => onStatusChange(option.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm font-semibold transition-colors',
            selectedStatus === option.value
              ? 'bg-action text-action-on shadow-sm'
              : 'bg-ink-100 text-ink-700 hover:bg-ink-150'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
