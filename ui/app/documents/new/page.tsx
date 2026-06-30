/**
 * /documents/new — Wizard "Nuevo documento"
 *
 * Monta el wizard visual completo (3 pasos + overlay de generación + modal de evidencia).
 * El cableado al backend se hace en pasos posteriores — ver TODO(wire) en los componentes
 * del wizard (/components/documents/wizard/).
 *
 * La página es un Server Component: el wizard en sí usa "use client" internamente.
 */
import NuevoDocumentoWizard from "@/components/documents/wizard/NuevoDocumentoWizard";

/**
 * El AppShell (ChromeShell) renderiza <main className="min-w-0 flex-1 overflow-auto">.
 * El wizard necesita llenar esa altura completa con flex-col (stepper + contenido + footer).
 * Usamos h-full para que WizardContainer ocupe todo el espacio disponible.
 */
export default function NewDocumentPage() {
  return (
    <div data-module="process" className="h-full">
      <NuevoDocumentoWizard />
    </div>
  );
}
