// Root app: wires the shell + view switching to every screen.
// Drop into a Vite/CRA/Next "use client" entry. Requires the tailwind.config.js tokens.
import React, { useState } from "react";
import { AppShell, ViewKey } from "./components/AppShell";
import BibliotecaScreen from "./screens/BibliotecaScreen";
import PorAprobarScreen from "./screens/PorAprobarScreen";
import NuevoDocumentoScreen from "./screens/NuevoDocumentoScreen";
import ImportarScreen from "./screens/ImportarScreen";
import PanelControlScreen from "./screens/PanelControlScreen";
import CarpetasScreen from "./screens/CarpetasScreen";
import TipoDocumentosScreen from "./screens/TipoDocumentosScreen";
import UsuariosRolesScreen from "./screens/UsuariosRolesScreen";
import TytoScreen from "./screens/TytoScreen";

export default function App() {
  const [view, setView] = useState<ViewKey>("biblioteca");

  return (
    <AppShell view={view} onNavigate={setView}>
      {view === "biblioteca" && <BibliotecaScreen />}
      {view === "porAprobar" && <PorAprobarScreen />}
      {view === "nuevo" && <NuevoDocumentoScreen />}
      {view === "importar" && <ImportarScreen />}
      {view === "panel" && <PanelControlScreen />}
      {view === "carpetas" && <CarpetasScreen />}
      {view === "tipos" && <TipoDocumentosScreen />}
      {view === "usuarios" && <UsuariosRolesScreen />}
      {view === "tyto" && <TytoScreen embedded />}
    </AppShell>
  );
}
