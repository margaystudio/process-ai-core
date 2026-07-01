"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getDocument,
  getEditableContent,
  saveEditableContent,
} from "@/lib/api";
import ManualEditorTiptap, {
  type ManualEditorTiptapRef,
} from "@/components/documents/ManualEditorTiptap";
import { usePdfViewer } from "@/hooks/usePdfViewer";
import { type Evidence } from "./data";
import { EvidenceCardCompact } from "./EvidenceCard";
import { WizardIcon } from "./WizardIcon";

/**
 * Paso 2: resumen de generación + editor del borrador (toggle Editar / Listo).
 * Carga el borrador real vía getDocument + getEditableContent y persiste con saveEditableContent.
 */
export function Step2Revision({
  evidences,
  documentId,
}: {
  evidences: Evidence[];
  /** document_id devuelto por createProcessRun */
  documentId: string | null;
}) {
  const [editing, setEditing] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);

  const [title, setTitle] = useState("");
  const [html, setHtml] = useState("");
  const [versionId, setVersionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const editorRef = useRef<ManualEditorTiptapRef | null>(null);
  const { openVersionPreviewPdf, ModalComponent } = usePdfViewer();

  const loadDraft = useCallback(async () => {
    if (!documentId) return;

    setLoading(true);
    setError(null);
    setEditing(false);
    setDirty(false);

    try {
      const [doc, editable] = await Promise.all([
        getDocument(documentId),
        getEditableContent(documentId),
      ]);
      setTitle(doc.name);
      setHtml(editable.html);
      setVersionId(editable.version_id);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Error al cargar el borrador",
      );
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void loadDraft();
  }, [loadDraft]);

  const handleSave = useCallback(
    async (newHtml: string) => {
      if (!documentId) return;

      setSaving(true);
      setError(null);

      try {
        await saveEditableContent(documentId, newHtml);
        setHtml(newHtml);
        setDirty(false);
        setEditing(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error al guardar");
      } finally {
        setSaving(false);
      }
    },
    [documentId],
  );

  const handleListo = () => {
    const currentHtml = editorRef.current?.getHtml() ?? html;
    void handleSave(currentHtml);
  };

  const handleCancel = () => {
    setEditing(false);
    setDirty(false);
  };

  const canEdit = Boolean(documentId && html && !loading);

  return (
    <div className="mx-auto max-w-[900px] px-[30px] py-7">
      {/* Encabezado del paso */}
      <div className="mb-[18px]">
        <div className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-400">
          Paso 2 · Revisión
        </div>
        <div className="text-2xl font-extrabold text-ink-900">
          Revisá el documento antes de enviarlo a aprobación
        </div>
      </div>

      {/* Resumen de generación */}
      <div className="mb-4 rounded-[14px] border border-line bg-surface p-[16px_20px] shadow-card">
        <div className="mb-3 flex items-center gap-2.5">
          <WizardIcon
            d="M5 3l1.2 3.2L9 7.5 5.8 8.8 5 12 4.2 8.8 1 7.5l3.2-1.3zM17 11l1 2.6L21 15l-2.6 1L17 19l-1-2.6L13 15l2.6-1z"
            size={16}
            className="text-indigo"
          />
          <span className="text-[13.5px] font-extrabold text-ink-900">
            Resumen de generación
          </span>
          <span className="ml-auto text-[11.5px] text-ink-400">
            Generado hace 18 segundos
          </span>
        </div>

        <div className="grid gap-[18px] sm:grid-cols-2">
          {/* Evidencias usadas */}
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-[.04em] text-ink-400">
                Se usaron · {evidences.length} evidencias
              </span>
              <button
                type="button"
                onClick={() => setShowEvidence((v) => !v)}
                className="text-[11px] font-bold text-indigo hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo"
              >
                {showEvidence ? "Ocultar" : "Ver evidencias"}
              </button>
            </div>
            {!showEvidence ? (
              <div className="flex flex-col gap-1.5">
                {["1 audio transcripto", "1 PDF", "3 imágenes"].map((t) => (
                  <div
                    key={t}
                    className="flex items-center gap-2 text-[13px] text-ink-700"
                  >
                    <WizardIcon
                      d="M20 6L9 17l-5-5"
                      size={14}
                      className="flex-shrink-0 text-success"
                      strokeWidth={2.6}
                    />
                    {t}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 animate-in">
                {evidences.map((e) => (
                  <EvidenceCardCompact key={e.id} evidence={e} />
                ))}
              </div>
            )}
          </div>

          {/* Lo que organizó la IA */}
          <div>
            <div className="mb-2 text-[11px] font-bold uppercase tracking-[.04em] text-ink-400">
              La IA organizó
            </div>
            <div className="flex gap-2">
              {(
                [
                  ["3", "secciones"],
                  ["12", "pasos"],
                  [String(evidences.length), "evidencias"],
                ] as const
              ).map(([v, l]) => (
                <div
                  key={l}
                  className="flex-1 rounded-[10px] border border-line-soft p-[8px_4px] text-center"
                >
                  <div className="text-lg font-extrabold text-indigo">{v}</div>
                  <div className="text-[10.5px] text-ink-400">{l}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Editor del borrador */}
      <div className="overflow-hidden rounded-[14px] border border-line bg-surface shadow-card">
        {!documentId ? (
          <div className="p-[22px_26px] text-sm text-ink-500">
            No hay documento para revisar. Volvé al paso anterior y creá un
            borrador.
          </div>
        ) : loading ? (
          <div className="p-[22px_26px]">
            <div className="animate-pulse space-y-4">
              <div className="h-6 w-1/3 rounded bg-line-softer" />
              <div className="h-4 w-full rounded bg-line-softer" />
              <div className="h-4 w-full rounded bg-line-softer" />
              <div className="h-48 rounded bg-line-softer" />
            </div>
            <p className="mt-4 text-center text-sm text-ink-400">
              Cargando borrador...
            </p>
          </div>
        ) : error && !html ? (
          <div className="p-[22px_26px]">
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
            <button
              type="button"
              onClick={() => void loadDraft()}
              className="mt-3 h-[34px] rounded-[9px] border border-line-input bg-surface px-3.5 text-[13px] font-semibold text-ink-700 transition-colors hover:bg-surface-hover"
            >
              Reintentar
            </button>
          </div>
        ) : (
          <>
            {/* Header del editor */}
            <div className="flex flex-wrap items-center gap-2.5 border-b border-line-soft p-[16px_22px]">
              <span className="text-lg font-extrabold text-ink-900">
                {title || "Borrador"}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-line-softer px-2.5 py-[3px] text-[11.5px] font-bold text-ink-500">
                <span className="h-1.5 w-1.5 rounded-full bg-ink-300" />
                Borrador
              </span>
              {versionId && documentId && !editing && (
                <button
                  type="button"
                  onClick={() =>
                    openVersionPreviewPdf(documentId, versionId)
                  }
                  className="inline-flex h-[34px] items-center gap-1.5 rounded-[9px] border border-line-input bg-surface px-3 text-[12.5px] font-semibold text-ink-600 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action"
                >
                  <WizardIcon
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6"
                    size={14}
                    className="text-indigo"
                  />
                  Ver PDF
                </button>
              )}
              <span className="flex-1" />
              {!editing ? (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  disabled={!canEdit}
                  className="inline-flex h-[34px] items-center gap-1.5 rounded-[9px] border border-line-input bg-surface px-3.5 text-[13px] font-bold text-ink-800 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <WizardIcon
                    d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"
                    size={14}
                    className="text-indigo"
                  />
                  Editar
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={handleCancel}
                    disabled={saving}
                    className="h-[34px] rounded-[9px] border border-line-input bg-surface px-[13px] text-[13px] font-semibold text-ink-500 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={handleListo}
                    disabled={saving}
                    className="h-[34px] rounded-[9px] bg-ink-800 px-3.5 text-[13px] font-bold text-white transition-colors hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saving ? "Guardando..." : "Listo"}
                  </button>
                </>
              )}
            </div>

            {error && html && (
              <div
                className="border-b border-danger-bd bg-danger-bg px-[22px] py-2.5 text-[12.5px] text-danger"
                role="alert"
              >
                {error}
              </div>
            )}

            {/* Cuerpo del borrador */}
            <div className="p-[22px_26px]">
              {!editing ? (
                <article
                  className="wizard-draft-html text-sm leading-7 text-ink-700"
                  dangerouslySetInnerHTML={{ __html: html }}
                />
              ) : (
                <ManualEditorTiptap
                  key={`${documentId}-edit`}
                  documentId={documentId}
                  initialHtml={html}
                  onSave={handleSave}
                  onDirtyChange={setDirty}
                  saving={saving}
                  editorRef={editorRef}
                />
              )}
              {editing && dirty && !saving && (
                <p className="mt-2 text-[12px] text-ink-400">
                  Hay cambios sin guardar. Usá &quot;Listo&quot; para
                  persistirlos.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      <ModalComponent />

      <style jsx global>{`
        .wizard-draft-html p {
          margin-bottom: 0.75em;
        }
        .wizard-draft-html h1 {
          font-size: 1.5rem;
          font-weight: 800;
          margin-top: 1.25em;
          margin-bottom: 0.5em;
          color: var(--ink-900);
        }
        .wizard-draft-html h2 {
          font-size: 1.25rem;
          font-weight: 700;
          margin-top: 1.25em;
          margin-bottom: 0.5em;
          color: var(--ink-900);
        }
        .wizard-draft-html h3 {
          font-size: 0.8125rem;
          font-weight: 800;
          margin-top: 1em;
          margin-bottom: 0.375em;
          color: var(--indigo);
        }
        .wizard-draft-html h4 {
          font-size: 1rem;
          font-weight: 600;
          margin-top: 0.875em;
          margin-bottom: 0.375em;
        }
        .wizard-draft-html ul {
          list-style-type: disc;
          padding-left: 1.5rem;
          margin-bottom: 0.75em;
        }
        .wizard-draft-html ol {
          list-style-type: decimal;
          padding-left: 1.5rem;
          margin-bottom: 0.75em;
        }
        .wizard-draft-html a {
          color: var(--indigo);
          text-decoration: underline;
        }
        .wizard-draft-html img {
          max-width: 100%;
          height: auto;
          border-radius: 4px;
        }
        .wizard-draft-html table {
          border-collapse: collapse;
          width: 100%;
          margin: 1em 0;
        }
        .wizard-draft-html th,
        .wizard-draft-html td {
          border: 1px solid var(--line);
          padding: 8px 12px;
          text-align: left;
        }
        .wizard-draft-html th {
          background: var(--surface-track);
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}
