"use client";

/**
 * Icono SVG inline estilo Feather/Lucide.
 * Acepta un path `d` con múltiples comandos M concatenados (el formato de data.ts).
 */
export function WizardIcon({
  d,
  size = 16,
  className = "",
  strokeWidth = 2,
}: {
  d: string;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {d
        .split("M")
        .filter(Boolean)
        .map((seg, i) => (
          <path key={i} d={"M" + seg} />
        ))}
    </svg>
  );
}
