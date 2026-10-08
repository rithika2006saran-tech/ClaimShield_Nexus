import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
export const money = (n: number | null | undefined) => (n == null ? "-" : n >= 1e6 ? `$${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `$${(n / 1e3).toFixed(0)}k` : `$${n.toFixed(0)}`);
export const num = (n: number | null | undefined) => (n == null ? "-" : n.toLocaleString());
export const pct = (n: number | null | undefined, d = 0) => (n == null ? "-" : `${(n * 100).toFixed(d)}%`);
export const f2 = (n: number | null | undefined) => (n == null ? "-" : n.toFixed(2));
export const BAND_COLOR: Record<string, string> = { CRITICAL: "bg-red-500/15 text-red-400 border-red-500/40", HIGH: "bg-orange-500/15 text-orange-400 border-orange-500/40", MEDIUM: "bg-yellow-500/15 text-yellow-400 border-yellow-500/40", LOW: "bg-green-500/15 text-green-400 border-green-500/40" };
export const BAND_HEX: Record<string, string> = { CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#22c55e" };
