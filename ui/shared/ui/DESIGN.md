# Design System Margay · spec

Fuente de verdad **legible** del sistema. Los **valores** viven en `tokens.css`, el
**mapeo a clases** en `tailwind-preset.ts`, los **componentes** en `components/*` y la
**fuente** en `fonts.ts`. Este doc explica y defiende esos tokens; no los reemplaza.
Dueño: el agente **margay-frontend**.

> Regla de oro: una sola fuente de verdad. ¿Cambia el verde de marca? Se edita en
> `tokens.css` y se actualiza toda la plataforma.

## Identidad
- **Marca:** verde Margay `#7CC39C` (`--green`); para texto/headers sobre claro, verde
  profundo (`--green-700` / `--create #1F8A55`).
- **Acción primaria = carbón** `--ink-800 #37393A` (el verde no compite con los datos).
  **Crear/nuevo = verde** (`variant="create"`).
- **Tipografía:** Plus Jakarta Sans (UI) + mono solo para IDs/código.
- **Densidad:** dashboard/admin, media-alta. Jerarquía con tipografía y tinta, no con
  cajas de color.

## El contrato de tokens (clases semánticas, nunca hex)
- **Tinta/neutros:** `text-ink-800` (principal), `text-ink-600` (secundario),
  `text-ink-500` (terciario/placeholder), `border-ink-200/300`, `bg-ink-50` (fondo),
  `bg-white` (tarjetas).
- **Marca/acción:** `bg-green`, `text-green-700`, `bg-action`/`text-action-on`, `bg-create`.
- **Estados:** `bg-{success|warning|danger|info}-bg` + `text-…` + `…-bd`. El rojo/verde se
  reservan para estado, nunca decorativos.
- **Acento por módulo:** envolvé en `data-module="hub|process|oms|gpu|insights"` y usá
  `text-accent` / `bg-accent-tint` / `text-accent-ink`. Mapa: hub=verde, process=
  periwinkle, oms=coral, gpu=violeta, insights=peach.
- **Tipografía:** `text-display/h1/h2/h3/body/sm/xs/label`.
- **Radios/sombras:** `rounded-sm/md/lg/xl`, `shadow-xs/sm/md/lg`. Spacing en múltiplos de 4.

## Componentes (usar, no recrear)
`<Button variant="primary|create|secondary|ghost|danger" size="sm|md|lg">`,
`<Card>/<CardBody>`, `<Badge variant="neutral|success|warning|danger|info">`,
`<Input>/<Field>`. Iconos: `lucide-react`. Si falta un componente, se agrega a
`components/*` con `cva` + tokens — nunca inline en la pantalla.

## Reglas (do / don't)
- ✅ tokens (`text-ink-600`, `bg-green`) — ❌ hex sueltos (`text-[#6A6E70]`).
- ✅ componentes base — ❌ un Button/Input casero por módulo.
- ✅ acento por `data-module` — ❌ hardcodear el color del módulo.
- ✅ estados vacío/carga/error en toda lista — ❌ pantalla en blanco.
- Accesibilidad AA: foco visible (ya global en `tokens.css`), label por input, navegación
  por teclado.
- **Tamaño de target:** el mínimo real (WCAG 2.2 AA, criterio 2.5.8) es **24px**.
  Recomendación Margay para acciones primarias o contextos táctiles/mobile: **≥38px**
  (`size="md"`). `size="sm"` (32px) es válido y preferido para densidad alta —toolbars,
  filas de tabla, dashboards apretados— pero no para la acción primaria en mobile.
- Sin gradientes decorativos, sin emojis en UI, sin fuentes fuera del sistema.

## Arquitectura de chrome (AppShell)

El shell de un módulo se compone con `<AppShell module topbar sidebar>`. Regla madre:
**cada marca aparece una sola vez, cada una con su etiqueta correcta.**

- **Topbar = el MÓDULO** (fondo claro). Emblema del módulo (`<ModuleEmblem>` en tile
  `bg-accent-tint text-accent-ink`) + nombre del módulo, a la izquierda. Usuario
  (nombre + email + avatar + Salir) a la derecha. El logo Margay NO va en el topbar.
  - **Switcher de organización (opcional):** pasale `tenants` + `activeTenantId` +
    `onTenantChange` al `<Topbar>` y aparece, junto al nombre del módulo, un selector de
    tenant (como el hub). Si el usuario tiene una sola organización se muestra sin desplegable.
    Cuando el switch vive en el topbar, NO repitas la cuenta en la sidebar.
- **Sidebar = oscura** (tokens `--sidebar-*`):
  - *Arriba* = la **cuenta/tenant** que se opera (`[iniciales]` + nombre). Solo si hay
    cliente (p.ej. OMS → "Bocaditos Express"). En módulos internos —o si el switcher de
    organización ya está en el topbar— se omite. El chevron de switcher solo aparece si
    se pasa `account.onSwitch` (sin handler no hay flechita muerta).
  - *Abajo* = **firma Margay** (logo + "Margay Studio · Plataforma Margay"). Siempre.
  - Item activo: `bg-white/[.09]` + barra de acento `shadow-[inset_3px_0_0_var(--accent)]`
    + icono `text-accent`.
- **Usuario:** SOLO en el topbar. Nunca duplicado en la sidebar.

### Emblemas de módulo
Familia monolínea, grilla 48×48, un trazo. `<ModuleEmblem module="gpu" />` (trazo =
`currentColor`, se tiñe con el acento). Mapa: hub=órbita · process=nodos · oms=flujo ·
gpu=pulso · insights=ojo/lente. También como SVG en `brand/modules/<mod>.svg` (plano) y
`<mod>-tile.svg` (con fondo, para favicons/app-icons). El **ojo Margay** (logo de marca,
`brand/margay-icon-48.png`) se usa solo en la firma de la sidebar y en el Hub.

### Componentes nuevos
- `<OptionSet options value onChange columns>` — selección de una opción (radio cards),
  se tiñe con el acento del módulo.
- `<Uploader accept hint onFile>` — dropzone de carga (resalta con el acento al arrastrar).
- `<AppShell>`, `<Topbar>`, `<Sidebar>`, `<ModuleEmblem>` — el chrome descrito arriba.

### Ejemplo de uso
```tsx
<AppShell
  module="gpu"
  topbar={<Topbar module="gpu" title="GPU Operaciones" user={user} />}
  sidebar={
    <Sidebar
      groups={[{ label: "Operaciones", items: [
        { label: "Objetivos", icon: <Target />, active: true },
        { label: "Cargas", icon: <Clock /> },
      ]}]}
    />
  }
>
  {/* contenido del módulo */}
</AppShell>
```
Para un módulo con cliente (OMS), pasá `account={{ name: "Bocaditos Express" }}` al Sidebar.

## Cómo lo adopta un módulo
Ver `README.md` (modo interino: copiar a `ui/shared/ui/`; futuro: paquete `@margay/ui`).

## Quién lo mantiene
**margay-frontend.** Token o componente nuevo → se agrega al código y se anota acá. Si el
cambio toca el modelo de plataforma (rutas, datos, permisos), se coordina con **margay-architect**.
