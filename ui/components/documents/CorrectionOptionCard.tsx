'use client'

interface CorrectionOptionCardProps {
  title: string
  description: string
  idealFor: string[]
  note: string
  onClick: () => void
}

export default function CorrectionOptionCard({
  title,
  description,
  idealFor,
  note,
  onClick,
}: CorrectionOptionCardProps) {
  return (
    <div
      onClick={onClick}
      className="bg-white border-2 border-ink-200 rounded-lg p-6 hover:border-accent hover:shadow-lg cursor-pointer transition-all"
    >
      <h3 className="text-h2 text-ink-900 mb-2">{title}</h3>
      <p className="text-sm text-ink-600 mb-4">{description}</p>

      <div className="mb-4">
        <p className="text-xs font-medium text-ink-700 mb-2">Ideal para:</p>
        <ul className="text-xs text-ink-600 space-y-1">
          {idealFor.map((item, index) => (
            <li key={index} className="flex items-start">
              <span className="mr-2">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-4 border-t border-ink-200">
        <p className="text-xs text-ink-500">{note}</p>
        <button className="mt-3 w-full px-4 py-2 bg-action text-white text-sm rounded-md hover:bg-action-hover transition">
          Usar esta opción
        </button>
      </div>
    </div>
  )
}



