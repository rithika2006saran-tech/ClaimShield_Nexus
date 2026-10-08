import { ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export const Page = ({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) => (
  <div className="p-5">
    <div className="mb-4 flex items-end justify-between gap-4">
      <div><h1 className="text-lg font-semibold tracking-tight">{title}</h1>{subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}</div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
    {children}
  </div>
);
export const Loading = ({ label = "Loading" }: { label?: string }) => <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> {label}...</div>;
export const ErrorBox = ({ error }: { error: string }) => <div className="m-4 flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300"><AlertTriangle className="mt-0.5 h-4 w-4" /> {error}</div>;
export const Stat = ({ label, value, sub, className }: { label: string; value: ReactNode; sub?: ReactNode; className?: string }) => (
  <Card className={cn("p-3", className)}><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div><div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>{sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}</Card>
);
export const Bar = ({ value, color = "#38bdf8", className }: { value: number; color?: string; className?: string }) => (
  <div className={cn("h-1.5 w-full overflow-hidden rounded bg-muted", className)}><div className="h-full rounded" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: color }} /></div>
);
export const Mono = ({ children, className }: { children: ReactNode; className?: string }) => <span className={cn("font-mono text-[11px]", className)}>{children}</span>;
