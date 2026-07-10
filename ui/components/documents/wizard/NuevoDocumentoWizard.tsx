"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FILE_TYPE_TO_FORM_FIELD, type EvidenceInput } from "./data";
import {
  cancelDocumentSubmission,
  createProcessRun,
  getDocumentVersions,
  processEvidenceFile,
  submitVersionForReview,
} from "@/lib/api";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useUserId } from "@/hooks/useUserId";
import { prefetchWorkspaceMembers } from "@/hooks/useWorkspaceMembers";
import { WizardContainer } from "./WizardContainer";
import { Step1NuevoDocumento, type Step1State } from "./Step1NuevoDocumento";
import { Step2Revision } from "./Step2Revision";
import {
  Step3EnviarAprobacion,
  type Step3State,
} from "./Step3EnviarAprobacion";
import { GeneratingOverlay } from "./GeneratingOverlay";
import { AddEvidenceModal } from "./AddEvidenceModal";

/**
 * Orquestador del wizard "Nuevo documento".
 *
 * Step 1: evidencias reales + createProcessRun.
 * Step 2: revisión y edición del borrador (getEditableContent / saveEditableContent).
 * Step 3: envío a aprobación (submitVersionForReview / cancelDocumentSubmission).
 */
export default function NuevoDocumentoWizard() {
  const router = useRouter();
  const userId = useUserId();
  const { selectedWorkspaceId } = useWorkspace();

  // Prefetch de aprobadores al abrir el wizard → el Paso 3 renderiza instantáneo.
  useEffect(() => {
    prefetchWorkspaceMembers(selectedWorkspaceId);
  }, [selectedWorkspaceId]);

  const [step, setStep] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);

  // ---- Estado Step 1 ----
  const [s1, setS1] = useState<Step1State>({
    name: "",
    folderId: "",
    folderName: "",
    contexto: "",
    advancedOpen: false,
    detailLevel: "",
    documentType: "procedimiento",
    evidences: [],
  });

  // ---- Estado Step 3 ----
  const [s3, setS3] = useState<Step3State>({
    folderName: "",
    sent: false,
    approvers: [],
    comment: "",
  });

  // ---- Estado de generación ----
  const [generating, setGenerating] = useState(false);
  /** true cuando createProcessRun() resolvió (éxito o error) */
  const [genDone, setGenDone] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);

  // ---- Estado Step 3: envío / retiro ----
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  /** Versión IN_REVIEW tras submit — necesaria para cancelDocumentSubmission */
  const [draftVersionId, setDraftVersionId] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  const addEvidence = (input: EvidenceInput) => {
    const evidence = { ...input, processingStatus: "processing" as const };
    setS1((s) => ({ ...s, evidences: [...s.evidences, evidence] }));

    void processEvidenceFile(evidence.file, evidence.fileType)
      .then((result) => {
        setS1((s) => ({
          ...s,
          evidences: s.evidences.map((x) =>
            x.id === evidence.id
              ? {
                  ...x,
                  processingStatus:
                    result.status === "error" ? "error" : result.status,
                  extractedText: result.extracted_text || undefined,
                  metadata: result.metadata,
                  processingError: result.error ?? undefined,
                }
              : x,
          ),
        }));
      })
      .catch((err) => {
        setS1((s) => ({
          ...s,
          evidences: s.evidences.map((x) =>
            x.id === evidence.id
              ? {
                  ...x,
                  processingStatus: "error" as const,
                  processingError:
                    err instanceof Error
                      ? err.message
                      : "Error al procesar la evidencia",
                }
              : x,
          ),
        }));
      });
  };

  const removeEvidence = (id: string) =>
    setS1((s) => ({ ...s, evidences: s.evidences.filter((x) => x.id !== id) }));

  const generateDraft = async () => {
    if (!s1.name.trim() || !s1.folderId) return;

    setGenError(null);
    setGenDone(false);
    setGenerating(true);

    try {
      const formData = new FormData();
      formData.append("process_name", s1.name.trim());
      formData.append("mode", "operativo");
      formData.append("folder_id", s1.folderId);
      formData.append("document_type", s1.documentType);
      if (s1.detailLevel) formData.append("detail_level", s1.detailLevel);
      if (s1.contexto.trim()) formData.append("context_text", s1.contexto.trim());

      for (const ev of s1.evidences) {
        const field = FILE_TYPE_TO_FORM_FIELD[ev.fileType];
        formData.append(field, ev.file);
        const extractedText =
          ev.processingStatus === "done" && ev.extractedText
            ? ev.extractedText
            : "";
        formData.append(`${field}_extracted_text`, extractedText);
      }

      const result = await createProcessRun(formData);

      if (!result.document_id) {
        throw new Error(
          "La generación no devolvió un documento. Intentá de nuevo.",
        );
      }

      setDocumentId(result.document_id);
      setS3({ folderName: s1.folderName, sent: false, approvers: [], comment: "" });
      setDraftVersionId(null);
      setSubmitError(null);
      setWithdrawError(null);
      setStep(2);
    } catch (err) {
      setGenError(
        err instanceof Error ? err.message : "Error al generar el borrador",
      );
    } finally {
      // Señalamos al overlay que el backend respondió (éxito o error) para
      // que complete visualmente el stepper antes de desmontarse.
      setGenDone(true);
      // Pequeña pausa para que el usuario vea el estado "completado" del overlay
      // antes de que desaparezca. Solo aplica si el overlay está montado.
      await new Promise<void>((r) => setTimeout(r, 600));
      setGenerating(false);
    }
  };

  const sendForApproval = async () => {
    if (!documentId || !userId || !selectedWorkspaceId) {
      setSubmitError("Falta información de usuario o workspace.");
      return;
    }

    setSubmitError(null);
    setSubmittingApproval(true);

    try {
      const versions = await getDocumentVersions(documentId);
      const draft = versions.find((v) => v.version_status === "DRAFT");
      if (!draft) {
        throw new Error("No se encontró un borrador para enviar.");
      }

      const result = await submitVersionForReview(
        documentId,
        draft.id,
        userId,
        selectedWorkspaceId,
        s3.approvers,
        s3.comment,
      );

      setDraftVersionId(result.version.id);
      setS3((s) => ({ ...s, sent: true }));
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Error al enviar a aprobación",
      );
    } finally {
      setSubmittingApproval(false);
    }
  };

  const withdrawSubmission = async () => {
    if (!documentId || !draftVersionId || !userId || !selectedWorkspaceId) {
      return;
    }

    setWithdrawError(null);
    setWithdrawing(true);

    try {
      await cancelDocumentSubmission(
        documentId,
        draftVersionId,
        userId,
        selectedWorkspaceId,
      );
      setS3((s) => ({ ...s, sent: false }));
      setDraftVersionId(null);
    } catch (err) {
      setWithdrawError(
        err instanceof Error ? err.message : "Error al retirar la solicitud",
      );
    } finally {
      setWithdrawing(false);
    }
  };

  if (generating) {
    const hasVideo = s1.evidences.some((ev) => ev.fileType === "video");
    return <GeneratingOverlay hasVideo={hasVideo} done={genDone} />;
  }

  const canGenerate = Boolean(s1.name.trim() && s1.folderId);

  const footer =
    step === 1
      ? {
          primaryLabel: "Crear borrador",
          hint: s1.folderId
            ? "Cargá evidencias y creá el borrador"
            : "Seleccioná una ubicación para continuar",
          onPrimary: generateDraft,
          disabled: !canGenerate,
          hideBack: true,
        }
      : step === 2
      ? {
          primaryLabel: "Continuar",
          hint: "Cuando el borrador esté listo, continuá",
          onPrimary: () => setStep(3),
          onBack: () => setStep(1),
        }
      : s3.sent
      ? {
          primaryLabel: "Volver a documentos",
          hint: "El documento quedó pendiente de aprobación",
          onPrimary: () => {
            if (documentId) router.push(`/documents/${documentId}`);
          },
          hideBack: true,
        }
      : {
          primaryLabel: submittingApproval
            ? "Enviando…"
            : "Enviar a aprobación",
          hint: "Se enviará al circuito de aprobación del workspace",
          onPrimary: sendForApproval,
          onBack: () => setStep(2),
          disabled: submittingApproval || !documentId,
        };

  return (
    <>
      <WizardContainer step={step} footer={footer}>
        {step === 1 && (
          <>
            <Step1NuevoDocumento
              s={s1}
              set={(p) => setS1((s) => ({ ...s, ...p }))}
              onAddEvidence={() => setModalOpen(true)}
              onRemoveEvidence={removeEvidence}
            />
            {genError && (
              <div className="mx-auto max-w-[1200px] px-[30px] pb-4">
                <div
                  role="alert"
                  className="rounded-[12px] border border-danger-bd bg-danger-bg px-4 py-3"
                >
                  <p className="text-[13px] font-semibold text-danger">
                    Error al generar el borrador
                  </p>
                  <p className="mt-0.5 text-[12.5px] text-danger">
                    {genError}
                  </p>
                </div>
              </div>
            )}
          </>
        )}
        {step === 2 && (
          <Step2Revision
            evidences={s1.evidences}
            documentId={documentId}
          />
        )}
        {step === 3 && (
          <Step3EnviarAprobacion
            s={s3}
            documentName={s1.name}
            submitError={submitError}
            onWithdraw={withdrawSubmission}
            withdrawing={withdrawing}
            withdrawError={withdrawError}
            onApproversChange={(ids) => setS3((prev) => ({ ...prev, approvers: ids }))}
            onCommentChange={(comment) => setS3((prev) => ({ ...prev, comment }))}
          />
        )}
      </WizardContainer>

      {modalOpen && (
        <AddEvidenceModal
          onClose={() => setModalOpen(false)}
          onAdd={addEvidence}
        />
      )}
    </>
  );
}
