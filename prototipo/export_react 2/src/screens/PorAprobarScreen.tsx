// Por aprobar — approver inbox (NOT a library; a work queue).
import React, { useState } from "react";
import { Icon, ICONS } from "../lib/data";
import { PrimaryButton, GhostButton } from "../components/ui";

interface Pending { id: string; name: string; carpeta: string; by: string; when: string; tipo: string; circuito: string; }

const PENDING: Pending[] = [
  { id: "cierre", name: "Cierre de caja", carpeta: "Procesos › Caja", by: "Martín Díaz", when: "hace 1 h", tipo: "Procedimiento", circuito: "Doble aprobación" },
  { id: "arqueo", name: "Arqueo de turno", carpeta: "Procesos › Caja", by: "Martín Díaz", when: "hace 3 h", tipo: "Procedimiento", circuito: "Aprobación simple" },
  { id: "liq", name: "Liquidación mensual", carpeta: "RRHH › Liquidación", by: "RRHH", when: "ayer", tipo: "Política", circuito: "Doble aprobación" },
];

export default function PorAprobarScreen() {
  const [active, setActive] = useState<Pending | null>(null);

  if (active) return <ReviewPane doc={active} onBack={() => setActive(null)} />;

  return (
    <div className="mx-auto max-w-[820px] px-8 pb-[60px] pt-7">
      <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">Bandeja de aprobación</div>
      <h1 className="text-[25px] font-extrabold text-ink-900">Por aprobar</h1>
      <p className="mt-1.5 text-[13px] text-ink-400">Documentos que esperan tu decisión. Entrá a resolver, no a buscar.</p>

      <div className="mt-6 flex flex-col gap-2.5">
        {PENDING.map((p) => (
          <button key={p.id} onClick={() => setActive(p)} className="flex items-center gap-[15px] rounded-[13px] border border-line bg-surface px-[18px] py-[15px] text-left hover:border-indigo-light">
            <span className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-[11px] bg-amber-bg text-amber"><Icon d={ICONS.doc} size={20} /></span>
            <div className="min-w-0 flex-1">
              <div className="text-[14.5px] font-extrabold text-ink-900">{p.name}</div>
              <div className="mt-0.5 text-xs text-ink-400">{p.carpeta} · enviado por {p.by} · {p.when}</div>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-amber-border bg-amber-bg px-3 py-[5px] text-[11px] font-extrabold text-amber">Esperando</span>
            <Icon d={ICONS.chevronR} size={16} className="flex-shrink-0 text-ink-200" />
          </button>
        ))}
      </div>
    </div>
  );
}

function ReviewPane({ doc, onBack }: { doc: Pending; onBack: () => void }) {
  return (
    <div className="mx-auto max-w-[920px] px-8 pb-[60px] pt-7">
      <button onClick={onBack} className="mb-4 inline-flex items-center gap-1.5 text-[13px] font-bold text-ink-500">
        <Icon d="M19 12H5M11 18l-6-6 6-6" size={16} />Volver a la bandeja
      </button>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-ink-400">{doc.carpeta}</div>
          <h1 className="mt-0.5 text-[22px] font-extrabold text-ink-900">{doc.name}</h1>
          <div className="mt-2 flex items-center gap-2 text-[12.5px] text-ink-400">
            <span className="rounded-md bg-indigo-tint px-2 py-0.5 font-bold text-indigo">{doc.tipo}</span>
            <span>·</span><span>{doc.circuito}</span><span>·</span><span>por {doc.by}</span>
          </div>
        </div>
      </div>

      {/* document body preview */}
      <div className="mt-6 rounded-[14px] border border-line bg-surface p-7 shadow-card">
        <div className="mb-3 flex items-center gap-2 rounded-[10px] border border-indigo-border bg-indigo-tint px-3.5 py-2.5 text-[11.5px] text-indigo">
          <Icon d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6zM9 12l2 2 4-4" size={15} />
          Estás revisando la representación derivada. El archivo original es la fuente oficial.
        </div>
        <h2 className="text-base font-extrabold text-ink-900">{doc.name}</h2>
        <p className="mt-2.5 text-sm leading-7 text-ink-700">Procedimiento para el cierre de caja diario en la estación. Aplica al turno que cierra la jornada. Incluye arqueo de efectivo, cierre de lote del POS y registro de diferencias.</p>
        <h3 className="mt-4 text-[13px] font-extrabold text-indigo">1 · Arqueo de efectivo</h3>
        <p className="mt-1.5 text-sm leading-7 text-ink-700">Contá el efectivo en presencia del supervisor y registralo en la planilla de cierre. Separá el fondo fijo antes de declarar el total del turno.</p>
      </div>

      {/* decision bar */}
      <div className="mt-6 flex items-center justify-between gap-3">
        <GhostButton><Icon d="M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" size={16} className="text-ink-400" />Pedir cambios</GhostButton>
        <div className="flex items-center gap-3">
          <span className="text-[12.5px] text-ink-400">Tu aprobación lo convierte en documento oficial.</span>
          <PrimaryButton className="!bg-green"><Icon d={ICONS.check} size={17} strokeWidth={2.4} />Aprobar documento</PrimaryButton>
        </div>
      </div>
    </div>
  );
}
