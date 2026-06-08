import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../cn";

/**
 * Botón Margay. Primaria = carbón. Usá variant="create" (verde) para "crear/nuevo".
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-semibold whitespace-nowrap rounded-md " +
    "transition-colors disabled:cursor-not-allowed disabled:bg-ink-150 disabled:text-ink-400 " +
    "[&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-action text-action-on hover:bg-action-hover active:bg-action-press",
        create: "bg-create text-white hover:bg-create-hover active:bg-create-press",
        secondary:
          "bg-white text-ink-800 border border-ink-300 hover:bg-ink-100 active:bg-ink-150 disabled:bg-ink-50 disabled:border-ink-200",
        ghost: "text-ink-700 hover:bg-ink-100 active:bg-ink-150",
        danger:
          "bg-white text-danger border border-danger-bd hover:bg-danger-bg active:bg-danger-press",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-[38px] px-4 text-sm",
        lg: "h-11 px-[22px] text-body",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = "Button";

export { buttonVariants };
