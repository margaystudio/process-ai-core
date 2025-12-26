'use client'

import { useMemo } from 'react'
import { Document } from '@/lib/api'

/**
 * Hook para filtrar documentos por búsqueda y carpeta.
 * 
 * @param documents - Lista de documentos a filtrar
 * @param searchQuery - Texto de búsqueda (busca en nombre y descripción)
 * @param selectedFolderId - ID de carpeta para filtrar (opcional)
 * @returns Lista filtrada de documentos
 */
export function useDocumentFilter(
  documents: Document[],
  searchQuery: string,
  selectedFolderId: string | null = null
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


