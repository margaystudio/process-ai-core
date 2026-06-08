# Margay UI · Design System

Fuente de verdad del diseño de la plataforma Margay: **tokens + preset de Tailwind +
componentes base**. Identidad: verde `#7CC39C` + carbón `#37393A`, Plus Jakarta Sans,
acentos por módulo vía `data-module`. El spec legible y las reglas están en `DESIGN.md`.
Lo mantiene el agente **margay-frontend**.

## Contenido
```
tokens.css            tokens (CSS variables) + capa base. Se importa en el módulo.
tailwind-preset.ts    mapeo tokens → clases (bg-green, text-ink-600, text-h2, ...).
fonts.ts              Plus Jakarta Sans (next/font).
cn.ts                 helper cn() (clsx + tailwind-merge).
components/           Button, Card/CardBody, Badge, Input/Field (+ index).
index.ts              barrel: re-exporta componentes + cn + jakarta.
DESIGN.md             el spec (reglas do/don't, contrato de tokens).
package.json          listo para promover a paquete @margay/ui.
```

## Cómo lo adopta un módulo (modo interino: copiar)
Mismo precedente que `ui/shared/auth/`.

1. **Copiá** esta carpeta a `<modulo>/ui/shared/ui/`.
2. **Dependencias:** `npm i class-variance-authority clsx tailwind-merge lucide-react`
   (y `next`/`react` ya están en el módulo).
3. **`tailwind.config.ts`** del módulo:
   ```ts
   import type { Config } from "tailwindcss";
   import margay from "./ui/shared/ui/tailwind-preset";

   const config: Config = {
     presets: [margay],
     content: [
       "./app/**/*.{ts,tsx}",
       "./components/**/*.{ts,tsx}",
       "./ui/shared/**/*.{ts,tsx}",
     ],
   };
   export default config;
   ```
4. **`app/globals.css`** del módulo (el import va ANTES de los @tailwind):
   ```css
   @import "../ui/shared/ui/tokens.css";
   @tailwind base;
   @tailwind components;
   @tailwind utilities;
   ```
5. **`app/layout.tsx`**: cargá la fuente.
   ```tsx
   import { jakarta } from "@/ui/shared/ui/fonts";
   import "./globals.css";

   export default function RootLayout({ children }: { children: React.ReactNode }) {
     return (
       <html lang="es" className={jakarta.variable}>
         <body>{children}</body>
       </html>
     );
   }
   ```
6. (Recomendado) Alias en `tsconfig.json` para importar limpio:
   `"paths": { "@ui/*": ["./ui/shared/ui/*"] }`.

## Cómo se usa
```tsx
import { Button, Card, CardBody, Badge } from "@/ui/shared/ui/components";
import { Plus } from "lucide-react";

<div data-module="oms">           {/* acento del módulo */}
  <Card><CardBody className="flex items-center justify-between">
    <div>
      <h3 className="text-h3">Pedidos</h3>
      <p className="text-sm text-ink-600">12 pendientes</p>
    </div>
    <Badge variant="success">Activo</Badge>
  </CardBody></Card>

  <Button variant="create"><Plus /> Nuevo pedido</Button>
</div>
```

## Futuro: paquete `@margay/ui`
Cuando copiar `ui/shared/ui/` en cada módulo empiece a doler, esta misma carpeta se
publica como paquete (`package.json` ya está). Los módulos pasan a:
`npm i @margay/ui` · `import margay from "@margay/ui/tailwind-preset"` ·
`@import "@margay/ui/tokens.css"` · `import { Button } from "@margay/ui"`.
Mismos archivos, una sola copia.
