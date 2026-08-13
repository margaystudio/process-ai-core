// components/PlatformShell.tsx
// El chrome de la plataforma, entero, en un solo componente. El módulo aporta
// CONFIGURACIÓN (qué módulo es, su navegación y los datos de sesión), no código de
// layout: no define colores, ni estructura de topbar, ni firma de marca, ni colapso.
//
// PRESENTACIÓN PURA: recibe props y pinta. No hace fetch, no conoce servicios, no decide
// qué mostrar. Todo lo visible se controla por props — lo que no se pasa, no se renderiza:
//   sin `modules` (o con uno solo) → el lockup no abre menú
//   sin `tenants`                  → no hay selector de cliente
//   sin `hubUrl`                   → el menú no muestra la salida al Hub
//   sin `nav`                      → no hay sidebar (ni drawer, ni hamburguesa)
//   sin `user`                     → no hay bloque de usuario
// La app decide, la librería obedece.
//
// Es la capa de arriba de AppShell + Topbar + Sidebar + ModuleSwitcher. Si un módulo
// necesita algo que el shell no da, NO lo parchea localmente — se agrega acá. Eso es lo
// que evita que las topbars se vuelvan a desalinear entre repos.
"use client";
import * as React from "react";
import { AppShell } from "./AppShell";
import { Topbar } from "./Topbar";
import { Sidebar, initialsOf, type NavGroup } from "./Sidebar";
import { ModuleSwitcher, type BrandRef, type ModuleRef, type TenantRef } from "./ModuleSwitcher";
import type { ModuleKey } from "./ModuleEmblem";

/** Usuario de sesión, tal como lo declara la app. */
export interface PlatformUser {
  /** Se pinta tal cual: la librería no concatena, no formatea, no deriva. */
  displayName: string;
  email: string;
  avatarUrl?: string;
}

/** El colapso se persiste: saltar de módulo es una recarga (cambia el subdominio). */
const CLAVE_COLAPSO = "margay:nav-collapsed";

export function PlatformShell({
  module,
  modules,
  brand,
  tenant,
  tenants,
  user,
  hubUrl,
  nav,
  onLogout,
  onProfile,
  onTenantChange,
  userLoading,
  tenantsLoading,
  company,
  logoSrc,
  children,
}: {
  /**
   * Clave del módulo actual: fija el acento (`data-module`) y el emblema. Es `string` y
   * no `ModuleKey` porque la lista de módulos la define la app. Una clave que la librería
   * no conoce no rompe nada: el emblema cae en tile neutro y el acento, en el verde de
   * marca (ninguna regla `[data-module]` matchea).
   */
  module: string;
  /** Los módulos que la app quiere mostrar, ya resueltos los permisos. */
  modules?: ModuleRef[];
  /**
   * Marca del cliente, para los módulos white-label: el lockup pasa a hablar del cliente
   * en vez del módulo. Va junto con los tokens `--tenant-*` (ver `tokens.css`), que la
   * app setea en runtime para el color. Sin esto, el chrome es el de plataforma.
   */
  brand?: BrandRef;
  /** Cliente activo: es el que queda marcado en el selector. */
  tenant?: TenantRef;
  /** Clientes elegibles. Sin esto —o sin `onTenantChange`— no hay selector de cliente. */
  tenants?: TenantRef[];
  user?: PlatformUser;
  hubUrl?: string;
  /** La navegación propia del módulo. Sin esto no hay sidebar. */
  nav?: NavGroup[];
  onLogout?: () => void;
  onProfile?: () => void;
  /**
   * Cambio de cliente. Sin este handler NO hay selector: el cliente activo vive en la
   * cookie compartida de la plataforma y escribirla es de la app, no de la librería
   * (misma regla que el chevron de `account.onSwitch`: sin handler no hay control muerto).
   */
  onTenantChange?: (tenant: TenantRef) => void;
  /**
   * `user` todavía no resolvió: el bloque de usuario del topbar ocupa su lugar exacto
   * con un skeleton en vez de dejar un hueco o pintar un valor provisorio. Se ignora si
   * `user` ya llegó.
   */
  userLoading?: boolean;
  /** Mismo criterio que `userLoading`, para el selector de cliente. */
  tenantsLoading?: boolean;
  company?: string;
  logoSrc?: string;
  children: React.ReactNode;
}) {
  const [navMobileAbierta, setNavMobileAbierta] = React.useState(false);
  const [colapsada, setColapsada] = React.useState(false);

  // localStorage se lee en efecto (no en el estado inicial) para no romper el SSR:
  // el primer render del servidor y el del cliente tienen que coincidir.
  React.useEffect(() => {
    try {
      setColapsada(window.localStorage.getItem(CLAVE_COLAPSO) === "1");
    } catch {
      /* modo privado / storage bloqueado: se queda expandida */
    }
  }, []);

  const alternarColapso = React.useCallback(() => {
    setColapsada((c) => {
      const proxima = !c;
      try {
        window.localStorage.setItem(CLAVE_COLAPSO, proxima ? "1" : "0");
      } catch {
        /* idem */
      }
      return proxima;
    });
  }, []);

  const conNav = !!nav && nav.length > 0;

  // Iniciales solo como fallback: si hay foto, no hay nada que derivar.
  const usuarioTopbar = user && {
    name: user.displayName,
    email: user.email,
    initials: user.avatarUrl ? "" : initialsOf(user.displayName),
    avatarUrl: user.avatarUrl,
  };

  // El switcher de cliente del Topbar habla en `id`. Sin handler no se ofrece.
  const tenantsTopbar = React.useMemo(
    () => (onTenantChange ? tenants?.map((t) => ({ id: t.id, name: t.name })) : undefined),
    [tenants, onTenantChange]
  );

  function cambiarTenant(id: string) {
    const destino = tenants?.find((t) => t.id === id);
    if (destino) onTenantChange?.(destino);
  }

  const sidebar = conNav ? (
    <Sidebar
      groups={nav!}
      company={company}
      logoSrc={logoSrc}
      collapsed={colapsada}
      onToggleCollapse={alternarColapso}
    />
  ) : null;

  return (
    <AppShell
      // La clave viene de la app: si no es una conocida, `data-module` simplemente no
      // matchea ninguna regla y el acento queda en el verde de marca.
      module={module as ModuleKey}
      // El drawer solo se cablea si hay navegación que mostrar.
      mobileNavOpen={conNav ? navMobileAbierta : undefined}
      onMobileNavClose={conNav ? () => setNavMobileAbierta(false) : undefined}
      // En el drawer no hay nada que colapsar: ocupa la pantalla y se cierra.
      mobileNav={conNav ? <Sidebar groups={nav!} company={company} logoSrc={logoSrc} /> : undefined}
      topbar={
        <Topbar
          module={module as ModuleKey}
          user={usuarioTopbar}
          onLogout={onLogout}
          onProfile={onProfile}
          onMenuClick={conNav ? () => setNavMobileAbierta(true) : undefined}
          tenants={tenantsTopbar}
          activeTenantId={tenant?.id}
          onTenantChange={cambiarTenant}
          userLoading={userLoading}
          tenantsLoading={tenantsLoading}
          lockup={
            <ModuleSwitcher
              module={module}
              modules={modules}
              brand={brand}
              hubUrl={hubUrl}
              logoSrc={logoSrc}
            />
          }
        />
      }
      sidebar={sidebar}
    >
      {children}
    </AppShell>
  );
}
