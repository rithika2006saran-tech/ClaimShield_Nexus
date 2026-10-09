import * as React from "react";
import { cn, BAND_COLOR } from "@/lib/utils";

import { cva, type VariantProps } from "class-variance-authority";

const badgeVariants = cva(
  "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-red-600 text-white hover:bg-red-600/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export const Badge = ({ className, variant, ...p }: BadgeProps) => (
  <span className={cn(badgeVariants({ variant }), className)} {...p} />
);
export const BandBadge = ({ band, className }: { band?: string | null; className?: string }) => (
  <Badge className={cn(band ? BAND_COLOR[band] : "", className)}>{band ?? "-"}</Badge>
);
