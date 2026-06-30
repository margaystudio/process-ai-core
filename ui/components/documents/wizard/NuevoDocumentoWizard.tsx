"use client";

import { useState } from "react";
import {
  APPROVERS,
  FILE_TYPE_TO_FORM_FIELD,
  type Evidence,
} from "./data";
import { createProcessRun } from "@/lib/api";
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
 * Step 1 está cableado al backend:
 *   - Evidencias arrancan vacías (archivos reales del usuario).
 *   - Carpetas reales vía listFolders (en FolderSelector).
 *   - "Crear borrador" llama a createProcessRun con los archivos reales.
 *   - GeneratingOverlay muestra mientras corre la llamada real (no setInterval).
 *
 * Step 2 y Step 3 aún son demo — se cablean en la próxima tanda.
 */
export default function NuevoDocumentoWizard() {
  const [step, setStep] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);

  // ---- Estado Step 1 (con tipos reales) ----
  const [s1, setS1] = useState<Step1State>({
    name: "",
    folderId: "",
    folderName: "",
    contexto: "",
    advancedOpen: false,
    detailLevel: "",
    documentType: "procedimiento",
    smartQueries: true,
    evidences: [],    // Arranca vacío — sin datos demo
  });

  // ---- Estado Step 3 (aún demo) ----
  const [s3, setS3] = useState<Step3State>({
    folderName: s1.folderName,
    approvers: APPROVERS,
    comment: "",
    sent: false,
  });

  // ---- Estado de generación real ----
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  /** document_id devuelto por createProcessRun — pasado a Step 2 */
  const [documentId, setDocumentId] = useState<string | null>(null);

  // ---- Agregar evidencia (archivo real, sin pipeline demo) ----
  const addEvidence = (e: Evidence) => {
    setS1((s) => ({ ...s, evidences: [...s.evidences, e] }));
  };

  const removeEvidence = (id: string) =>
    setS1((s) => ({ ...s, evidences: s.evidences.filter((x) => x.id !== id) }));

  // ---- Generar borrador: llamada real a createProcessRun ----
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

      // Agregar archivos de evidencia al FormData según su tipo
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
      // Sincronizar folderName al Step 3
      setS3((s) => ({ ...s, folderName: s1.folderName }));
      setStep(2);
    } catch (err) {
      setGenError(
        err instanceof Error ? err.message : "Error al generar el borrador",
      );
    } finally {
      setGenerating(false);
    }
  };

  // ---- Overlay de generación (corre la llamada real) ----
  if (generating) {
    // Mostramos el overlay mientras createProcessRun está en vuelo.
    // current=0 mantiene el primer paso activo durante toda la espera.
    // TODO(wire): si el backend devuelve progreso en tiempo real (websocket/SSE),
    //             actualizar `current` con el estado real del pipeline.
    return <GeneratingOverlay current={0} />;
  }

  // ---- Configuración del footer por paso ----
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
          // TODO(wire): redirigir a /documents/:documentId (usar useRouter)
          hint: "El documento quedó pendiente de aprobación",
          onPrimary: () => {
            setStep(1);
            setS3((s) => ({ ...s, sent: false }));
          },
          hideBack: true,
        }
      : {
          primaryLabel: "Enviar a aprobación",
          hint: s3.approvers.some((a) => a.sel)
            ? "Se enviará a los aprobadores elegidos"
            : "Seleccioná al menos un aprobador",
          // TODO(wire): llamar a submitVersionForReview(documentId, versionId)
          onPrimary: () => setS3((s) => ({ ...s, sent: true })),
          onBack: () => setStep(2),
          disabled: !s3.approvers.some((a) => a.sel),
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
            {/* Error de generación — mostrado en el step 1 al volver del overlay */}
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
            set={(p) => setS3((s) => ({ ...s, ...p }))}
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
