"use client";

import { useState, useRef, useEffect } from "react";
import { INITIAL_EVIDENCE, APPROVERS, GEN_STEPS, type Evidence } from "./data";
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
 * Posee el estado completo: paso actual, overlay de generación, modal de evidencia
 * y los estados de cada step.
 *
 * TODOS LOS TODO(wire) de este archivo:
 *   - generateDraft: reemplazar el setTimeout/setInterval por la llamada real a
 *     createProcessRun (formData con archivos y metadatos del step 1).
 *   - addEvidence: el pipeline demo de 1.4 s debe reemplazarse con subida real
 *     al storage + inicio del procesamiento backend.
 *   - s1.folder: actualmente es un string demo; debe ser un folder_id real.
 *   - s3.approvers: actualmente son datos demo; deben venir del governance de la carpeta.
 *   - El footer "Volver a documentos" (step 3 enviado) debe redirigir a /documents/:id.
 */
export default function NuevoDocumentoWizard() {
  const [step, setStep] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [genStep, setGenStep] = useState(0);
  const [modalOpen, setModalOpen] = useState(false);

  const [s1, setS1] = useState<Step1State>({
    name: "Cierre de caja",
    folder: "Procesos / Caja",
    contexto: "",
    advancedOpen: false,
    detailLevel: "",
    smartQueries: true,
    evidences: INITIAL_EVIDENCE,
  });

  const [s3, setS3] = useState<Step3State>({
    folder: s1.folder,
    approvers: APPROVERS,
    comment: "",
    sent: false,
  });

  const genTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    return () => {
      if (genTimer.current) clearInterval(genTimer.current);
    };
  }, []);

  // ---- Agregar evidencia con pipeline demo ----
  // TODO(wire): reemplazar con subida real al storage + inicio de procesamiento
  const addEvidence = (e: Evidence) => {
    const pending = { ...e, processing: true };
    setS1((s) => ({ ...s, evidences: [...s.evidences, pending] }));
    setTimeout(
      () =>
        setS1((s) => ({
          ...s,
          evidences: s.evidences.map((x) =>
            x.id === e.id ? { ...x, processing: false } : x,
          ),
        })),
      1400,
    );
  };

  const removeEvidence = (id: string) =>
    setS1((s) => ({ ...s, evidences: s.evidences.filter((x) => x.id !== id) }));

  // ---- Generar borrador: pipeline demo → paso 2 ----
  // TODO(wire): reemplazar con llamada real a createProcessRun(formData)
  //             Armar el formData con: process_name, mode, folder_id, document_type,
  //             detail_level, y los archivos reales subidos como evidencias.
  const generateDraft = () => {
    setGenerating(true);
    setGenStep(0);
    let n = 0;
    genTimer.current = setInterval(() => {
      n += 1;
      if (n >= GEN_STEPS.length) {
        if (genTimer.current) clearInterval(genTimer.current);
        setGenStep(GEN_STEPS.length);
        setTimeout(() => {
          setGenerating(false);
          setGenStep(0);
          setStep(2);
        }, 450);
      } else {
        setGenStep(n);
      }
    }, 560);
  };

  // ---- Overlay de generación (reemplaza el shell completo) ----
  if (generating) return <GeneratingOverlay current={genStep} />;

  // ---- Configuración del footer por paso ----
  const footer =
    step === 1
      ? {
          primaryLabel: "Crear borrador",
          hint: s1.folder
            ? "Cargá evidencias y creá el borrador"
            : "Seleccioná una ubicación para continuar",
          onPrimary: generateDraft,
          disabled: !s1.folder,
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
          // TODO(wire): redirigir a /documents/:documentId en lugar de resetear el wizard
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
          // TODO(wire): onPrimary debe llamar a submitVersionForReview(documentId, versionId)
          onPrimary: () => setS3((s) => ({ ...s, sent: true })),
          onBack: () => setStep(2),
          disabled: !s3.approvers.some((a) => a.sel),
        };

  return (
    <>
      <WizardContainer step={step} footer={footer}>
        {step === 1 && (
          <Step1NuevoDocumento
            s={s1}
            set={(p) => setS1((s) => ({ ...s, ...p }))}
            onAddEvidence={() => setModalOpen(true)}
            onRemoveEvidence={removeEvidence}
          />
        )}
        {step === 2 && <Step2Revision evidences={s1.evidences} />}
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
