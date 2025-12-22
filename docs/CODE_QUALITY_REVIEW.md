# Revisión de Calidad de Código - UI

## Problemas Identificados

### 1. Lógica Duplicada: `handleViewPdf`

**Ubicaciones:**
- `ui/app/workspace/page.tsx` (líneas 74-91)
- `ui/app/dashboard/approval-queue/page.tsx` (líneas 81-98)
- `ui/app/dashboard/to-review/page.tsx` (líneas ~80-100)
- `ui/app/dashboard/view/page.tsx` (líneas 91-108)

**Código duplicado:**
```typescript
const handleViewPdf = async (document: Document) => {
  try {
    const runs = await getDocumentRuns(document.id)
    if (runs.length > 0 && runs[0].artifacts.pdf) {
      const filename = runs[0].artifacts.pdf.split('/').pop() || 'process.pdf'
      setViewerModal({
        isOpen: true,
        runId: runs[0].run_id,
        filename,
        type: 'pdf',
      })
    } else {
      alert('No hay PDF disponible para este documento')
    }
  } catch (err) {
    alert('Error al cargar el PDF: ' + (err instanceof Error ? err.message : 'Error desconocido'))
  }
}
```

**Solución propuesta:** Crear un hook `usePdfViewer` que encapsule esta lógica.

---

### 2. Estado Duplicado: `viewerModal`

**Ubicaciones:** Todas las páginas que usan `ArtifactViewerModal`

**Código duplicado:**
```typescript
const [viewerModal, setViewerModal] = useState<{
  isOpen: boolean
  runId: string
  filename: string
  type: 'json' | 'markdown' | 'pdf'
}>({
  isOpen: false,
  runId: '',
  filename: '',
  type: 'pdf',
})
```

**Solución propuesta:** Incluir en el hook `usePdfViewer`.

---

### 3. Función Duplicada: `getUserId`

**Ubicaciones:**
- `ui/app/dashboard/approval-queue/page.tsx` (líneas 40-45)
- `ui/app/dashboard/to-review/page.tsx` (líneas 40-45)
- `ui/app/dashboard/approval-queue/[document_id]/review/page.tsx` (líneas 30-35)
- `ui/hooks/useUserRole.ts` (líneas 21-29) - Ya existe una versión

**Código duplicado:**
```typescript
const getUserId = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('userId')
  }
  return null
}
```

**Solución propuesta:** Usar la función que ya existe en `useUserRole.ts` o crear un hook `useUserId`.

---

### 4. Lógica de Filtrado Duplicada

**Ubicaciones:**
- `ui/app/workspace/page.tsx` (líneas 61-72)
- `ui/app/dashboard/view/page.tsx` (líneas 65-76)
- `ui/app/dashboard/to-review/page.tsx` (líneas 82-101)
- `ui/app/dashboard/approval-queue/page.tsx` (líneas 101-120)

**Código duplicado:**
```typescript
const filteredDocuments = useMemo(() => {
  let filtered = documents

  // Filtrar por carpeta
  if (selectedFolderId) {
    filtered = filtered.filter((doc) => doc.folder_id === selectedFolderId)
  }

  // Filtrar por búsqueda
  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase()
    filtered = filtered.filter(
      (doc) =>
        doc.name.toLowerCase().includes(query) ||
        doc.description.toLowerCase().includes(query)
    )
  }

  return filtered
}, [documents, searchQuery, selectedFolderId])
```

**Variaciones:**
- `workspace/page.tsx` y `view/page.tsx` no filtran por carpeta en el useMemo (lo hacen en la query)
- `approval-queue/page.tsx` y `to-review/page.tsx` sí filtran por carpeta

**Solución propuesta:** Crear un hook `useDocumentFilter` que encapsule esta lógica.

---

### 5. Patrón de Carga de Documentos Similar

**Ubicaciones:** Todas las páginas de listado de documentos

**Patrón común:**
```typescript
useEffect(() => {
  async function loadDocuments() {
    if (!selectedWorkspaceId) {
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(null)
      const docs = await listDocumentsXXX(...)
      setDocuments(docs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  loadDocuments()
}, [selectedWorkspaceId, ...deps])
```

**Variaciones:**
- Diferentes funciones de API (`listDocuments`, `listDocumentsPendingApproval`, `listDocumentsToReview`, `listApprovedDocuments`)
- Algunas requieren `userId`, otras no
- Algunas tienen `selectedFolderId` como dependencia

**Solución propuesta:** Crear un hook genérico `useDocuments` que acepte la función de carga como parámetro.

---

### 6. Manejo de Errores Inconsistente

**Problemas:**
- Algunos usan `alert()` para errores (handleViewPdf)
- Otros usan estados de error en el componente
- Mensajes de error inconsistentes

**Solución propuesta:** Crear un sistema centralizado de notificaciones (toast/alert) o usar un hook `useErrorHandler`.

---

### 7. Componente `ArtifactViewerModal` Repetido

**Ubicaciones:** Todas las páginas que lo usan tienen el mismo código al final:
```typescript
<ArtifactViewerModal
  isOpen={viewerModal.isOpen}
  onClose={() => setViewerModal({ ...viewerModal, isOpen: false })}
  runId={viewerModal.runId}
  filename={viewerModal.filename}
  type={viewerModal.type}
/>
```

**Solución propuesta:** Incluir en el hook `usePdfViewer` que retorne el componente.

---

## Propuestas de Refactorización

### Hook 1: `usePdfViewer`

```typescript
// ui/hooks/usePdfViewer.ts
export function usePdfViewer() {
  const [viewerModal, setViewerModal] = useState<ViewerModalState>({
    isOpen: false,
    runId: '',
    filename: '',
    type: 'pdf',
  })

  const openPdf = async (document: Document) => {
    try {
      const runs = await getDocumentRuns(document.id)
      if (runs.length > 0 && runs[0].artifacts.pdf) {
        const filename = runs[0].artifacts.pdf.split('/').pop() || 'process.pdf'
        setViewerModal({
          isOpen: true,
          runId: runs[0].run_id,
          filename,
          type: 'pdf',
        })
      } else {
        // Usar sistema de notificaciones
        showError('No hay PDF disponible para este documento')
      }
    } catch (err) {
      showError('Error al cargar el PDF: ' + (err instanceof Error ? err.message : 'Error desconocido'))
    }
  }

  const closeModal = () => {
    setViewerModal({ ...viewerModal, isOpen: false })
  }

  const ModalComponent = () => (
    <ArtifactViewerModal
      isOpen={viewerModal.isOpen}
      onClose={closeModal}
      runId={viewerModal.runId}
      filename={viewerModal.filename}
      type={viewerModal.type}
    />
  )

  return { openPdf, ModalComponent }
}
```

### Hook 2: `useDocumentFilter`

```typescript
// ui/hooks/useDocumentFilter.ts
export function useDocumentFilter(
  documents: Document[],
  searchQuery: string,
  selectedFolderId: string | null
) {
  return useMemo(() => {
    let filtered = documents

    // Filtrar por carpeta
    if (selectedFolderId) {
      filtered = filtered.filter((doc) => doc.folder_id === selectedFolderId)
    }

    // Filtrar por búsqueda
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (doc) =>
          doc.name.toLowerCase().includes(query) ||
          (doc.description && doc.description.toLowerCase().includes(query))
      )
    }

    return filtered
  }, [documents, searchQuery, selectedFolderId])
}
```

### Hook 3: `useUserId`

```typescript
// ui/hooks/useUserId.ts
export function useUserId(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('userId')
  }
  return null
}
```

### Hook 4: `useDocuments` (Opcional, más complejo)

```typescript
// ui/hooks/useDocuments.ts
export function useDocuments<T>(
  loadFn: (workspaceId: string, ...args: any[]) => Promise<T[]>,
  deps: any[] = []
) {
  const { selectedWorkspaceId } = useWorkspace()
  const [documents, setDocuments] = useState<T[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!selectedWorkspaceId) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        setError(null)
        const docs = await loadFn(selectedWorkspaceId, ...deps)
        setDocuments(docs)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error desconocido')
        setDocuments([])
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [selectedWorkspaceId, ...deps])

  return { documents, loading, error }
}
```

---

## Prioridades de Refactorización

1. **Alta:** `usePdfViewer` - Elimina mucha duplicación y simplifica el código
2. **Alta:** `useDocumentFilter` - Lógica duplicada en 4 lugares
3. **Media:** `useUserId` - Ya existe en `useUserRole`, solo necesitamos extraerlo
4. **Baja:** `useDocuments` - Puede ser demasiado genérico y perder claridad

---

## Otros Problemas Menores

1. **Inconsistencia en manejo de errores:** Mezcla de `alert()` y estados de error
2. **Tipos duplicados:** El tipo del estado `viewerModal` está definido inline en cada página
3. **Falta de validación:** No se valida que `document.id` exista antes de hacer requests
4. **Carga de PDF duplicada:** `DocumentPreview` y `ApprovalModal` tienen lógica similar para cargar PDFs
5. **Múltiples formas de cargar PDFs:** Algunos usan blob URLs, otros URLs directas, inconsistente

---

## Resumen Ejecutivo

### Duplicación Crítica (Alta Prioridad)
- ✅ `handleViewPdf`: **4 copias idénticas** en diferentes páginas
- ✅ Estado `viewerModal`: **5 copias idénticas** 
- ✅ `getUserId`: **3 copias** (ya existe en `useUserRole.ts`)
- ✅ Lógica de filtrado: **4 copias** con pequeñas variaciones

### Impacto de Refactorización
- **Líneas de código eliminadas:** ~200-300 líneas
- **Mantenibilidad:** Mucho mejor - cambios en un solo lugar
- **Consistencia:** Comportamiento uniforme en toda la app
- **Testing:** Más fácil testear hooks aislados

### Recomendación
**Refactorizar en este orden:**
1. `usePdfViewer` - Mayor impacto, elimina más duplicación
2. `useDocumentFilter` - Muy común, usado en 4 lugares
3. `useUserId` - Simple, ya existe la lógica en `useUserRole`
4. Sistema de notificaciones - Para reemplazar `alert()`

