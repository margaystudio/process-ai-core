// Traducción de las apps del control plane a los módulos del design system, y datos
// de identidad de ESTE módulo para el chrome de plataforma (`<PlatformShell>`).
//
// Mismo patrón que adoptó margay-crm (margay-ui 0.11–0.13): workspace identifica las
// apps con su `key` de registro (`process_ai`, `margay_timbo`, …) y el design system
// con la clave de identidad (`arrayan`, `timbo`, …), que resuelve emblema, color y
// descriptor (ver DESIGN.md § Identidad de módulo). Son dos vocabularios distintos y
// este archivo es el único lugar donde se cruzan.
//
// TODO(arquitectura): `/api/v1/users/me` (CurrentUserResponse en lib/api.ts) todavía no
// reexpone `modules` (key, name, entry_url) del contexto de sesión de workspace, así que
// hoy no hay de dónde sacar la lista de módulos del usuario para el switcher cruzado —
// pedir que lo agregue como hizo margay-crm en `commercial_api/api/me.py`
// (`_modules_of_tenant`, reexponiendo `tenant_modules[].applications` sin decidir acceso).
// Mientras tanto, `modulosParaSwitcher` degrada con gracia: sin `modules`, el lockup del
// topbar muestra el emblema + nombre del módulo actual, sin abrir menú (comportamiento
// idéntico al que tenía este chrome antes del sync).
import type { ModuleRef } from '@/shared/ui/components'

/** App del control plane, tal como la expondría `/users/me` (ver TODO arriba). */
export interface ModuleApp {
  key: string
  name: string
  entry_url: string
}

/** `key` de workspace → clave de identidad del design system. */
const CLAVE_DS: Record<string, string> = {
  process_ai: 'arrayan',
  gpu_ops: 'gpu',
  margay_timbo: 'timbo',
  commercial: 'timbo',
  oms: 'pindo',
  margay_insights: 'ceibo',
  tablero_bi_360: 'ombu',
  margay_data: 'data',
}

/** La clave del design system para ESTE módulo (Process AI = Arrayán). Fija el acento
 *  (`data-module`) y el emblema del chrome. */
export const MODULO_ACTUAL = 'arrayan'

/** El Hub está registrado como una app más en el control plane, pero no es un módulo:
 *  es nivel plataforma. El switcher ya lo muestra aparte (fila propia, logo Margay, vía
 *  `hubUrl`); dejarlo pasar acá lo duplicaría con tile neutro (no tiene emblema desde la
 *  identidad 0.9.0). */
const NO_SON_MODULOS = new Set(['hub', 'margay_hub'])

/** Orden de lectura del switcher: visión → operación → datos, como el Hub. Una clave que
 *  no esté acá va al final, en el orden en que vino. */
const ORDEN = ['ombu', 'pindo', 'timbo', 'gpu', 'arrayan', 'ceibo', 'data']

/**
 * Apps del control plane → `modules` del switcher. Una app sin traducción conocida pasa
 * con su key cruda: el DS la pinta con tile neutro (`isModuleKey`) en vez de romper, así
 * un módulo nuevo aparece en el menú antes de que este mapa lo conozca.
 */
export function modulosParaSwitcher(apps: ModuleApp[] | undefined): ModuleRef[] {
  const refs = (apps ?? [])
    .filter((app) => !NO_SON_MODULOS.has(app.key))
    .map((app) => ({
      key: CLAVE_DS[app.key] ?? app.key,
      name: app.name,
      entryUrl: app.entry_url,
    }))
  return refs.sort((a, b) => {
    const ia = ORDEN.indexOf(a.key)
    const ib = ORDEN.indexOf(b.key)
    return (ia === -1 ? ORDEN.length : ia) - (ib === -1 ? ORDEN.length : ib)
  })
}

/** URL del Hub, para la salida del menú de módulos. Mismo patrón que `lib/hub-login.ts`. */
export function hubUrl(): string {
  return (process.env.NEXT_PUBLIC_HUB_URL ?? 'https://hub.margaystudio.io').replace(/\/+$/, '')
}
