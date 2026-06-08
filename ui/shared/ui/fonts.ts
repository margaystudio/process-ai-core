import { Plus_Jakarta_Sans } from "next/font/google";

/**
 * Tipografía oficial Margay. Importá `jakarta` en tu app/layout.tsx y añadí
 * `jakarta.variable` a la clase del <html>. La variable CSS --font-jakarta ya
 * está referenciada en el tailwind-preset.
 */
export const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jakarta",
  display: "swap",
});
