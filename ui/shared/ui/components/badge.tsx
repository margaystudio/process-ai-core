import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../cn";

/** Badge de estado Margay */
const badgeVariants = cva(
  "inline-flex items-center gap-1.5 font-semibold leading-none rounded-full px-2.5 py-1.5 text-xs " +
    "before:content-[''] before:size-1.5 before:rounded-full before:bg-current before:opacity-90",
  {
    variants: {
      variant: {
        neutral: "bg-ink-100 text-ink-600",
        success: "bg-success-bg text-success-fg",
        warning: "bg-warning-bg text-warning",
        danger: "bg-danger-bg text-danger",
        info: "bg-info-bg text-info",
      },
      dot: { false: "before:hidden", true: "" },
    },
    defaultVariants: { variant: "neutral", dot: true },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, dot, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, dot }), className)} {...props} />;
}

export { badgeVariants };
