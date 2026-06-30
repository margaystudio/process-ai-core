// Usuarios y roles — roles cards + users table.
import React from "react";
import { Icon } from "../lib/data";

const ROLES = [
  { id: "admin", name: "Admin", members: "2 miembros", scope: "toda la organización", desc: "Control total: gobierno, permisos, Tyto y administración de carpetas.", caps: ["Administrar todo", "Permisos", "Gobierno", "Tyto"], tone: "#CB4242" },
  { id: "gerente", name: "Gerente", members: "4 miembros", scope: "sus áreas", desc: "Crea, importa y aprueba documentos. Administra las carpetas de su área.", caps: ["Aprobar", "Importar", "Crear", "Administrar carpeta"], tone: "#48569C" },
  { id: "encargado", name: "Encargado", members: "9 miembros", scope: "su carpeta", desc: "Aprueba documentos de su turno o área y crea contenido.", caps: ["Aprobar", "Crear", "Editar"], tone: "#2F9E62" },
  { id: "editor", name: "Editor", members: "18 miembros", scope: "carpetas asignadas", desc: "Crea y edita borradores. No aprueba ni administra.", caps: ["Crear", "Editar", "Ver"], tone: "#C99A2E" },
  { id: "lector", name: "Lector", members: "40+ miembros", scope: "según permisos", desc: "Consulta documentos oficiales y usa Tyto. Solo lectura.", caps: ["Ver", "Consultar a Tyto"], tone: "#6A6E70" },
];

const USERS = [
  ["Lucía Gómez", "lucia.gomez@empresa.com", "Gerente", "LG", "Activo", "hace 2 horas", "#48569C"],
  ["Martín Díaz", "martin.diaz@empresa.com", "Editor", "MD", "Activo", "hace 1 hora", "#C99A2E"],
  ["Juan Pérez", "juan.perez@empresa.com", "Encargado", "JP", "Activo", "ayer", "#2F9E62"],
  ["Ana Torres", "ana.torres@empresa.com", "Lector", "AT", "Activo", "hace 3 días", "#6A6E70"],
  ["Pablo Ruiz", "pablo.ruiz@empresa.com", "Admin", "PR", "Invitado", "—", "#CB4242"],
];

export default function UsuariosRolesScreen() {
  return (
    <div className="mx-auto max-w-[1080px] px-8 pb-[60px] pt-7">
      <div className="mb-[22px] flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Administración</div>
          <h1 className="text-[25px] font-extrabold text-ink-900">Usuarios y roles</h1>
          <p className="mt-1.5 text-[13px] text-ink-400">Quién accede al conocimiento y qué puede hacer. Los permisos por carpeta se ajustan en cada carpeta.</p>
        </div>
        <button className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white">
          <Icon d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 7m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M19 8v6M22 11h-6" size={16} />Invitar usuario
        </button>
      </div>

      {/* roles */}
      <div className="mb-3 text-[13px] font-extrabold text-ink-900">Roles</div>
      <div className="mb-[30px] grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))" }}>
        {ROLES.map((r) => (
          <div key={r.id} className="rounded-[14px] border border-line bg-surface p-5 shadow-card">
            <div className="mb-2.5 flex items-center gap-2.5">
              <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px]" style={{ color: r.tone, background: `${r.tone}1f` }}>
                <Icon d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" size={17} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-extrabold text-ink-900">{r.name}</div>
                <div className="text-[11.5px] text-ink-400">{r.members} · {r.scope}</div>
              </div>
            </div>
            <p className="mb-3 text-xs leading-relaxed text-ink-500">{r.desc}</p>
            <div className="flex flex-wrap gap-1.5">
              {r.caps.map((c) => <span key={c} className="rounded-md border border-indigo-border bg-indigo-tint px-2.5 py-[3px] text-[10.5px] font-bold text-indigo">{c}</span>)}
            </div>
          </div>
        ))}
      </div>

      {/* users table */}
      <div className="mb-3 flex items-center justify-between">
        <div className="text-[13px] font-extrabold text-ink-900">Usuarios</div>
        <span className="text-xs text-ink-400">{USERS.length} usuarios</span>
      </div>
      <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
        <div className="grid gap-3.5 border-b border-line-soft bg-surface-hover px-[22px] py-[11px] text-[10.5px] font-extrabold uppercase tracking-[.05em] text-ink-400" style={{ gridTemplateColumns: "2.2fr 1.3fr 1fr 1fr" }}>
          <span>Usuario</span><span>Rol</span><span>Estado</span><span>Último acceso</span>
        </div>
        {USERS.map((u, i) => {
          const activo = u[4] === "Activo";
          return (
            <div key={i} className="grid items-center gap-3.5 border-b border-line-softer px-[22px] py-3.5" style={{ gridTemplateColumns: "2.2fr 1.3fr 1fr 1fr" }}>
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-full text-xs font-extrabold text-white" style={{ background: u[6] }}>{u[3]}</span>
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-bold text-ink-800">{u[0]}</div>
                  <div className="truncate text-[11px] text-ink-300">{u[1]}</div>
                </div>
              </div>
              <div><span className="inline-flex items-center rounded-pill px-3 py-[3px] text-[11.5px] font-bold" style={{ color: u[6], background: `${u[6]}1f` }}>{u[2]}</span></div>
              <div>
                <span className={"inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-[3px] text-[11px] font-bold " + (activo ? "border-green-border bg-green-bg text-green-text" : "border-amber-border bg-amber-bg text-amber")}>{u[4]}</span>
              </div>
              <div className="text-xs text-ink-400">{u[5]}</div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[11.5px] text-ink-300">Los permisos efectivos de cada persona resultan de su rol más los accesos específicos que tenga en cada carpeta.</p>
    </div>
  );
}
