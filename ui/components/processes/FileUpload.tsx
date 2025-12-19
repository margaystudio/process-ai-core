/**
 * Componente para subir archivos.
 * 
 * Placeholder - me vas a indicar cómo querés que funcione.
 */

interface FileUploadProps {
  label: string
  name: string
  accept?: string
  multiple?: boolean
}

export default function FileUpload({ 
  label, 
  name, 
  accept, 
  multiple = false 
}: FileUploadProps) {
  return (
    <div>
      <label className="block text-sm font-medium mb-2">{label}</label>
      <input
        type="file"
        name={name}
        accept={accept}
        multiple={multiple}
        className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
      />
    </div>
  )
}

