// components/tyto/TytoHistorySheet.tsx
// "Lo que pregunté" en /consultar: el mismo panel de conversaciones del hilo
// completo (buscar, retomar, renombrar, anclar, borrar), pero como hoja
// secundaria — nunca compite con la caja de preguntar de la pantalla principal.
'use client'

import { Dialog } from '@/shared/ui/components'
import { TytoConversationsPanel } from './TytoConversationsPanel'
import type { TytoSessionSummary } from '@/lib/api'

export function TytoHistorySheet({
  open,
  onClose,
  ...panelProps
}: {
  open: boolean
  onClose: () => void
  sessions: TytoSessionSummary[]
  loading: boolean
  error: string | null
  onRetry: () => void
  searchValue: string
  onSearchChange: (value: string) => void
  activeSessionId: string | null
  pendingIds: Set<string>
  actionError: string | null
  onDismissActionError: () => void
  onSelect: (session: TytoSessionSummary) => void
  onRename: (session: TytoSessionSummary, title: string) => void
  onTogglePin: (session: TytoSessionSummary) => void
  onDelete: (session: TytoSessionSummary) => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title="Lo que pregunté" maxWidth="max-w-md">
      {/* El Dialog trae su propio padding de body: se cancela acá porque el
          panel arma el suyo (buscador, filas, footer) para calzar con la
          versión de escritorio del hilo completo. Altura fija (no flex-1):
          el panel resuelve su scroll interno solo a partir de un alto concreto. */}
      <div className="-mx-5 -my-4">
        <TytoConversationsPanel {...panelProps} className="h-[70vh] max-h-[560px]" />
      </div>
    </Dialog>
  )
}
