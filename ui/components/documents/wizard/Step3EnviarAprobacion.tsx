"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getDocument,
  getWorkspaceMembers,
  type WorkspaceMember,
} from "@/lib/api";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { WizardIcon } from "./WizardIcon";

export interface Step3State {
  /** Nombre legible de la carpeta destino (para mostrar) */
  folderName: string;
  sent: boolean;
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

function ApproverChips({ members }: { members: WorkspaceMember[] }) {
  if (members.length === 0) {
    return (
      <p className="text-[13px] text-ink-400">
        No hay aprobadores configurados en este workspace.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {members.map((m) => (
        <span
          key={m.user_id}
          className="inline-flex items-center gap-2 rounded-pill border border-line py-[5px] pl-[5px] pr-3"
        >
          <span className="grid h-6 w-6 place-items-center rounded-full bg-indigo text-[10px] font-bold text-white">
            {getInitials(m.name || m.email)}
          </span>
          <span className="text-[13px] font-semibold text-ink-700">
            {m.name?.trim() || m.email}
          </span>
          <span className="text-[11px] text-ink-400">
            {ROLE_LABELS[m.role] ?? m.role}
          </span>
        </span>
      ))}
    </div>
  );
}

/**
 * Paso 3: envío a aprobación + confirmación.
 * Cableado a submitVersionForReview / cancelDocumentSubmission vía el orquestador.
 */
export function Step3EnviarAprobacion({
  s,
  documentId,
  submitError,
  onWithdraw,
  withdrawing,
  withdrawError,
}: {
  s: Step3State;
  documentId: string | null;
  submitError: string | null;
  onWithdraw: () => void;
  withdrawing: boolean;
  withdrawError: string | null;
}) {
  const { selectedWorkspaceId } = useWorkspace();

  const [documentTitle, setDocumentTitle] = useState("");
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  const [approvers, setApprovers] = useState<WorkspaceMember[]>([]);
  const [loadingApprovers, setLoadingApprovers] = useState(false);

  const loadDocument = useCallback(async () => {
    if (!documentId) return;
    setLoadingDoc(true);
    setDocError(null);
    try {
      const doc = await getDocument(documentId);
      setDocumentTitle(doc.name);
    } catch (e) {
      setDocError(
        e instanceof Error ? e.message : "Error al cargar el documento",
      );
    } finally {
      setLoadingDoc(false);
    }
  }, [documentId]);

  const loadApprovers = useCallback(async () => {
    if (!selectedWorkspaceId) return;
    setLoadingApprovers(true);
    try {
      const { members } = await getWorkspaceMembers(selectedWorkspaceId);
      setApprovers(
        members.filter((m) => APPROVER_ROLES.has(m.role.toLowerCase())),
      );
    } catch {
      setApprovers([]);
    } finally {
      setLoadingApprovers(false);
    }
  }, [selectedWorkspaceId]);

  useEffect(() => {
    void loadDocument();
  }, [loadDocument]);

  useEffect(() => {
    void loadApprovers();
  }, [loadApprovers]);

  const title = documentTitle || "Borrador";

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
                {loadingDoc ? "Cargando…" : docError ? "Documento" : title}
              </div>
              <div className="text-xs text-ink-400">
                Borrador · en {s.folderName || "—"}
              </div>
              {docError && (
                <p className="mt-1 text-[11.5px] text-danger">{docError}</p>
              )}
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-line-softer px-2.5 py-1 text-[11.5px] font-bold text-ink-500">
              <span className="h-1.5 w-1.5 rounded-full bg-ink-300" />
              Borrador
            </span>
          </div>

          {/* Aprobadores informativos (sin picker) */}
          <div className="mb-4 rounded-[14px] border border-line bg-surface p-[20px_22px] shadow-card">
            <div className="text-sm font-extrabold text-ink-900">
              Quiénes pueden aprobar
            </div>
            <div className="mb-3.5 text-xs text-ink-400">
              Cualquiera de las siguientes personas, con permiso de aprobación
              en el workspace, podrá validarlo en la carpeta{" "}
              <strong className="text-ink-500">{s.folderName || "—"}</strong>.
            </div>
            {loadingApprovers ? (
              <div className="animate-pulse space-y-2">
                <div className="h-8 w-48 rounded bg-line-softer" />
                <div className="h-8 w-56 rounded bg-line-softer" />
              </div>
            ) : (
              <ApproverChips members={approvers} />
            )}
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
            <span className="grid h-11 w-11 flex-shrink-0 place-items-center rounded-full bg-success">
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
            <div className="mb-2.5 text-[11px] font-bold uppercase tracking-[.06em] text-ink-400">
              Quiénes pueden aprobar
            </div>
            <div className="mb-[22px]">
              <ApproverChips members={approvers} />
            </div>

            <div className="mb-[11px] text-[13px] font-bold text-ink-900">
              Cuando alguno lo apruebe:
            </div>
            <div className="flex flex-col gap-2.5">
              {(
                [
                  {
                    d: "M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
                    bg: "rgba(124,195,156,.22)",
                    c: "#2E6E4D",
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
                    bg: "#37393A",
                    c: "#fff",
                    t: (
                      <>
                        Queda <strong>disponible para Tyto</strong> como fuente
                        oficial.
                      </>
                    ),
                  },
                  {
                    d: "M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3z",
                    bg: "rgba(173,185,223,.26)",
                    c: "#48569C",
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
                    className="grid h-[26px] w-[26px] flex-shrink-0 place-items-center rounded-[7px]"
                    style={{ background: r.bg, color: r.c }}
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
