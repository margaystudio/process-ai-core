// NuevoDocumentoWizard — orchestrates the full authoring flow:
//   Step 1 (form + evidence)  →  [generating overlay]  →  Step 2 (review)  →  Step 3 (send)
// Owns wizard state, the AddEvidenceModal, evidence processing, and the footer action bar.
import React, { useState, useRef, useEffect } from "react";
import { INITIAL_EVIDENCE, APPROVERS, GEN_STEPS, Evidence } from "./data";
import { WizardContainer } from "./WizardContainer";
import { Step1NuevoDocumento, Step1State } from "./Step1NuevoDocumento";
import { Step2Revision } from "./Step2Revision";
import { Step3EnviarAprobacion, Step3State } from "./Step3EnviarAprobacion";
import { GeneratingOverlay } from "./GeneratingOverlay";
import { AddEvidenceModal } from "./AddEvidenceModal";

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
  const [s3, setS3] = useState<Step3State>({ folder: s1.folder, approvers: APPROVERS, comment: "", sent: false });

  const genTimer = useRef<any>(null);
  useEffect(() => () => clearInterval(genTimer.current), []);

  // ---- evidence add (with brief processing on the card) ----
  const addEvidence = (e: Evidence) => {
    const pending = { ...e, processing: true };
    setS1((s) => ({ ...s, evidences: [...s.evidences, pending] }));
    setTimeout(() => setS1((s) => ({ ...s, evidences: s.evidences.map((x) => (x.id === e.id ? { ...x, processing: false } : x)) })), 1400);
  };
  const removeEvidence = (id: string) => setS1((s) => ({ ...s, evidences: s.evidences.filter((x) => x.id !== id) }));

  // ---- generate draft: run pipeline, then go to step 2 ----
  const generateDraft = () => {
    setGenerating(true); setGenStep(0);
    let n = 0;
    genTimer.current = setInterval(() => {
      n += 1;
      if (n >= GEN_STEPS.length) { clearInterval(genTimer.current); setGenStep(GEN_STEPS.length); setTimeout(() => { setGenerating(false); setGenStep(0); setStep(2); }, 450); }
      else setGenStep(n);
    }, 560);
  };

  if (generating) return <GeneratingOverlay current={genStep} />;

  // footer config per step
  const footer =
    step === 1
      ? { primaryLabel: "Crear borrador", hint: s1.folder ? "Cargá evidencias y creá el borrador" : "Seleccioná una ubicación para continuar", onPrimary: generateDraft, disabled: !s1.folder, hideBack: true }
      : step === 2
      ? { primaryLabel: "Continuar", hint: "Cuando el borrador esté listo, continuá", onPrimary: () => setStep(3), onBack: () => setStep(1) }
      : s3.sent
      ? { primaryLabel: "Volver a documentos", hint: "El documento quedó pendiente de aprobación", onPrimary: () => { setStep(1); setS3((s) => ({ ...s, sent: false })); }, hideBack: true }
      : { primaryLabel: "Enviar a aprobación", hint: s3.approvers.some((a) => a.sel) ? "Se enviará a los aprobadores elegidos" : "Seleccioná al menos un aprobador", onPrimary: () => setS3((s) => ({ ...s, sent: true })), onBack: () => setStep(2), disabled: !s3.approvers.some((a) => a.sel) };

  return (
    <>
      <WizardContainer step={step} footer={footer}>
        {step === 1 && <Step1NuevoDocumento s={s1} set={(p) => setS1((s) => ({ ...s, ...p }))} onAddEvidence={() => setModalOpen(true)} onRemoveEvidence={removeEvidence} />}
        {step === 2 && <Step2Revision evidences={s1.evidences} />}
        {step === 3 && <Step3EnviarAprobacion s={s3} set={(p) => setS3((s) => ({ ...s, ...p }))} />}
      </WizardContainer>

      {modalOpen && <AddEvidenceModal onClose={() => setModalOpen(false)} onAdd={addEvidence} />}
    </>
  );
}
