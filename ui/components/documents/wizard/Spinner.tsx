"use client";

/** Spinner SVG animado — usado en pipelines de procesamiento */
export function Spinner({
  size = 15,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.4}
      className={"animate-spin " + className}
      style={{ animationDuration: ".8s" }}
      aria-hidden="true"
    >
      <path d="M21 12a9 9 0 1 1-6.2-8.5" />
    </svg>
  );
}
