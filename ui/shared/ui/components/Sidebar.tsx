// components/Sidebar.tsx
// Chrome: panel lateral OSCURO. Arriba = la cuenta/tenant que operás (solo si hay
// cliente). Al pie = firma Margay (logo + empresa). El usuario NO va acá (va en Topbar).
// Colores desde tokens de sidebar (--sidebar-*) y acento por data-module.
// Colapso: opt-in vía `onToggleCollapse` (el estado lo maneja el consumidor, o
// `<PlatformShell>`, que además lo persiste). Sin esa prop el render es el histórico.
import * as React from "react";
import { ChevronDown, ExternalLink, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { cn } from "../cn";

export interface NavItem {
  label: string;
  icon?: React.ReactNode;
  active?: boolean;
  external?: boolean;
  /**
   * Ruta destino. Con esto el ítem sale como `<a href>` y el navegador puede abrirlo en
   * otra pestaña (⌘/Ctrl+clic, botón del medio, "Abrir en pestaña nueva") — con un
   * `<button>` eso es imposible. El clic normal lo sigue manejando `onClick`, así el
   * módulo conserva su navegación client-side; los clics con modificador caen al
   * comportamiento nativo del link.
   */
  href?: string;
  onClick?: () => void;
  /**
   * Sub-ítems. Un ítem con hijos es un contenedor: no navega, el clic abre y cierra. Dos
   * niveles y no más: un árbol más profundo en 224px deja de leerse.
   */
  children?: NavItem[];
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Una pestaña navegable. Con `href` sale como `<a>` para que el navegador pueda abrirla en
 * otra pestaña; el clic normal lo sigue resolviendo `onClick` (navegación client-side del
 * módulo) y los clics con modificador caen al comportamiento nativo del link.
 */
function Hoja({
  item,
  collapsed,
  esHijo = false,
}: {
  item: NavItem;
  collapsed: boolean;
  esHijo?: boolean;
}) {
  const clases = cn(
    "relative flex items-center rounded-md py-2 text-left font-semibold transition-colors hover:bg-sidebar-hover hover:text-white",
    esHijo ? "text-[12.5px]" : "text-[13px]",
    collapsed ? "justify-center gap-0 px-0" : "gap-2.5 px-2.5",
    item.active ? "bg-white/[0.09] text-white shadow-[inset_3px_0_0_var(--accent)]" : "text-white/65"
  );

  const contenido = (
    <>
      <span
        className={cn(
          "shrink-0",
          esHijo ? "[&_svg]:h-[15px] [&_svg]:w-[15px]" : "[&_svg]:h-[18px] [&_svg]:w-[18px]",
          item.active ? "text-accent" : "text-white/50"
        )}
        aria-hidden="true"
      >
        {item.icon}
      </span>
      {!collapsed && (
        <>
          <span className="truncate">{item.label}</span>
          {item.external && <ExternalLink className="ml-auto h-3.5 w-3.5 text-white/40" />}
        </>
      )}
    </>
  );

  if (!item.href) {
    return (
      <button
        type="button"
        onClick={item.onClick}
        title={collapsed ? item.label : undefined}
        aria-label={collapsed ? item.label : undefined}
        className={clases}
      >
        {contenido}
      </button>
    );
  }

  return (
    <a
      href={item.href}
      target={item.external ? "_blank" : undefined}
      rel={item.external ? "noopener noreferrer" : undefined}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      aria-current={item.active ? "page" : undefined}
      className={clases}
      onClick={(e) => {
        if (item.external || !item.onClick) return;
        // ⌘/Ctrl/Shift/Alt o botón que no sea el principal: lo resuelve el navegador.
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
        e.preventDefault();
        item.onClick();
      }}
    >
      {contenido}
    </a>
  );
}

/** Iniciales a partir de un nombre. Solo para el fallback del avatar/tile. */
export function initialsOf(name: string) {
  return name
    .replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ ]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function Sidebar({
  account,
  groups,
  company = "Margay Studio",
  logoSrc = "/brand/margay-icon-48.png",
  collapsed = false,
  onToggleCollapse,
}: {
  /**
   * Cuenta/cliente que se opera. Omitir en módulos internos (Hub propio, GPU interno) o
   * cuando el switch de organización vive en el topbar. El chevron de switcher solo
   * aparece si se pasa `onSwitch` (evita una flechita muerta).
   */
  account?: { name: string; sub?: string; onSwitch?: () => void };
  groups: NavGroup[];
  company?: string;
  logoSrc?: string;
  /** Rail de 64px: solo iconos, sin etiquetas. El estado lo maneja el consumidor. */
  collapsed?: boolean;
  /** Si se pasa, aparece el botón de colapso al pie. Sin handler no hay botón muerto. */
  onToggleCollapse?: () => void;
}) {
  // `abiertos` es la ÚNICA fuente de verdad de qué padres están desplegados. Un padre con
  // un hijo activo se auto-abre al navegar hacia ese hijo (efecto de abajo), pero el
  // usuario siempre puede cerrarlo a mano aunque siga viendo una de sus pestañas.
  const [abiertos, setAbiertos] = React.useState<Set<string>>(new Set());

  const alternarAbierto = (key: string) =>
    setAbiertos((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  // Padres que albergan al ítem activo.
  const padresDelActivo = React.useMemo(() => {
    const keys: string[] = [];
    groups.forEach((g, gi) =>
      g.items.forEach((it, ii) => {
        if (it.children?.length && it.children.some((c) => c.active)) keys.push(`${gi}-${ii}`);
      })
    );
    return keys;
  }, [groups]);

  // Auto-abre un padre SOLO cuando el hijo activo entra en él (o sea, al navegar), no en
  // cada render: si el usuario lo cerró a mano, no se reabre por seguir ahí parado.
  const padresPrevios = React.useRef<string[]>([]);
  React.useEffect(() => {
    const nuevos = padresDelActivo.filter((k) => !padresPrevios.current.includes(k));
    if (nuevos.length) {
      setAbiertos((prev) => {
        const next = new Set(prev);
        nuevos.forEach((k) => next.add(k));
        return next;
      });
    }
    padresPrevios.current = padresDelActivo;
  }, [padresDelActivo]);

  const accountInner = account && (
    <>
      <span
        className="grid h-9 w-9 shrink-0 place-items-center rounded-[10px] bg-white/10 text-xs font-bold"
        title={collapsed ? account.name : undefined}
      >
        {initialsOf(account.name)}
      </span>
      {!collapsed && (
        <>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-sm font-bold">{account.name}</div>
            {account.sub && <div className="text-xs text-white/50">{account.sub}</div>}
          </div>
          {account.onSwitch && <ChevronDown className="h-4 w-4 text-white/40" />}
        </>
      )}
    </>
  );

  return (
    <aside
      className={cn(
        "print:hidden flex shrink-0 flex-col bg-sidebar-surface pb-3 pt-3.5 text-sidebar-fg transition-[width] duration-150",
        collapsed ? "w-[64px] px-2" : "w-[224px] px-3"
      )}
    >
      {account &&
        (account.onSwitch ? (
          <button
            type="button"
            onClick={account.onSwitch}
            className={cn(
              "flex items-center gap-2.5 rounded-md py-1 pb-3.5 text-left transition-colors hover:bg-sidebar-hover",
              collapsed ? "justify-center px-0" : "px-1.5"
            )}
          >
            {accountInner}
          </button>
        ) : (
          <div
            className={cn(
              "flex items-center gap-2.5 pb-3.5",
              collapsed ? "justify-center px-0" : "px-1.5"
            )}
          >
            {accountInner}
          </div>
        ))}

      <nav className="flex flex-col gap-0.5">
        {groups.map((g, gi) => (
          <React.Fragment key={gi}>
            {collapsed ? (
              // Sin espacio para la etiqueta del grupo, la separación la hace una línea.
              gi > 0 && <div className="mx-1.5 my-2 border-t border-sidebar-border" />
            ) : (
              <div className="px-2.5 pb-1.5 pt-3.5 text-[10px] font-bold uppercase tracking-[.1em] text-white/30">
                {g.label}
              </div>
            )}
            {g.items.map((it, ii) => {
              const key = `${gi}-${ii}`;
              const conHijos = !!it.children?.length;
              if (!conHijos) return <Hoja key={key} item={it} collapsed={collapsed} />;

              const abierto = abiertos.has(key);
              return (
                <React.Fragment key={key}>
                  {/* El padre no navega: abre y cierra. Su estado activo lo dan los hijos. */}
                  <button
                    type="button"
                    onClick={() => {
                      // Colapsada no hay lugar para el submenú: primero se expande.
                      if (collapsed) {
                        onToggleCollapse?.();
                        setAbiertos((prev) => new Set(prev).add(key));
                        return;
                      }
                      alternarAbierto(key);
                    }}
                    title={collapsed ? it.label : undefined}
                    aria-label={collapsed ? it.label : undefined}
                    aria-expanded={collapsed ? undefined : abierto}
                    className={cn(
                      "relative flex items-center gap-2.5 rounded-md py-2 text-left text-[13px] font-semibold text-white/65 transition-colors hover:bg-sidebar-hover hover:text-white",
                      collapsed ? "justify-center px-0" : "px-2.5",
                      it.active && "text-white"
                    )}
                  >
                    <span
                      className={cn(
                        "[&_svg]:h-[18px] [&_svg]:w-[18px]",
                        it.active ? "text-accent" : "text-white/50"
                      )}
                    >
                      {it.icon}
                    </span>
                    {!collapsed && (
                      <>
                        <span>{it.label}</span>
                        <ChevronDown
                          className={cn(
                            "ml-auto h-3.5 w-3.5 text-white/40 transition-transform",
                            abierto && "rotate-180"
                          )}
                        />
                      </>
                    )}
                  </button>

                  {/* Hijos: solo con la sidebar expandida y el padre abierto. */}
                  {!collapsed && abierto && (
                    <div className="ml-[18px] flex flex-col gap-0.5 border-l border-sidebar-border pl-1.5">
                      {it.children!.map((hijo, ci) => (
                        <Hoja key={`${key}-${ci}`} item={hijo} collapsed={false} esHijo />
                      ))}
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </React.Fragment>
        ))}
      </nav>

      <div className="flex-1" />

      {onToggleCollapse && (
        <button
          type="button"
          onClick={onToggleCollapse}
          title={collapsed ? "Expandir menú" : "Colapsar menú"}
          aria-label={collapsed ? "Expandir menú" : "Colapsar menú"}
          aria-expanded={!collapsed}
          className={cn(
            "flex items-center gap-2.5 rounded-md py-2 text-[13px] font-semibold text-white/50 transition-colors hover:bg-sidebar-hover hover:text-white",
            collapsed ? "justify-center px-0" : "px-2.5"
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px]" />
          ) : (
            <PanelLeftClose className="h-[18px] w-[18px]" />
          )}
          {!collapsed && <span>Colapsar</span>}
        </button>
      )}

      <div
        className={cn(
          "mt-1.5 flex items-center gap-2.5 border-t border-sidebar-border pb-0.5 pt-3",
          collapsed ? "justify-center px-0" : "px-1.5"
        )}
      >
        <img
          src={logoSrc}
          alt=""
          className="h-[30px] w-[30px] shrink-0 rounded-md"
          title={collapsed ? `${company} · Plataforma Margay` : undefined}
        />
        {!collapsed && (
          <div className="leading-tight">
            <div className="text-[13px] font-bold">{company}</div>
            <div className="text-[10.5px] text-white/45">Plataforma Margay</div>
          </div>
        )}
      </div>
    </aside>
  );
}
