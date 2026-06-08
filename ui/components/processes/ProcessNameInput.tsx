import { Field, Input } from '@/shared/ui/components'

interface ProcessNameInputProps {
  value: string
  onChange: (value: string) => void
}

export default function ProcessNameInput({ value, onChange }: ProcessNameInputProps) {
  return (
    <Field label="Nombre del proceso *">
      <Input
        type="text"
        id="process_name"
        name="process_name"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required
        placeholder="Ej: Recepción de mercadería"
      />
    </Field>
  )
}
