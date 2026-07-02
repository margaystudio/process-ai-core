"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FILE_TYPE_TO_FORM_FIELD, type Evidence } from "./data";
import {
  cancelDocumentSubmission,
  createProcessRun,
  getDocumentVersions,
  submitVersionForReview,
} from "@/lib/api";
import { useWorkspace } from "@/contexts/WorkspaceContext";
import { useUserId } from "@/hooks/useUserId";
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
    smartQueries: true,
    evidences: [],
  });

  // ---- Estado Step 3 ----
  const [s3, setS3] = useState<Step3State>({
    folderName: "",
    sent: false,
  });

  // ---- Estado de generación ----
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);

  // ---- Estado Step 3: envío / retiro ----
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  /** Versión IN_REVIEW tras submit — necesaria para cancelDocumentSubmission */
  const [draftVersionId, setDraftVersionId] = useState<string | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);

  const addEvidence = (e: Evidence) => {
    setS1((s) => ({ ...s, evidences: [...s.evidences, e] }));
  };

  const removeEvidence = (id: string) =>
    setS1((s) => ({ ...s, evidences: s.evidences.filter((x) => x.id !== id) }));

  const generateDraft = async () => {
    if (!s1.name.trim() || !s1.folderId) return;

    setGenError(null);
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
      }

      const result = await createProcessRun(formData);

      if (!result.document_id) {
        throw new Error(
          "La generación no devolvió un documento. Intentá de nuevo.",
        );
      }

      setDocumentId(result.document_id);
      setS3({ folderName: s1.folderName, sent: false });
      setDraftVersionId(null);
      setSubmitError(null);
      setWithdrawError(null);
      setStep(2);
    } catch (err) {
      setGenError(
        err instanceof Error ? err.message : "Error al generar el borrador",
      );
    } finally {
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
    return <GeneratingOverlay current={0} />;
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
            documentId={documentId}
            submitError={submitError}
            onWithdraw={withdrawSubmission}
            withdrawing={withdrawing}
            withdrawError={withdrawError}
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
