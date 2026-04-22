import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "bg-primary/10 text-primary",
        secondary:
          "bg-secondary/10 text-secondary",
        destructive:
          "bg-error/10 text-error",
        success:
          "bg-primary-container/10 text-primary-container",
        warning:
          "bg-tertiary-container/10 text-tertiary",
        outline: "border border-outline-variant/20 text-on-surface-variant",
        verified: "bg-primary-container/10 text-primary-container",
        active: "bg-tertiary-container/10 text-tertiary-container",
        ready: "bg-surface-variant text-on-surface-variant/60",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
