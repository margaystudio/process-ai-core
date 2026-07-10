"use client";

/**
 * useAsync — patrón consistente para datos async en componentes Margay.
 *
 * Distingue cuatro estados explícitos para evitar el bug clásico de mostrar
 * "Cargando…" cuando en realidad el resultado está vacío:
 *
 *   idle    → nunca iniciado (page cargando, dependencias todavía nulas).
 *   loading → fetch en curso.
 *   success → fetch completado; `data` puede ser un array vacío o null.
 *   error   → fetch fallido; `error` contiene el mensaje.
 *
 * La lógica de transición vive en `asyncReducer` (función pura, importable y
 * testeable sin DOM). El hook simplemente la aplica con useReducer + useEffect.
 *
 * @example
 * const { state, data, error } = useAsync(
 *   () => fetchDocuments(workspaceId),
 *   [workspaceId]
 * );
 * if (state === 'idle' || state === 'loading') return <Skeleton />;
 * if (state === 'error')   return <ErrorMessage message={error} />;
 * if (!data?.length)       return <EmptyState />;
 * return <List items={data} />;
 */

import { useReducer, useEffect, useRef, useCallback, DependencyList } from "react";

// ─── Estado ────────────────────────────────────────────────────────────────

export type AsyncStatus = "idle" | "loading" | "success" | "error";

export interface AsyncState<T> {
  status: AsyncStatus;
  data: T | null;
  error: string | null;
}

// ─── Acciones ──────────────────────────────────────────────────────────────

export type AsyncAction<T> =
  | { type: "LOADING" }
  | { type: "SUCCESS"; data: T }
  | { type: "ERROR"; error: string }
  | { type: "RESET" };

// ─── Reducer puro (exportado para tests) ───────────────────────────────────

export function asyncReducer<T>(
  state: AsyncState<T>,
  action: AsyncAction<T>
): AsyncState<T> {
  switch (action.type) {
    case "LOADING":
      return { status: "loading", data: state.data, error: null };
    case "SUCCESS":
      return { status: "success", data: action.data, error: null };
    case "ERROR":
      return { status: "error", data: null, error: action.error };
    case "RESET":
      return { status: "idle", data: null, error: null };
    default:
      return state;
  }
}

export function initialAsyncState<T>(): AsyncState<T> {
  return { status: "idle", data: null, error: null };
}

// ─── Hook ──────────────────────────────────────────────────────────────────

export interface UseAsyncReturn<T> extends AsyncState<T> {
  /** Lanza el fetch manualmente (útil para retry). */
  reload: () => void;
}

/**
 * @param fn    Función async que devuelve el dato. Se vuelve a llamar cuando
 *              cambian las `deps`. Si devuelve `undefined`, el estado no cambia
 *              (permite abortar cuando las dependencias son nulas).
 * @param deps  Dependencias, igual que useEffect.
 */
export function useAsync<T>(
  fn: () => Promise<T | undefined>,
  deps: DependencyList
): UseAsyncReturn<T> {
  const [state, dispatch] = useReducer(
    asyncReducer as (s: AsyncState<T>, a: AsyncAction<T>) => AsyncState<T>,
    undefined,
    initialAsyncState<T>
  );

  // Versión estable de la función para evitar re-renders extra.
  const fnRef = useRef(fn);
  fnRef.current = fn;

  // Contador de runs para ignorar respuestas de runs obsoletos.
  const runRef = useRef(0);

  const run = useCallback(() => {
    const currentRun = ++runRef.current;
    dispatch({ type: "LOADING" });

    fnRef.current().then(
      (data) => {
        if (runRef.current !== currentRun) return; // resultado obsoleto
        if (data === undefined) return;             // fn decidió no actualizar
        dispatch({ type: "SUCCESS", data });
      },
      (err: unknown) => {
        if (runRef.current !== currentRun) return;
        const message =
          err instanceof Error ? err.message : String(err ?? "Error desconocido");
        dispatch({ type: "ERROR", error: message });
      }
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { ...state, reload: run };
}
