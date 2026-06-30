// Biblioteca — landing screen. Folder tree (left) + document list (right).
// Filters by state, local search, density toggle, per-row actions menu.
import React, { useMemo, useState } from "react";
import { DOCS, FOLDERS, Folder, folderPath, FOLDER_ICON_PATHS, Icon, ICONS } from "../lib/data";
import { Chip, StatusBadge } from "../components/ui";

type View = "lista" | "carpetas" | "recientes" | "pendientes";
type Density = "detallada" | "compacta";
const ESTADOS = ["Todos", "Aprobado", "Pendiente", "Borrador", "Archivado"] as const;
const EXTRA_FILTERS = ["Tipo documental", "Responsable", "Autor", "Aprobador", "Fecha", "Consultas IA"];

function FolderTree({ selected, onSelect }: { selected: string; onSelect: (path: string) => void }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ procesos: true, contratos: true });
  const children = (pid: string | null) => FOLDERS.filter((f) => f.parent === pid);

  const renderRow = (f: Folder, depth: number): React.ReactNode => {
    const kids = children(f.id);
    const isOpen = !!expanded[f.id];
    const path = folderPath(f);
    const sel = selected === path;
    return (
      <React.Fragment key={f.id}>
        <div className="flex w-full items-center gap-px" style={{ paddingLeft: depth * 14 }}>
          <span
            onClick={() => kids.length && setExpanded((e) => ({ ...e, [f.id]: !e[f.id] }))}
            className={"grid h-7 w-[18px] flex-shrink-0 place-items-center transition-transform " + (kids.length ? "cursor-pointer" : "pointer-events-none opacity-0")}
            style={{ transform: `rotate(${isOpen ? 90 : 0}deg)` }}
          >
            <Icon d={ICONS.chevronR} size={11} className="text-ink-400" strokeWidth={2.6} />
          </span>
          <button
            onClick={() => onSelect(path)}
            className={"flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 py-[7px] text-[12.5px] " + (sel ? "bg-indigo-tint font-bold text-ink-800" : "font-semibold text-ink-700 hover:bg-surface-hover")}
          >
            <span className="flex-shrink-0" style={{ color: f.color }}><Icon d={FOLDER_ICON_PATHS[f.icon]} size={14} /></span>
            <span className="min-w-0 flex-1 truncate text-left">{f.name}</span>
            <span className="flex-shrink-0 text-[10.5px] font-bold text-ink-300">{f.docs}</span>
          </button>
        </div>
        {isOpen && kids.map((k) => renderRow(k, depth + 1))}
      </React.Fragment>
    );
  };

  return (
    <div className="sticky top-0 max-h-screen w-[228px] flex-shrink-0 self-start overflow-y-auto border-r border-line bg-surface p-3 pt-[22px]">
      <div className="px-2 pb-3.5 text-[11px] font-bold uppercase tracking-[.08em] text-ink-400">Estructura</div>
      <button
        onClick={() => onSelect("Todas")}
        className={"mb-1 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] " + (selected === "Todas" ? "bg-indigo-tint font-bold text-ink-800" : "font-semibold text-ink-700")}
      >
        <Icon d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" size={15} />
        <span className="flex-1 text-left">Biblioteca completa</span>
        <span className="text-[10.5px] font-bold text-ink-300">{DOCS.length}</span>
      </button>
      {children(null).map((f) => renderRow(f, 0))}
    </div>
  );
}

export default function BibliotecaScreen() {
  const [folder, setFolder] = useState("Todas");
  const [estado, setEstado] = useState<(typeof ESTADOS)[number]>("Todos");
  const [view, setView] = useState<View>("lista");
  const [density, setDensity] = useState<Density>("detallada");
  const [query, setQuery] = useState("");
  const [menuId, setMenuId] = useState<string | null>(null);

  const docs = useMemo(() => {
    const q = query.toLowerCase().trim();
    return DOCS.filter((d) => {
      const estOk = view === "pendientes" ? d.estado === "Pendiente" : estado === "Todos" || d.estado === estado;
      const carpOk = folder === "Todas" || d.carpeta.startsWith(folder);
      return estOk && carpOk && (!q || d.name.toLowerCase().includes(q));
    });
  }, [folder, estado, view, query]);

  const counts = {
    apr: docs.filter((d) => d.estado === "Aprobado").length,
    pen: docs.filter((d) => d.estado === "Pendiente").length,
    bor: docs.filter((d) => d.estado === "Borrador").length,
  };
  const compact = density === "compacta";
  const scopeLabel = folder === "Todas" ? "Biblioteca" : folder.split(" / ").join(" › ");

  return (
    <div className="flex min-h-full items-stretch">
      <FolderTree selected={folder} onSelect={setFolder} />

      <div className="min-w-0 max-w-[940px] flex-1 px-8 pb-[50px] pt-7">
        {/* header */}
        <div className="mb-[18px]">
          <div className="mb-1.5 text-xs font-bold uppercase tracking-[.1em] text-ink-400">{scopeLabel}</div>
          <h1 className="text-[25px] font-extrabold text-ink-900">Biblioteca</h1>
          <p className="mt-1.5 text-[13px] text-ink-400">Toda la documentación oficial de la organización. El documento oficial es la fuente de verdad.</p>
        </div>

        {/* view selector */}
        <div className="mb-[18px] inline-flex items-center gap-0.5 rounded-[10px] bg-surface-track p-[3px]">
          {(["lista", "carpetas", "recientes", "pendientes"] as View[]).map((v) => (
            <button key={v} onClick={() => setView(v)} className={"h-8 rounded-lg px-[15px] text-[12.5px] font-bold capitalize transition-all " + (view === v ? "bg-surface text-ink-800 shadow-card" : "text-ink-400")}>{v}</button>
          ))}
        </div>

        {/* local search */}
        <div className="relative mb-3.5">
          <Icon d={ICONS.search} size={16} className="absolute left-3.5 top-3.5 text-ink-300" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar documentos…" className="h-[42px] w-full rounded-[10px] border border-line bg-surface pl-[38px] pr-3.5 text-[13.5px] text-ink-800 outline-none" />
        </div>

        {/* state chips */}
        <div className="mb-3 flex flex-wrap gap-[7px]">
          {ESTADOS.map((s) => <Chip key={s} active={estado === s} onClick={() => setEstado(s)}>{s}</Chip>)}
        </div>

        {/* extra filters */}
        <div className="mb-[18px] flex flex-wrap items-center gap-2">
          <span className="mr-0.5 text-[11px] text-ink-300">Filtros:</span>
          {EXTRA_FILTERS.map((f) => (
            <button key={f} className="inline-flex h-[30px] items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-[11.5px] font-semibold text-ink-500">
              {f}<Icon d="M6 9l6 6 6-6" size={11} className="text-ink-300" strokeWidth={2.4} />
            </button>
          ))}
        </div>

        {/* summary + density */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-[11.5px] text-ink-400">
            Mostrando {docs.length} de {DOCS.length} documentos
            <span className="text-ink-200"> · </span><span className="font-bold text-green-text">{counts.apr} aprobados</span>
            <span className="text-ink-200"> · </span><span className="font-bold text-amber">{counts.pen} pendientes</span>
            <span className="text-ink-200"> · </span><span className="font-bold text-indigo">{counts.bor} borradores</span>
          </div>
          <div className="inline-flex items-center gap-0.5 rounded-lg bg-surface-track p-0.5">
            {([["detallada", "M8 6h13M8 12h13M8 18h10"], ["compacta", "M4 5h16M4 9h16M4 13h16M4 17h16"]] as const).map(([k, d]) => (
              <button key={k} onClick={() => setDensity(k)} title={`Vista ${k}`} className={"grid h-[26px] w-[30px] place-items-center rounded-md transition-all " + (density === k ? "bg-surface text-ink-800 shadow-card" : "text-ink-300")}>
                <Icon d={d} size={15} />
              </button>
            ))}
          </div>
        </div>

        {/* list */}
        {docs.length > 0 ? (
          <div className={"flex flex-col " + (compact ? "gap-1.5" : "gap-[9px]")}>
            {docs.map((d) => {
              const segs = d.carpeta.split(" / ");
              const versionLabel = d.estado === "Aprobado" ? `${d.version !== "—" ? d.version : "v1"} • Oficial` : d.estado === "Pendiente" ? "En revisión" : d.estado === "Archivado" ? "Archivado" : "Sin versión aún";
              return (
                <div key={d.id} className={"relative flex items-center border border-line bg-surface " + (compact ? "gap-3 rounded-[11px] px-4 py-[9px]" : "gap-[15px] rounded-[13px] px-[18px] py-3.5")}>
                  <span className={"grid flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo " + (compact ? "h-[30px] w-[30px]" : "h-10 w-10")}>
                    <Icon d={ICONS.doc} size={compact ? 16 : 19} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={"truncate font-bold text-ink-900 " + (compact ? "text-[13px]" : "text-sm")}>{d.name}</span>
                      {d.estado !== "Archivado" && (
                        <span className="inline-flex flex-shrink-0 items-center gap-[3px] rounded-[5px] border border-indigo-border bg-indigo-tint px-1.5 py-px text-[9.5px] font-extrabold text-indigo" title="Disponible para consultas inteligentes">
                          <Icon d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0" size={9} />IA
                        </span>
                      )}
                    </div>
                    {!compact && (
                      <>
                        <div className="mt-[5px] flex items-center gap-1">
                          {segs.map((s, i) => (
                            <React.Fragment key={i}>
                              <button onClick={() => setFolder(segs.slice(0, i + 1).join(" / "))} className="text-[11.5px] font-semibold text-ink-400">{s}</button>
                              {i < segs.length - 1 && <span className="text-[11px] text-ink-200">›</span>}
                            </React.Fragment>
                          ))}
                        </div>
                        <div className="mt-1.5"><VersionPill estado={d.estado} label={versionLabel} /></div>
                        <div className="mt-1.5 text-[11px] text-ink-300">{d.by} · {d.fecha}</div>
                      </>
                    )}
                    {compact && (
                      <div className="mt-0.5 flex items-center gap-[7px] truncate text-[11px] text-ink-300">
                        <span className="text-ink-400">{segs.join(" › ")}</span><span>·</span><VersionPill estado={d.estado} label={versionLabel} /><span>·</span><span>{d.by} · {d.fecha}</span>
                      </div>
                    )}
                  </div>
                  <StatusBadge estado={d.estado} />
                  <button className="inline-flex h-[34px] flex-shrink-0 items-center gap-[7px] rounded-[9px] border border-line bg-surface px-4 text-[12.5px] font-bold text-ink-700">Abrir</button>
                  <button onClick={() => setMenuId(menuId === d.id ? null : d.id)} className="grid h-[34px] w-[34px] flex-shrink-0 place-items-center rounded-[9px] border border-line bg-surface text-ink-500">
                    <Icon d={ICONS.dots} size={16} strokeWidth={2.4} />
                  </button>
                  {menuId === d.id && <RowMenu estado={d.estado} onClose={() => setMenuId(null)} />}
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}

function VersionPill({ estado, label }: { estado: string; label: string }) {
  const tone = estado === "Aprobado" ? { c: "#1E7A47", bg: "#E7F4ED" } : estado === "Pendiente" ? { c: "#9A6A00", bg: "#FBF3DD" } : { c: "#8A8F91", bg: "#F2F4F5" };
  return <span className="rounded-md px-2 py-0.5 text-[10.5px] font-bold" style={{ color: tone.c, background: tone.bg }}>{label}</span>;
}

function RowMenu({ estado, onClose }: { estado: string; onClose: () => void }) {
  // groups separated: consulta / edición / administración
  const groups: { label: string; danger?: boolean }[][] = [
    [{ label: "Abrir documento" }, { label: "Ver historial" }],
    [...(estado === "Aprobado" || estado === "Pendiente" ? [{ label: "Crear nueva versión" }] : []), { label: "Copiar enlace" }],
    [{ label: "Mover" }, { label: "Archivar" }, ...(estado === "Borrador" ? [{ label: "Eliminar", danger: true }] : [])],
  ];
  return (
    <div className="absolute right-3.5 top-[calc(100%-4px)] z-20 w-[212px] rounded-[11px] border border-line bg-surface p-1.5 shadow-menu" onMouseLeave={onClose}>
      {groups.map((g, gi) => (
        <React.Fragment key={gi}>
          {gi > 0 && <div className="mx-2 my-[5px] h-px bg-line-soft" />}
          {g.map((a) => (
            <button key={a.label} onClick={onClose} className={"w-full rounded-md px-2.5 py-2 text-left text-[12.5px] font-semibold " + (a.danger ? "text-red" : "text-ink-800")}>{a.label}</button>
          ))}
        </React.Fragment>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border-[1.5px] border-dashed border-line-input bg-surface-hover px-6 py-[54px] text-center">
      <span className="mx-auto mb-3.5 grid h-[54px] w-[54px] place-items-center rounded-2xl border border-line bg-surface text-ink-300">
        <Icon d={ICONS.folder} size={26} strokeWidth={1.6} />
      </span>
      <div className="mb-1 text-[15px] font-extrabold text-ink-800">Esta carpeta todavía no tiene documentos</div>
      <div className="mb-5 text-[13px] text-ink-400">Creá conocimiento desde cero o incorporá documentación existente.</div>
      <div className="flex items-center justify-center gap-2.5">
        <button className="inline-flex h-[42px] items-center gap-2 rounded-[10px] bg-ink-800 px-[18px] text-[13.5px] font-bold text-white"><Icon d={ICONS.plus} size={16} />Crear documento</button>
        <button className="inline-flex h-[42px] items-center gap-2 rounded-[10px] border border-line-input bg-surface px-[18px] text-[13.5px] font-bold text-ink-700"><Icon d={ICONS.upload} size={16} />Importar documentación</button>
      </div>
    </div>
  );
}
