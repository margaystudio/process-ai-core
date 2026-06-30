import type { Config } from "tailwindcss";

/**
 * Preset Tailwind del Design System Margay.
 * Mapea los tokens de tokens.css a clases semánticas (bg-green, text-ink-600,
 * rounded-md, shadow-sm, text-h2, ...). Los módulos lo consumen así:
 *
 *   import margay from "./ui/shared/ui/tailwind-preset";
 *   const config: Config = { presets: [margay], content: [...] };
 *
 * El `content` lo define cada módulo (no el preset).
 */
const preset: Partial<Config> = {
  theme: {
    extend: {
      colors: {
        green: {
          DEFAULT: "var(--green)",
          50: "var(--green-50)", 100: "var(--green-100)", 200: "var(--green-200)",
          300: "var(--green-300)", 400: "var(--green-400)", 500: "var(--green-500)",
          600: "var(--green-600)", 700: "var(--green-700)",
        },
        ink: {
          50: "var(--ink-50)", 100: "var(--ink-100)", 150: "var(--ink-150)",
          200: "var(--ink-200)", 300: "var(--ink-300)", 400: "var(--ink-400)",
          500: "var(--ink-500)", 600: "var(--ink-600)", 700: "var(--ink-700)",
          800: "var(--ink-800)", 900: "var(--ink-900)",
        },
        action: {
          DEFAULT: "var(--action)", hover: "var(--action-hover)", press: "var(--action-press)",
          on: "var(--on-action)", tint: "var(--action-tint)", ring: "var(--action-ring)",
        },
        create: {
          DEFAULT: "var(--create)", hover: "var(--create-hover)", press: "var(--create-press)",
          ring: "var(--create-ring)",
        },
        accent: {
          DEFAULT: "var(--accent)", ink: "var(--accent-ink)", tint: "var(--accent-tint)",
        },
        success: { DEFAULT: "var(--success)", bg: "var(--success-bg)", bd: "var(--success-bd)", fg: "var(--success-fg)" },
        warning: { DEFAULT: "var(--warning)", bg: "var(--warning-bg)", bd: "var(--warning-bd)" },
        danger:  { DEFAULT: "var(--danger)",  bg: "var(--danger-bg)",  bd: "var(--danger-bd)", press: "var(--danger-press)" },
        info:    { DEFAULT: "var(--info)",    bg: "var(--info-bg)",    bd: "var(--info-bd)" },
        sidebar: {
          bg:      "var(--sidebar-bg)",
          surface: "var(--sidebar-surface)",
          fg:      "var(--sidebar-fg)",
          muted:   "var(--sidebar-muted)",
          hover:   "var(--sidebar-item-hover)",
          border:  "var(--sidebar-border)",
        },
        /* ---- Tokens de borde (del prototipo Process AI) ---- */
        line: {
          DEFAULT: "var(--line)",
          soft:    "var(--line-soft)",
          softer:  "var(--line-softer)",
          input:   "var(--line-input)",
        },
        /* ---- Superficies ---- */
        surface: {
          DEFAULT: "var(--surface)",
          app:     "var(--surface-app)",
          hover:   "var(--surface-hover)",
          track:   "var(--surface-track)",
        },
        /* ---- Indigo / IA / acento process ---- */
        indigo: {
          DEFAULT: "var(--indigo)",
          light:   "var(--indigo-light)",
          tint:    "var(--indigo-tint)",
          border:  "var(--indigo-border)",
        },
        /* ---- Complementarios ---- */
        teal:   { DEFAULT: "var(--teal)" },
        violet: { DEFAULT: "var(--violet)" },
        /* ---- Amber: alias semántico de warning para el prototipo ---- */
        amber: {
          DEFAULT: "var(--warning)",
          bg:      "var(--warning-bg)",
          border:  "var(--warning-bd)",
        },
      },
      borderRadius: {
        sm: "var(--r-sm)", md: "var(--r-md)", lg: "var(--r-lg)", xl: "var(--r-xl)",
        pill: "var(--r-pill)",
      },
      boxShadow: {
        xs: "var(--sh-xs)", sm: "var(--sh-sm)", md: "var(--sh-md)", lg: "var(--sh-lg)",
        card:   "var(--sh-card)",
        raised: "var(--sh-raised)",
        modal:  "var(--sh-modal)",
        menu:   "var(--sh-menu)",
        drawer: "var(--sh-drawer)",
      },
      fontFamily: {
        sans: ["var(--font-jakarta)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        label: ["11.5px", { lineHeight: "1.3", letterSpacing: ".06em" }],
        xs: ["12px", { lineHeight: "1.4" }],
        sm: ["13px", { lineHeight: "1.45" }],
        body: ["14.5px", { lineHeight: "1.5" }],
        h3: ["16px", { lineHeight: "1.4", fontWeight: "700" }],
        h2: ["19px", { lineHeight: "1.35", fontWeight: "700" }],
        h1: ["24px", { lineHeight: "1.25", fontWeight: "700", letterSpacing: "-.01em" }],
        display: ["30px", { lineHeight: "1.2", fontWeight: "700", letterSpacing: "-.01em" }],
      },
      keyframes: {
        in: { from: { transform: "translateY(9px)" }, to: { transform: "none" } },
      },
      animation: {
        in: "in .3s cubic-bezier(.2,.7,.3,1) both",
      },
    },
  },
  plugins: [],
};

export default preset;
