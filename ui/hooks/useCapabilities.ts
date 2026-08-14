'use client'

import { useEffect, useSyncExternalStore } from 'react'
import { getMyCapabilities, type MyCapabilities } from '@/lib/api'
import { useWorkspace } from '@/contexts/WorkspaceContext'

/**
 * Capacidades efectivas del usuario en el tenant activo
 * (GET /api/v1/users/me/capabilities). Fuente de verdad compartida por
 * `useHasPermission`, `useFolderAccess` y los hooks de gating de
 * administración (`useCanManageWorkspace`, `useCanManageBranding`):
 * un solo fetch (cacheado/deduplicado en `lib/api`), muchos consumidores.
 *
 * `capabilities` es `null` mientras carga o si falló — los hooks derivados
 * son fail-closed en ese caso.
 *
 * Por qué un store module-level (con `useSyncExternalStore`) en vez de un
 * `useState` por instancia: estos hooks se montan en SIMULTÁNEO en varios
 * componentes de la misma pantalla (ej. el chrome del layout + el modal
 * "Nueva carpeta" de la página). Con `useState` por instancia, `refresh()`
 * solo actualizaría a quien lo llamó y el resto quedaría con el mapa de
 * carpetas viejo hasta su propio remount — exactamente el bug que esto
 * arregla (una carpeta recién creada queda "sin acceso" en el select de
 * carpeta padre hasta refrescar la página, porque `capabilities.folders`
 * no la conocía todavía). Con un store compartido, `refreshCapabilities()`
 * ejecutado desde CUALQUIER lugar (ej. tras crear una carpeta) notifica y
 * re-renderiza a TODOS los consumidores montados.
 */
interface CapabilitiesState {
  data: MyCapabilities | null
  loading: boolean
}

let state: CapabilitiesState = { data: null, loading: true }
const listeners = new Set<() => void>()

function setState(patch: Partial<CapabilitiesState>): void {
  state = { ...state, ...patch }
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): CapabilitiesState {
  return state
}

// Última key (workspace+tenant) por la que se pidió/resolvió el fetch. Sirve
// para no repetir la carga si varias instancias de useCapabilities montan a
// la vez con la misma key, y para descartar una respuesta tardía si el
// tenant activo cambió mientras esperábamos al backend.
let lastLoadKey: string | null = null

async function loadCapabilities(key: string, options?: { force?: boolean }): Promise<void> {
  lastLoadKey = key
  setState({ loading: true })
  try {
    const data = await getMyCapabilities(options)
    if (lastLoadKey !== key) return
    setState({ data, loading: false })
  } catch {
    if (lastLoadKey !== key) return
    setState({ data: null, loading: false })
  }
}

/**
 * Fuerza un refetch de capabilities y notifica a todos los hooks derivados
 * montados en ese momento (`useCapabilities`, `useFolderAccess`,
 * `useHasPermission`, los gates de administración, etc.), sin importar en
 * qué componente se llame.
 *
 * Llamalo después de cualquier mutación que cambie el conjunto de carpetas
 * del usuario o su estructura (crear, borrar, mover/re-parentar): si no se
 * refresca, `capabilities.folders` queda desactualizado y una carpeta nueva
 * se trata como "sin acceso" (fail-closed) hasta que el usuario recarga la
 * página a mano.
 */
export function refreshCapabilities(): Promise<void> {
  return loadCapabilities(lastLoadKey ?? '', { force: true })
}

/**
 * Solo para tests: resetea el store compartido entre casos.
 *
 * Al ser un singleton de módulo (a propósito: es lo que permite notificar a
 * todos los consumidores montados), sobrevive entre los `it()` de un mismo
 * archivo de test. Sin este reset, el segundo test heredaría las
 * capabilities cacheadas del primero aunque su mock de `getMyCapabilities`
 * devuelva otra cosa — se llama desde `vitest.setup.ts` en un `afterEach`
 * global, no hace falta invocarlo a mano en cada test.
 */
export function __resetCapabilitiesStoreForTests(): void {
  state = { data: null, loading: true }
  lastLoadKey = null
  listeners.clear()
}

export function useCapabilities(): { capabilities: MyCapabilities | null; loading: boolean } {
  const { selectedWorkspaceId, activeTenantId } = useWorkspace()
  const key = `${selectedWorkspaceId ?? ''}:${activeTenantId ?? ''}`

  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  useEffect(() => {
    // Solo se refetchea al cambiar de workspace/tenant activo (o en la carga
    // inicial): si ya hay una carga en curso o resuelta para esta key, esta
    // instancia se limita a suscribirse al store en vez de disparar otro
    // fetch redundante.
    if (lastLoadKey === key) return
    loadCapabilities(key)
  }, [key])

  return { capabilities: snapshot.data, loading: snapshot.loading }
}
