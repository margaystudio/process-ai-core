# Process AI — React + Tailwind export

Readable React (TypeScript) + Tailwind CSS source for the Process AI platform, **one file per screen**. Recreated from the HTML prototype; data is demo data — replace with your API.

## Structure

```
export_react/
├── tailwind.config.js          # design tokens as Tailwind theme (colors, shadows, fonts)
├── src/
│   ├── App.tsx                 # root: shell + view switching
│   ├── lib/
│   │   └── data.tsx            # types, demo data (DOCS, FOLDERS), Icon helper, tone helpers
│   ├── components/
│   │   ├── AppShell.tsx        # Sidebar (dark) + Topbar + content area + ViewKey type
│   │   └── ui.tsx              # StatusBadge, TintPill, Chip, buttons, Card, SectionLabel
│   └── screens/
│       ├── BibliotecaScreen.tsx        # landing: folder tree + doc list, filters, density, row menu, empty state
│       ├── PorAprobarScreen.tsx        # approver inbox + review pane
│       ├── NuevoDocumentoScreen.tsx    # AI authoring: evidence → generating → draft review
│       ├── ImportarScreen.tsx          # 5-step batch import wizard (config → incorporate → process → review → result)
│       ├── PanelControlScreen.tsx      # global governance control center (KPIs + alerts + lists)
│       ├── CarpetasScreen.tsx          # folder governance: tree + tabs (Gobierno/Tyto/Permisos/IA) + inheritance + create modal
│       ├── TipoDocumentosScreen.tsx    # configurable document types + behaviours
│       ├── UsuariosRolesScreen.tsx     # role cards + users table
│       └── TytoScreen.tsx              # assistant: home + conversation + context panel + special states
```

## Setup

These files assume a React + TypeScript + Tailwind project (Vite recommended). To run:

1. `npm create vite@latest process-ai -- --template react-ts`
2. Add Tailwind: `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p`
3. Replace the generated `tailwind.config.js` with the one here.
4. Copy `src/` over the generated one. Render `<App />` from `src/main.tsx`.
5. Add the fonts to `index.html`:
   ```html
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
   <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
   ```
6. Tailwind base CSS (`@tailwind base; @tailwind components; @tailwind utilities;`) in your entry CSS.

## Conventions

- **Icons:** the `Icon` helper in `lib/data.tsx` draws inline Feather/Lucide-style paths. Swap it for `lucide-react` if you prefer (path data is provided in `ICONS`).
- **Badge tint convention:** state/inheritance pills use `color = accent`, `background = accent + "14"`, `border = accent + "33"`. See `TintPill`.
- **Tokens:** all colors/shadows live in `tailwind.config.js` under `theme.extend`. Don't hardcode hex in components beyond the few dynamic per-row tints (those mirror the prototype).
- **State:** each screen owns its local state with `useState`. For a real app, lift shared data (current role, selected folder) into a store/context and replace demo arrays with queries.

## What is demo / needs wiring

- All documents, folders, users, activity, KPIs and Tyto answers are **hardcoded demo data**.
- **Tyto** matches questions to fixed scenarios by keyword — replace with your real retrieval + citation engine over the derived representation.
- The **Nuevo documento** flow generates the hardcoded "Cierre de caja" draft.
- Drag & drop reparent (Carpetas), file upload (Importar), and rich-text editing are stubbed for fidelity — wire to your backend.

## Screenshots

See `export_react/screenshots/` for a render of each screen and its key states.
