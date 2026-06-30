/** @type {import('tailwindcss').Config} */
// Process AI — design tokens as Tailwind theme.
// Recreated from the HTML prototype. Colors share croma/luminosity; only hue varies.
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      colors: {
        ink: {
          900: "#232627", // títulos
          800: "#37393A", // texto fuerte / sidebar
          700: "#4C4F51", // cuerpo
          500: "#6A6E70", // muted
          400: "#8A8F91", // muted claro
          300: "#AEB3B5", // placeholder
          200: "#C8CDCF", // placeholder muy claro
        },
        line: {
          DEFAULT: "#E5E8EA", // borde estándar
          soft: "#EDEFF1",    // borde sutil
          softer: "#F4F5F6",  // divisores
          input: "#D2D6D8",   // bordes de input
        },
        surface: {
          DEFAULT: "#FFFFFF", // cards
          app: "#F7F8F9",     // área de trabajo
          hover: "#FAFBFB",   // hover / zebra
          track: "#EDEFF1",   // segmented / track
        },
        // Acento primario / IA / Tyto
        indigo: {
          DEFAULT: "#48569C",
          light: "#ADB9DF",
          tint: "rgba(173,185,223,0.16)",
          border: "#D2CFE6",
        },
        // Aprobado / éxito
        green: { DEFAULT: "#1F8A55", bright: "#2F9E62", text: "#1E7A47", bg: "#E7F4ED", border: "#B9E0C9" },
        // Pendiente / advertencia
        amber: { DEFAULT: "#9A6A00", bright: "#C99A2E", bg: "#FBF3DD", border: "#F0DCA0" },
        // Error / rechazo / crítico
        red: { DEFAULT: "#CB4242", deep: "#B0413E", bg: "#FDECEC", border: "#E7B6B2" },
        teal: { DEFAULT: "#2E8B8B" },   // importación / sistemas
        violet: { DEFAULT: "#8B5CC2" }, // personas / roles
      },
      borderRadius: { pill: "999px" },
      boxShadow: {
        card: "0 1px 3px rgba(20,28,33,0.05)",
        raised: "0 4px 16px rgba(20,28,33,0.06)",
        modal: "0 24px 60px rgba(20,28,33,0.28)",
        menu: "0 12px 32px rgba(20,28,33,0.18)",
        drawer: "-12px 0 40px rgba(20,28,33,0.2)",
      },
      keyframes: {
        in: { from: { transform: "translateY(9px)" }, to: { transform: "none" } },
      },
      animation: { in: "in .3s cubic-bezier(.2,.7,.3,1) both" },
    },
  },
  plugins: [],
};
