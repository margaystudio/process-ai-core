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
      className="bg-white border-2 border-gray-200 rounded-lg p-6 hover:border-blue-400 hover:shadow-lg cursor-pointer transition-all"
    >
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4">{description}</p>

      <div className="mb-4">
        <p className="text-xs font-medium text-gray-700 mb-2">✅ Ideal para:</p>
        <ul className="text-xs text-gray-600 space-y-1">
          {idealFor.map((item, index) => (
            <li key={index} className="flex items-start">
              <span className="mr-2">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">{note}</p>
        <button className="mt-3 w-full px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition">
          Usar esta opción
        </button>
      </div>
    </div>
  )
}



