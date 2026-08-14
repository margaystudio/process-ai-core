// lib/networkError.ts
// Distingue "no pudimos ni hablar con el servidor" de un error que el backend
// sí respondió (404, 500 con `detail`, etc.). En una estación de servicio la
// conectividad es mala: sin esta distinción, un corte de señal se muestra con
// el mismo texto genérico que un error real, y el retry pierde sentido.

/** `fetch` nunca llegó a completarse: sin señal, DNS caído, servidor inalcanzable. */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof TypeError) return true
  if (err instanceof Error) {
    return /failed to fetch|networkerror|load failed|ERR_INTERNET|ERR_NETWORK/i.test(err.message)
  }
  return false
}

/** Copy consistente para el caso de red, en el mismo tono que el resto de Tyto. */
export const NETWORK_ERROR_MESSAGE =
  'No hay conexión con el servidor. Revisá tu señal y volvé a intentar — lo que preguntaste no se perdió.'
