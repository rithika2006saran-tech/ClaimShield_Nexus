import * as React from "react";
import { cn, BAND_COLOR } from "@/lib/utils";

export const Badge = ({ className, ...p }: React.HTMLAttributes<HTMLSpanElement>) => (
  <span className={cn("inline-flex items-center rounded border border-border bg-secondary px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-secondary-foreground", className)} {...p} />
);
export const BandBadge = ({ band, className }: { band?: string | null; className?: string }) => (
  <Badge className={cn(band ? BAND_COLOR[band] : "", className)}>{band ?? "-"}</Badge>
);
