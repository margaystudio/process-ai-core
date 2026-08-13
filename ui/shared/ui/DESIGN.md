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
- **Acento por módulo:** envolvé en
  `data-module="ombu|arrayan|gpu|timbo|ceibo|pindo|data"` y usá
  `text-accent` / `bg-accent-tint` / `text-accent-ink`. Mapa: ombu=teal `#1F7A85`,
  arrayan=índigo `#4A5CB8`, gpu=violeta `#7E4FA8`, timbo=magenta `#A8437B`,
  ceibo=carmín `#AD2E38`, pindo=naranja `#E07B22`, data=oliva `#77841F`. El verde
  de marca no lo usa ningún módulo; es el acento por defecto (sin `data-module`).
- **Tipografía:** `text-display/h1/h2/h3/body/sm/xs/label`.
- **Radios/sombras:** `rounded-sm/md/lg/xl`, `shadow-xs/sm/md/lg`. Spacing en múltiplos de 4.

## Componentes (usar, no recrear)
`<Button variant="primary|create|secondary|ghost|danger" size="sm|md|lg">`,
`<Card>/<CardBody>`, `<Badge variant="neutral|success|warning|danger|info">`,
`<Input>/<Field>`. Iconos: `lucide-react`. Si falta un componente, se agrega a
`components/*` con `cva` + tokens — nunca inline en la pantalla.

## Carga: Skeleton vs. Spinner
Dos primitivos, sin superposición — extensiones locales de este módulo (como
Dialog/Tabs), candidatas a subir a margay-ui:

- **`<Skeleton className="...">`** — TODA carga de contenido o de página: el shell al
  entrar, una lista, un preview de PDF, un formulario. Un bloque que pulsa
  (`animate-pulse`, `bg-ink-100`) en el lugar exacto donde va el dato real; la forma la
  da `className` (alto/ancho/radio), no una variante. Nunca pantalla en blanco.
- **`<Spinner size="xs|sm|md|lg">`** — SOLO una acción puntual dentro de un control: un
  botón guardando, una fila procesando un import, una búsqueda en curso. `Loader2` de
  lucide + `animate-spin`. Nunca a pantalla completa, nunca para carga de página.
- **Retirado:** el spinner del logo del margay girando (`LoadingOverlay` +
  `margay-spiner.png`) y el zoológico de ~20 `animate-spin` ad-hoc (medialunas
  `border-b-2`, círculos `border-t-accent`, `Loader2` sueltos de distinto tamaño) que
  había antes de este estándar — todos migrados a uno de los dos primitivos de arriba.
- **Chrome de entrada:** `<Sidebar>` acepta `NavItem.loading` (renderiza el ítem como
  skeleton en su lugar exacto en vez de omitirlo hasta que el permiso resuelva —
  evita que la sidebar se "pueble de a uno") y `<Topbar>`/`<PlatformShell>` aceptan
  `userLoading` / `tenantsLoading` (skeleton en el bloque de usuario y en el selector de
  cliente mientras la sesión resuelve, en vez de un nombre provisorio tipo "Usuario").

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

## Arquitectura de chrome

Dos niveles, y el de arriba es el que usa un módulo de la plataforma:

- **`<PlatformShell>`** — el chrome completo (topbar + switcher de módulo + cliente +
  usuario + sidebar con colapso + firma). El módulo aporta **configuración**, no layout.
  **Es lo que usa cualquier módulo de la plataforma.**
- **`<AppShell>` + `<Topbar>` + `<Sidebar>` sueltos** — la capa de abajo, para casos donde
  no hay registro de módulos (login, un embed, una pantalla fuera de la plataforma).

Regla madre de las dos: **cada marca aparece una sola vez, con su etiqueta correcta.**

### PlatformShell (el chrome de la plataforma)

El chrome deja de vivir en cada repo de módulo. La app pasa `module`, `nav` y los datos de
sesión; no define colores, ni estructura de topbar, ni firma de marca, ni lógica de
colapso. Si necesita algo que el shell no da, **no lo parchea localmente: se agrega acá.**

> **La librería es presentación pura: recibe props y pinta.** No hace fetch, no conoce
> servicios, no decide qué mostrar. De dónde sale la lista de módulos, quién tiene permiso
> y qué cliente está activo lo resuelve cada app. La librería aporta el emblema, el color
> y el descriptor; el resto lo trae la app.

```tsx
<PlatformShell
  module="pindo"          // string — fija acento y emblema
  modules={modules}       // ModuleRef[] — los que la app quiere mostrar
  tenant={tenant}         // TenantRef activo
  tenants={tenants}       // TenantRef[] elegibles
  user={user}             // PlatformUser
  hubUrl="https://hub.margay.io"
  nav={groups}            // NavGroup[] — la navegación propia del módulo
  onLogout={handleLogout}
>
  {children}
</PlatformShell>
```

```ts
interface ModuleRef   { key: string; name: string; entryUrl: string; unavailable?: boolean }
interface TenantRef   { id: string; name: string; slug: string }   // el switcher usa id y name
interface PlatformUser { displayName: string; email: string; avatarUrl?: string }
```

**Todo lo visible se controla por props. Lo que no se pasa, no se renderiza:**

| Falta | Qué desaparece |
|---|---|
| `modules` (o trae uno solo) | el lockup no abre menú |
| `tenants` **o** `onTenantChange` | no hay selector de cliente |
| `hubUrl` | el menú no muestra la salida al Hub |
| `nav` | no hay sidebar, ni drawer, ni hamburguesa |
| `user` | no hay bloque de usuario |
| `brand` | el lockup habla del módulo, no del cliente (chrome de plataforma) |

### White-label por cliente

Hay módulos que un cliente compra con SU marca: el usuario de esa intendencia entra a ver
su tablero, no «un módulo de Margay». Para esos casos el chrome se rebrandea sin forkearse,
con dos piezas que van juntas:

- **`brand={{ name, subtitle? }}`** — el lockup pasa a hablar del cliente. El menú de
  módulos NO cambia: adentro, el módulo actual sigue saliendo con su nombre y su
  descriptor de plataforma, porque ahí el usuario está eligiendo entre módulos Margay.
- **Tokens `--tenant-*`** — el color. La app los setea en `:root` en runtime, cuando
  resuelve el cliente:

  | Token | Pisa a |
  |---|---|
  | `--tenant-accent` / `--tenant-accent-ink` / `--tenant-accent-tint` | el acento del módulo |
  | `--tenant-sidebar-bg` / `--tenant-sidebar-surface` | los fondos de la sidebar |

  Van con indirección (`var(--tenant-accent, var(--acc-ombu))`) y no por especificidad:
  `--accent` se define en el nodo `[data-module]`, que está más cerca que `:root`, así que
  un override heredado —incluso un style inline en `<html>`— perdería. Un módulo que no se
  rebrandea no setea nada y no cambia en nada.

**El emblema y la clave del módulo no se rebrandean.** El cliente pone su nombre y su
color; qué módulo es sigue siendo de la plataforma, y es lo que hace que el switcher se
entienda cuando el usuario tiene tres módulos de tres clientes distintos.

Reglas del contrato:
- **`key` es `string`, no `ModuleKey`.** La lista de módulos la define la app, no la
  librería. Una clave que la librería no conoce **no rompe nada**: el emblema cae en tile
  neutro y el acento queda en el verde de marca (ninguna regla `[data-module]` matchea).
  Agregar un módulo nuevo nunca puede tirar abajo el switcher.
- **El nombre lo trae la app** (`modules[].name`), y se pinta tal cual. La librería no
  mantiene un mapa de nombres: eso es lo que termina con «Margay Pindó» contra «Ombú».
- **El descriptor lo aporta la librería** (`MODULE_DESC`, junto a `ModuleEmblem`): es copy
  de identidad, no varía por cliente ni por app. Clave sin descriptor → fila sin
  descriptor.
- **`displayName` se pinta tal cual**: no se concatena, no se formatea, no se deriva. Las
  iniciales del avatar sí las calcula la librería, pero **solo** si no viene `avatarUrl`.
- **`unavailable`** lo pinta la librería (fila atenuada + «No disponible»); **quién está
  disponible lo decide la app.** El link sigue siendo navegable: el aviso de por qué el
  cliente no aplica lo da el módulo destino, no el switcher.

Lo que arma el shell:
- **Topbar**, de lo general a lo particular: `[emblema + nombre módulo ▾]` · `[cliente ▾]`
  · … · `[usuario]`.
- **Avatar:** `avatarUrl` si existe, iniciales si no. La regla vive en el shell, así que
  deja de variar entre módulos.
- **Sidebar** oscura con la nav del módulo, colapso **siempre disponible** y la firma
  Margay al pie. `NavItem` acepta `href` (sale como `<a>`, así el ítem se puede abrir en
  otra pestaña con ⌘/Ctrl+clic o el botón del medio; el clic normal lo sigue manejando
  `onClick`) y `children` (dos niveles: el padre no navega, abre y cierra, y se auto-abre
  cuando el hijo activo entra en él — pero si el usuario lo cierra a mano, se queda
  cerrado). Con la sidebar colapsada, tocar un padre la expande primero: en 64px no hay
  lugar para un submenú. El colapso se persiste en `localStorage` (`margay:nav-collapsed`): saltar
  de módulo es una recarga completa —cambia el subdominio— y sin persistir se resetearía
  en cada salto.
- **Drawer mobile** cableado solo: el módulo no maneja ese estado.
- **Cuenta en la sidebar: no.** El cliente vive en el topbar; repetirlo abajo lo duplica.

### ModuleSwitcher

Se abre desde el lockup. Lista los módulos que le pasaron con emblema, nombre y
descriptor, marca el actual y —si hay `hubUrl`— cierra con la salida al Hub.

- **El destino es la `entryUrl` pelada** (la barra final, si viene, se ignora): el cliente
  activo NO va en la URL. Viaja en la cookie compartida de `.margaystudio.io`, que todos
  los módulos ya leen para resolverlo. Hasta 0.11.0 iba en el path (`${entryUrl}/${slug}`)
  buscando links autodescriptivos, pero ningún módulo rutea ese segmento: el salto caía
  en 404. Si algún día se quiere de vuelta, primero lo tienen que aceptar los destinos.
- Son **enlaces reales** (`<a href>`), no navegación de router: cambia el subdominio. Y
  **abren en pestaña nueva**, para no perder lo que estabas haciendo en el módulo actual.
  La fila del módulo actual no es un link: ya estás ahí (sería una pestaña duplicada).
- **El Hub no es un módulo:** va en su propia fila al pie, con el logo Margay y sin
  emblema. Si viene en `modules` es que la app se lo pasó — filtralo antes, o aparece
  dos veces y con tile neutro (la librería no adivina qué es un módulo y qué no).
- Cada tile lleva su propio `data-module`, así el emblema del menú sale en **su** color y
  no en el del módulo actual.
- **Un solo módulo:** el lockup no abre menú — es un lockup y punto.
- **El Hub no es un módulo:** sin emblema, con el logo Margay, siempre última fila.

### La capa de abajo (AppShell + Topbar + Sidebar)

- **Topbar = el MÓDULO** (fondo claro). Emblema del módulo (`<ModuleEmblem>` en tile
  `bg-accent-tint text-accent-ink`) + nombre del módulo, a la izquierda. Usuario
  (nombre + email + avatar + Salir) a la derecha. El logo Margay NO va en el topbar.
  - **Switcher de organización (opcional):** pasale `tenants` + `activeTenantId` +
    `onTenantChange` al `<Topbar>` y aparece, junto al nombre del módulo, un selector de
    tenant (como el hub). Si el usuario tiene una sola organización se muestra sin desplegable.
    Cuando el switch vive en el topbar, NO repitas la cuenta en la sidebar.
- **Sidebar = oscura** (tokens `--sidebar-*`):
  - *Arriba* = la **cuenta/tenant** que se opera (`[iniciales]` + nombre). Solo si hay
    cliente (p.ej. Pindó → "Bocaditos Express"). En módulos internos —o si el switcher de
    organización ya está en el topbar— se omite. El chevron de switcher solo aparece si
    se pasa `account.onSwitch` (sin handler no hay flechita muerta).
  - *Abajo* = **firma Margay** (logo + "Margay Studio · Plataforma Margay"). Siempre.
  - Item activo: `bg-white/[.09]` + barra de acento `shadow-[inset_3px_0_0_var(--accent)]`
    + icono `text-accent`.
- **Usuario:** SOLO en el topbar. Nunca duplicado en la sidebar.

### Identidad de módulo (nombre, descriptor, emblema)
Siete módulos, cada uno con nombre, descriptor, emblema y color propios:

| Clave | Módulo | Descriptor | Emblema |
|---|---|---|---|
| `ombu` | Ombú | Visión 360 del negocio | la copa ancha |
| `arrayan` | Arrayán | Conocimiento y procesos | nodos enlazados |
| `gpu` | GPU Operaciones | Objetivos, ETL y monitoreo | el pulso |
| `timbo` | Timbó | Clientes, oportunidades y ventas | anillos, el cliente al centro |
| `ceibo` | Ceibo | Capa semántica y chat | la flor |
| `pindo` | Pindó | Recepción y gestión de pedidos | la corona de la palma |
| `data` | Margay Data | Infraestructura y calidad de datos | capas apiladas |

- **Nombres:** producto de cara al cliente = árbol nativo (Ombú, Arrayán, Timbó, Ceibo,
  Pindó); infraestructura = nombre funcional (GPU Operaciones, Margay Data).
- **Descriptores:** 3 a 5 palabras, alcance concreto, sin repetir el nombre del módulo.
  Viven en el código como `MODULE_DESC` (junto a `ModuleEmblem`): son copy de identidad,
  no dato de negocio. Esta tabla y ese record tienen que decir lo mismo.
- **Emblemas:** familia monolínea, grilla 48×48, trazo 3, caja óptica ~34×32, ningún
  círculo por debajo de radio 4. Se tiñen con `currentColor`:
  `<ModuleEmblem module="gpu" />` toma el acento del contexto.
- **Tinte del tile: 30%.** Por debajo de ~20% los siete tonos colapsan contra el blanco.
- **El verde `--green` queda exclusivo de la marca Margay**: ningún módulo lo usa.
- El **Hub no es un módulo**: es nivel plataforma y no lleva emblema.

También como SVG en `brand/modules/`, tres por módulo: `<mod>.svg` (glifo solo, trazo en
el acento, fondo transparente), `<mod>-tile.svg` (64×64, fondo al 30% + glifo en `ink` —
el tile de la UI) y `<mod>-favicon.svg` (fondo sólido del acento + glifo blanco con trazo
grueso; **usá este para favicon**: el monolínea sobre claro desaparece a 16px).

El logo Margay (`brand/margay-icon-48.png`) va solo en la firma de la sidebar y en el
Hub; el emblema del módulo va en su topbar y en su tarjeta del Hub. Nunca los dos juntos.

### Componentes nuevos
- `<OptionSet options value onChange columns>` — selección de una opción (radio cards),
  se tiñe con el acento del módulo.
- `<Uploader accept hint onFile>` — dropzone de carga (resalta con el acento al arrastrar).
- `<AppShell>`, `<Topbar>`, `<Sidebar>`, `<ModuleEmblem>` — el chrome descrito arriba.
- `<PlatformShell>`, `<ModuleSwitcher>` — el chrome de plataforma, armado sobre los cuatro
  anteriores. Props opt-in que habilitan: `<Topbar lockup>` (reemplaza emblema + título),
  `<Topbar user?>` (sin usuario no hay bloque de usuario) y `<Sidebar collapsed
  onToggleCollapse>` (rail de 64px). Sin esas props, ambos renderizan igual que siempre.
- `MODULE_DESC` / `isModuleKey(key)` — descriptores de identidad y el guard de claves
  conocidas (para tolerar módulos que la librería todavía no dibuja).

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
Para un módulo con cliente (Pindó), pasá `account={{ name: "Bocaditos Express" }}` al Sidebar.

## Cómo lo adopta un módulo
Ver `README.md` (modo interino: copiar a `ui/shared/ui/`; futuro: paquete `@margay/ui`).

## Quién lo mantiene
**margay-frontend.** Token o componente nuevo → se agrega al código y se anota acá. Si el
cambio toca el modelo de plataforma (rutas, datos, permisos), se coordina con **margay-architect**.

## Changelog
- **0.16.0 · Estándar de carga: `Skeleton` + `Spinner`, y el chrome deja de "poblarse de
  a uno".** Dos primitivos nuevos (`components/Skeleton.tsx`, `components/Spinner.tsx`)
  reemplazan el zoológico de ~20 `animate-spin` ad-hoc del módulo (medialunas, círculos,
  `Loader2` sueltos) y retiran el spinner del logo del margay girando (`LoadingOverlay`
  + `margay-spiner.png`, sin reemplazo directo: el overlay bloqueante de
  `LoadingContext` pasa a usar `<Spinner size="lg">`).
  - **`<Skeleton>`** — bloque `animate-pulse`/`bg-ink-100`, forma por `className`. Para
    TODA carga de contenido/página.
  - **`<Spinner size="xs|sm|md|lg">`** — `Loader2` + `animate-spin`, tamaños fijos. Solo
    para una acción puntual dentro de un control.
  - **`Sidebar` → `NavItem.loading`**: un ítem gateado por permiso que todavía no
    resolvió ocupa su lugar con un skeleton en vez de aparecer recién cuando el permiso
    confirma — eso era lo que hacía que la sidebar se poblara ítem por ítem al entrar.
  - **`Topbar`/`PlatformShell` → `userLoading` / `tenantsLoading`**: el bloque de
    usuario y el selector de cliente muestran skeleton mientras la sesión resuelve, en
    vez de un placeholder tipo "Usuario" que después cambia (flash de dato incompleto).
  - Sin cambios de comportamiento para un consumidor que no pase las props nuevas.
- **0.15.0 · La sidebar acepta links y submenús.** `NavItem.href` (pestaña nueva con
  ⌘/Ctrl+clic o botón del medio, que con un `<button>` era imposible) y
  `NavItem.children` (dos niveles). Sale también del tablero, cuyo menú es un árbol —el
  tenant de turismo agrupa siete pestañas bajo «Encuesta MinTur»— y que hasta ahora no
  podía adoptar la sidebar del sistema sin aplanarlo. Es lo que le faltaba al `NavGroup`
  cuando el CRM tuvo que resignar su grupo «Administración» plegable: ahora está acá y no
  parcheado en cada copia.
- **0.14.0 · White-label por cliente.** Un módulo que se vende con la marca del cliente
  ya no tiene que forkear el chrome: `brand` cambia el lockup y los tokens `--tenant-*`
  cambian el color (acento y sidebar). Sale del tablero (Ombú), que se rebrandea por
  tenant —CIMET Colonia corre en azul— y por eso era el único módulo que no podía adoptar
  `PlatformShell`. **El menú de módulos no se rebrandea:** ahí el usuario elige entre
  módulos Margay, así que cada uno sale con su nombre y su descriptor de plataforma.
  Módulo que no lo usa, no cambia en nada.
- **0.13.0 · El switcher abre en pestaña nueva.** Saltar de módulo no puede costarte lo
  que tenías a medio hacer en el actual: un formulario abierto, un filtro armado, una
  tarjeta en el medio de un drag. Los destinos van con `target="_blank"` y `rel="noopener
  noreferrer"` explícito (no por el default del browser). Aplica también a la fila del Hub.
  - **La fila del módulo actual deja de ser un link.** Ya estás ahí, y con pestaña nueva
    un link sería un duplicado de la pestaña que ya tenés abierta. Queda como fila
    marcada (`aria-current="page"` + check), sin hover de destino.
- **0.12.0 · El cliente activo sale de la URL.** Los destinos del switcher van a la
  `entryUrl` pelada; el cliente viaja en la cookie compartida de `.margaystudio.io`, que
  todos los módulos ya leen. Poner el slug en el path (0.10.0–0.11.0) era una promesa que
  ningún módulo cumplía: **ninguno rutea ese segmento**, así que cada salto del switcher
  caía en 404 del lado del destino. Sin cambios en tokens, emblemas ni el resto del chrome.
  - **`hrefDe(m)`** ya no toma `tenant` y **`<ModuleSwitcher>` pierde la prop `tenant`**:
    no afectaba nada más que al href. Breaking para quien lo use directo; `<PlatformShell>`
    absorbe el cambio (sigue tomando `tenant`, ahora solo para marcar el activo).
  - **El selector de cliente exige `onTenantChange`.** Antes, sin handler, navegaba a
    `${entryUrl}/${slug}`; sin slug ese fallback no cambia de cliente, así que sería un
    control que no hace nada. Escribir la cookie es de la app, no de la librería — misma
    regla que el chevron de `account.onSwitch`.
  - Los links siguen siendo `<a href>` reales a otro subdominio: eso no cambia.
- **0.11.0 · El chrome de plataforma, como presentación pura.** Ajuste del contrato de
  `<PlatformShell>` y `<ModuleSwitcher>` a la forma que ya usa la plataforma. La librería
  recibe props y pinta: no hace fetch, no conoce servicios, no decide qué mostrar.
  - **Tipos alineados** (declarados acá, sin dependencias de otros repos):
    `ModuleRef { key: string; name: string; entryUrl: string; unavailable?: boolean }`,
    `TenantRef { id; name; slug }`, `PlatformUser { displayName; email; avatarUrl? }`.
    `key` pasa a `string`: **la lista de módulos la define la app, no la librería.**
  - **Todo lo visible es opcional.** Sin `modules` (o con uno solo) el lockup no abre
    menú; sin `tenants` no hay selector de cliente; sin `hubUrl` no hay salida al Hub;
    sin `nav` no hay sidebar; sin `user` no hay bloque de usuario.
  - **Reparto de responsabilidades en el lockup:** el **nombre** lo trae la app y se pinta
    tal cual; el **emblema, el color y el descriptor** los aporta la librería. Nuevo
    `MODULE_DESC: Record<ModuleKey, string>` junto a `ModuleEmblem` — copy de identidad,
    no dato de negocio. Clave sin descriptor → fila sin descriptor.
  - **Tolerancia a claves desconocidas** (`isModuleKey`): una key que la librería no
    dibuja se pinta con tile neutro en vez de romper. Agregar un módulo no puede tirar
    abajo el switcher.
  - **`displayName` se pinta tal cual** — sin concatenar, formatear ni derivar. Las
    iniciales del avatar las calcula la librería **solo** si no viene `avatarUrl`.
  - **`unavailable?`**: la app marca qué módulo no aplica al cliente activo y la librería
    lo pinta (fila atenuada + «No disponible»). La librería no calcula disponibilidad.
  - **Destino:** `${entryUrl sin barra final}/${tenant.slug}`, o la `entryUrl` pelada si
    no hay cliente. Sigue siendo `<a href>` real: cambia el subdominio.
    *(Revertido en 0.12.0: el slug sale de la URL.)*
  - `<Topbar user>` pasa a opcional (aditivo: los consumidores actuales lo pasan siempre).
  - Sin cambios en tokens, emblemas ni componentes base.
- **0.10.0 · `<PlatformShell>` + `<ModuleSwitcher>`.** El chrome deja de estar
  reimplementado en cada repo de módulo y pasa a ser un componente del sistema; el módulo
  aporta configuración (`module`, `nav`, sesión), no layout. Con eso desaparecen de una
  los síntomas que veníamos arreglando de a uno: el nombre del módulo distinto en cada
  topbar, el descriptor presente en dos de tres, el colapso que existía en Ombú y
  Commercial pero no en Pindó, el avatar que alternaba entre foto e iniciales.
  - **`ModuleSwitcher`**: lockup con emblema + nombre + descriptor **del registro del
    Hub**, menú de módulos con enlaces reales (`<a href>`, cambian de subdominio) y el
    cliente activo en el path (`${url}/${slug}`). Última fila = salida al Hub con el logo
    Margay. Cada fila lleva su `data-module` y sale en su propio color.
  - **`PlatformShell`**: compone `AppShell` + `Topbar` + `Sidebar` + `ModuleSwitcher`.
    Maneja el drawer mobile y el colapso de la sidebar (persistido en `localStorage`,
    porque saltar de módulo es una recarga completa).
  - **Props opt-in y retrocompatibles** en dos componentes de chrome: `<Topbar lockup>` —
    sin ella el lockup sigue siendo emblema + `title`— y `<Sidebar collapsed
    onToggleCollapse>` — sin handler no hay botón, igual que la regla del chevron de
    `account.onSwitch`. Ningún consumidor actual cambia de render.
  - **Deliberado, contra el spec:** el selector de cliente **no** muestra chevron cuando
    hay un solo cliente. El spec pedía "siempre con chevron", pero la regla del sistema
    (sin handler no hay flechita muerta) ya estaba y vale para los dos casos.
  - Sin cambios en tokens, escalas ni componentes base.
- **0.9.0 · Identidad de módulos cerrada (siete módulos con nombre, emblema y color).**
  Sync desde `react-handoff-v2/SYNC-IDENTIDAD.md`. No cambia el stack ni las escalas
  (espaciado, tipografía, radios, sombras) ni los componentes fuera de `ModuleEmblem`.
  - **Claves nuevas:** `ombu · arrayan · gpu · timbo · ceibo · pindo · data`.
    Migración: `process→arrayan`, `oms→pindo`, `insights→ceibo`, `commercial→timbo`,
    `dashboards→ombu`; `gpu` se mantiene; `hub` deja de ser módulo (es plataforma).
  - **Paleta nueva de acentos:** siete tonos separados 28–55° en el círculo cromático,
    todos AA sobre el tile al 30%. Se retiran `--acc-green/periwinkle/coral/violet/
    peach/teal/sky`. El verde de marca ya no lo usa ningún módulo — pasa a ser el
    acento por defecto de `:root` (sin `data-module`).
  - **`ModuleEmblem.tsx` reemplazado:** cambian claves y dibujos. **No tiene alias**:
    una clave vieja (`process`, `oms`, `insights`, `hub`, `commercial`) no compila.
  - **Alias de compatibilidad en `tokens.css`** para las seis claves viejas: cubren el
    *color* mientras se migran los usos en los módulos. Retiralos cuando no queden.
  - **Assets:** 21 SVG en `public/brand/modules/` (3 por módulo: plano, tile y el nuevo
    `-favicon`). Se eliminan los de las claves retiradas (`hub`, `process`, `oms`,
    `insights`, `dashboards`) — su trazo llevaba los hex de la paleta vieja.
  - `tailwind-preset.ts` sin cambios: `accent`/`accent-ink`/`accent-tint` ya mapean a
    las CSS vars y heredan los valores nuevos solos.
- **0.8.0 · Margay Commercial + drawer mobile del shell.** Llega desde `margay-crm`, donde
  estos cambios vivían **sólo en la copia local** de `ui/shared/ui/` (violando la regla de
  oro: nunca editar la copia). Se portan al source para que dejen de perderse en cada
  re-sync y para que el resto de los módulos los aproveche:
  - **Módulo `commercial` (sky).** `--acc-sky #8EC4DA`, `[data-module="commercial"]` con
    `--accent-ink #3E7E9B` y tint `rgba(142,196,218,.26)`, más el emblema (embudo del
    pipeline) en `ModuleEmblem.tsx`. **Ojo:** la copia de margay-crm había *reemplazado* la
    línea del módulo `data` por la de `commercial` en lugar de agregarla; acá conviven los
    dos. Pendiente: los SVG planos `public/brand/modules/commercial{,-tile}.svg`.
  - **Drawer mobile en `AppShell` + hamburguesa en `Topbar`.** Opt-in y retrocompatible: sin
    las props nuevas (`mobileNav`, `mobileNavOpen`, `onMobileNavClose`, `onMenuClick`) el
    render es idéntico al histórico. Incluye cierre con Escape, scroll-lock del body,
    overlay clickeable y `role="dialog"` + `aria-modal`.
  - **`h-screen` → `h-dvh` en `AppShell`.** Aplica a TODOS los módulos: en desktop es
    idéntico, en mobile evita que la barra de URL recorte el alto del shell.
- **Margay Data (slice 3.5b, margay-core/backoffice/web):** faltaban los SVG estáticos del
  módulo `data` (teal) en `public/brand/modules/` — el emblema ya existía en
  `ModuleEmblem.tsx` pero sin su contraparte plana/tile. Se agregaron `data.svg` y
  `data-tile.svg` siguiendo el mismo patrón que el resto de los módulos (mismo trazo del
  emblema, `--acc-teal #82BEC9` / `--accent-ink #2D7486` / tint `rgba(130,190,201,.24)`).
