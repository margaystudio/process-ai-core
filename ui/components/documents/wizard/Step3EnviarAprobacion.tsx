"use client";

import { useEffect, useMemo, useRef } from "react";
import { useWorkspaceMembers } from "@/hooks/useWorkspaceMembers";
import { WizardIcon } from "./WizardIcon";

export interface Step3State {
  /** Nombre legible de la carpeta destino (para mostrar) */
  folderName: string;
  sent: boolean;
  /** Ids de aprobadores seleccionados (sugeridos). Default = todos los elegibles. */
  approvers: string[];
  /** Comentario opcional del autor para los aprobadores. */
  comment: string;
}

const APPROVER_ROLES = new Set(["owner", "admin", "approver"]);

const ROLE_LABELS: Record<string, string> = {
  owner: "Dueño",
  admin: "Administrador",
  approver: "Aprobador",
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

/**
 * Paso 3: envío a aprobación + confirmación.
 * Cableado a submitVersionForReview / cancelDocumentSubmission vía el orquestador.
 *
 * La selección de aprobadores es sugerida/informativa: no restringe quién puede
 * aprobar (cualquiera con permiso documents.approve puede hacerlo). Por eso no
 * se fuerza "al menos uno" y el default es todos los elegibles pre-seleccionados.
 */
export function Step3EnviarAprobacion({
  s,
  documentName,
  submitError,
  onWithdraw,
  withdrawing,
  withdrawError,
  onApproversChange,
  onCommentChange,
}: {
  s: Step3State;
  /** Nombre del documento — lo sabe el wizard; evita un getDocument extra en este paso. */
  documentName: string;
  submitError: string | null;
  onWithdraw: () => void;
  withdrawing: boolean;
  withdrawError: string | null;
  /** Callback para levantar el estado de ids seleccionados al orquestador. */
  onApproversChange: (ids: string[]) => void;
  /** Callback para levantar el comentario al orquestador. */
  onCommentChange: (comment: string) => void;
}) {
  // Aprobadores cacheados/prefetcheados (useWorkspaceMembers): sin fetch en cada entrada al paso.
  const { members, loading: loadingApprovers } = useWorkspaceMembers();

  const eligibleMembers = useMemo(
    () => members.filter((m) => APPROVER_ROLES.has(m.role.toLowerCase())),
    [members],
  );

  // Pre-seleccionar todos los elegibles una vez que cargaron (default: sugerencia a todos).
  const didInitApprovers = useRef(false);
  useEffect(() => {
    if (didInitApprovers.current || loadingApprovers) return;
    didInitApprovers.current = true;
    onApproversChange(eligibleMembers.map((m) => m.user_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingApprovers, eligibleMembers]);

  const title = documentName || "Borrador";

  // Conjunto para lookup O(1)
  const selectedSet = new Set(s.approvers);

  const toggleApprover = (userId: string) => {
    const next = selectedSet.has(userId)
      ? s.approvers.filter((id) => id !== userId)
      : [...s.approvers, userId];
    onApproversChange(next);
  };

  // Aprobadores seleccionados (para el bloque de confirmación)
  const selectedMembers = eligibleMembers.filter((m) =>
    selectedSet.has(m.user_id),
  );

  return (
    <div className="mx-auto max-w-[720px] px-[30px] py-7">
      {/* Encabezado del paso */}
      <div className="mb-[18px]">
        <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
          Paso 3 · Enviar a aprobación
        </div>
        <div className="text-2xl font-extrabold text-ink-900">
          Enviá el documento al circuito de aprobación
        </div>
      </div>

      {!s.sent ? (
        /* ---- Formulario de envío ---- */
        <>
          {submitError && (
            <div
              role="alert"
              className="mb-4 rounded-[12px] border border-danger-bd bg-danger-bg px-4 py-3 text-[13px] text-danger"
            >
              {submitError}
            </div>
          )}

          {/* Encabezado del documento */}
          <div className="mb-4 flex items-center gap-3 rounded-[14px] border border-line bg-surface p-[16px_20px] shadow-card">
            <span className="grid h-[38px] w-[38px] flex-shrink-0 place-items-center rounded-[10px] bg-indigo-tint text-indigo">
              <WizardIcon
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6"
                size={19}
              />
            </span>
            <div className="flex-1">
              <div className="text-base font-extrabold text-ink-900">
                {title}
              </div>
              <div className="text-xs text-ink-400">
                Borrador · en {s.folderName || "—"}
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-line-softer px-2.5 py-1 text-[11.5px] font-bold text-ink-500">
              <span className="h-1.5 w-1.5 rounded-full bg-ink-300" />
              Borrador
            </span>
          </div>

          {/* Selector de aprobadores */}
          <div className="mb-4 rounded-[14px] border border-line bg-surface p-[20px_22px] shadow-card">
            <div className="text-sm font-extrabold text-ink-900">
              Aprobadores disponibles
            </div>
            <div className="mb-3.5 text-xs text-ink-400">
              Según la carpeta{" "}
              <strong className="text-ink-500">{s.folderName || "—"}</strong> y
              los permisos. Elegí uno o varios.
            </div>

            {loadingApprovers ? (
              <div className="animate-pulse space-y-2">
                <div className="h-[52px] rounded-[11px] bg-line-softer" />
                <div className="h-[52px] rounded-[11px] bg-line-softer" />
              </div>
            ) : eligibleMembers.length === 0 ? (
              <p className="text-[13px] text-ink-400">
                No hay aprobadores configurados en este workspace.
              </p>
            ) : (
              <div className="flex flex-col gap-2" role="group" aria-label="Aprobadores sugeridos">
                {eligibleMembers.map((m) => {
                  const isSelected = selectedSet.has(m.user_id);
                  const displayName = m.name?.trim() || m.email;
                  return (
                    <button
                      key={m.user_id}
                      type="button"
                      onClick={() => toggleApprover(m.user_id)}
                      aria-pressed={isSelected}
                      className={
                        "flex items-center gap-3 rounded-[11px] border p-[10px_12px] text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action " +
                        (isSelected
                          ? "border-indigo-light bg-indigo-tint"
                          : "border-line bg-surface hover:bg-surface-hover")
                      }
                    >
                      {/* Checkbox */}
                      <span
                        className={
                          "grid h-[22px] w-[22px] flex-shrink-0 place-items-center rounded-[7px] " +
                          (isSelected
                            ? "bg-indigo"
                            : "border-[1.5px] border-line-input bg-surface")
                        }
                        aria-hidden="true"
                      >
                        {isSelected && (
                          <WizardIcon
                            d="M20 6L9 17l-5-5"
                            size={13}
                            className="text-white"
                            strokeWidth={3}
                          />
                        )}
                      </span>
                      {/* Avatar */}
                      <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-indigo text-[11px] font-bold text-white">
                        {getInitials(displayName)}
                      </span>
                      {/* Info */}
                      <span className="flex-1">
                        <span className="block text-[13.5px] font-bold text-ink-900">
                          {displayName}
                        </span>
                        <span className="block text-[11.5px] text-ink-400">
                          {ROLE_LABELS[m.role] ?? m.role}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Comentario opcional */}
          <div className="mb-4 rounded-[14px] border border-line bg-surface p-[20px_22px] shadow-card">
            <div className="mb-2 text-[13px] font-bold text-ink-900">
              Comentario para los aprobadores{" "}
              <span className="font-medium text-ink-400">(opcional)</span>
            </div>
            <textarea
              value={s.comment}
              onChange={(e) => onCommentChange(e.target.value)}
              placeholder="Ej: Revisar especialmente el procedimiento de arqueo."
              rows={3}
              className="min-h-[70px] w-full resize-y rounded-[10px] border border-line-input bg-surface p-[11px_13px] text-[13.5px] leading-normal text-ink-700 placeholder:text-ink-400 outline-none transition-colors hover:border-ink-300 focus:border-indigo focus:ring-2 focus:ring-indigo/20"
            />
          </div>

          {/* Aviso */}
          <div className="flex items-start gap-2.5 rounded-xl border border-line-soft bg-surface-hover p-[13px_16px]">
            <WizardIcon
              d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 16v-4M12 8h.01"
              size={17}
              className="mt-px flex-shrink-0 text-warning"
            />
            <div className="text-[12.5px] leading-relaxed text-ink-500">
              El documento queda{" "}
              <strong className="text-ink-800">en revisión</strong> hasta que
              un aprobador lo apruebe. El versionado oficial empieza recién
              ahí.
            </div>
          </div>
        </>
      ) : (
        /* ---- Confirmación de envío ---- */
        <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card animate-in">
          <div className="flex items-center gap-3 border-b border-line-soft p-[24px_26px]">
            <span className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-full bg-green">
              <WizardIcon
                d="M20 6L9 17l-5-5"
                size={22}
                className="text-white"
                strokeWidth={2.6}
              />
            </span>
            <div>
              <div className="text-lg font-extrabold text-ink-900">
                El documento quedó enviado a aprobación
              </div>
              <div className="text-[12.5px] text-ink-400">
                {title} · en revisión
              </div>
            </div>
          </div>

          <div className="p-[22px_26px]">
            {/* Aprobadores seleccionados (chips) */}
            <div className="mb-2.5 text-[11px] font-bold uppercase tracking-[.06em] text-ink-400">
              Aprobadores seleccionados
            </div>
            <div className="mb-[22px]">
              {selectedMembers.length === 0 ? (
                <p className="text-[13px] text-ink-400">
                  Ninguno seleccionado — cualquier aprobador del workspace puede aprobar.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {selectedMembers.map((m) => (
                    <span
                      key={m.user_id}
                      className="inline-flex items-center gap-2 rounded-pill border border-line py-[5px] pl-[5px] pr-3"
                    >
                      <span className="grid h-6 w-6 place-items-center rounded-full bg-indigo text-[10px] font-bold text-white">
                        {getInitials(m.name?.trim() || m.email)}
                      </span>
                      <span className="text-[13px] font-semibold text-ink-700">
                        {m.name?.trim() || m.email}
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Comentario del autor (si hay) */}
            {s.comment.trim() && (
              <div className="mb-[22px]">
                <div className="mb-1.5 text-[11px] font-bold uppercase tracking-[.06em] text-ink-400">
                  Comentario del autor
                </div>
                <p className="rounded-[10px] border border-line bg-surface-hover px-[13px] py-[11px] text-[13px] leading-relaxed text-ink-700">
                  {s.comment}
                </p>
              </div>
            )}

            <div className="mb-[11px] text-[13px] font-bold text-ink-900">
              Cuando alguno lo apruebe:
            </div>
            <div className="flex flex-col gap-2.5">
              {(
                [
                  {
                    d: "M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
                    cls: "bg-green-100 text-green-700",
                    t: (
                      <>
                        Se convierte en la{" "}
                        <strong>versión oficial</strong> (arranca el
                        versionado).
                      </>
                    ),
                  },
                  {
                    d: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
                    cls: "bg-ink-800 text-white",
                    t: (
                      <>
                        Queda <strong>disponible para Tyto</strong> como fuente
                        oficial.
                      </>
                    ),
                  },
                  {
                    d: "M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3z",
                    cls: "bg-indigo-tint text-indigo",
                    t: (
                      <>
                        La IA genera las{" "}
                        <strong>relaciones sugeridas</strong> para la red
                        documental.
                      </>
                    ),
                  },
                ] as const
              ).map((r, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span
                    className={`grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-[7px] ${r.cls}`}
                  >
                    <WizardIcon d={r.d} size={15} />
                  </span>
                  <div className="pt-[3px] text-[13.5px] leading-snug text-ink-700">
                    {r.t}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {withdrawError && (
            <div
              role="alert"
              className="border-t border-danger-bd bg-danger-bg px-[26px] py-2.5 text-[12.5px] text-danger"
            >
              {withdrawError}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-line-soft bg-surface-hover p-[16px_26px]">
            <span className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-pill border border-warning-bd bg-warning-bg px-[11px] py-[5px] text-xs font-bold text-warning">
              <span className="h-1.5 w-1.5 rounded-full bg-warning" />
              Pendiente de aprobación
            </span>
            <span className="text-[11.5px] leading-snug text-ink-400">
              Mientras esté pendiente no podrá editarse.
            </span>
            <button
              type="button"
              onClick={onWithdraw}
              disabled={withdrawing}
              className="ml-auto inline-flex h-10 flex-shrink-0 items-center gap-1.5 rounded-[10px] border border-line-input bg-surface px-[15px] text-[13px] font-bold text-ink-700 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:cursor-not-allowed disabled:opacity-50"
            >
              <WizardIcon
                d="M3 2v6h6M3.51 15a9 9 0 1 0 2.13-9.36L3 8"
                size={14}
                className="text-ink-500"
              />
              {withdrawing ? "Retirando…" : "Retirar solicitud"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
