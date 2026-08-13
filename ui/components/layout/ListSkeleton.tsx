// components/layout/ListSkeleton.tsx
//
// Skeleton de una fila de documento (armado con el primitivo `<Skeleton>` del design
// system) y su composición en lista + encabezado. Nace en la Biblioteca
// (`app/workspace/page.tsx`) y se generaliza acá para reusarse en cualquier pantalla
// que muestre "una lista de documentos cargando" — incluida la entrada de la app
// (`app/page.tsx`), que no sabe todavía a qué pantalla va a redirigir pero sí que el
// destino más común es la Biblioteca.
import { Skeleton } from '@/shared/ui/components'

export function RowSkeleton() {
  return (
    <div className="flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-3.5">
      <Skeleton className="h-10 w-10 flex-shrink-0 rounded-[10px]" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-3 w-1/3" />
      </div>
      <Skeleton className="h-7 w-20 rounded-pill" />
      <Skeleton className="h-[34px] w-16 rounded-[9px]" />
    </div>
  )
}

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-[9px]">
      {Array.from({ length: rows }).map((_, i) => (
        <RowSkeleton key={i} />
      ))}
    </div>
  )
}

/**
 * Skeleton de página completa: encabezado (kicker + título + descripción) y lista.
 * Pensado para el hueco entre "el shell ya está" y "todavía no sé qué contenido va acá"
 * — p. ej. `app/page.tsx` mientras resuelve a qué pantalla redirigir.
 */
export function PageListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="min-w-0 max-w-[940px] flex-1 px-8 pb-[50px] pt-7">
      <div className="mb-[18px] space-y-2.5">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <ListSkeleton rows={rows} />
    </div>
  )
}
