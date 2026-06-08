import * as React from "react";
import { cn } from "../cn";

/** Input Margay */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-md border border-ink-300 bg-white px-3 text-body text-ink-800",
        "placeholder:text-ink-500 transition-colors",
        "focus:border-action focus:outline-none focus:ring-[3px] focus:ring-action-ring",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

/** Campo con etiqueta */
export function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-sm font-semibold text-ink-700">{label}</span>
      {children}
    </label>
  );
}
