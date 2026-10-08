import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { Activity, Brain, ListOrdered, Network, ShieldCheck, Stethoscope, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/useApi";
import CommandCenter from "@/pages/CommandCenter";
import Queue from "@/pages/Queue";
import Workspace from "@/pages/Workspace";
import NetworkExplorer from "@/pages/NetworkExplorer";
import ProviderProfile from "@/pages/ProviderProfile";
import Memory from "@/pages/Memory";

const NAV = [
  { to: "/", label: "Command Center", icon: Activity, end: true },
  { to: "/queue", label: "SIU Queue", icon: ListOrdered },
  { to: "/case/CASE-1024", label: "Investigation Workspace", icon: ShieldCheck },
  { to: "/network", label: "Network Explorer", icon: Network },
  { to: "/provider/PRV-102", label: "Provider Profile", icon: Stethoscope },
  { to: "/memory", label: "Nexus Memory", icon: Brain },
];

export default function App() {
  const health = useApi<any>("/health");
  const h = health.data;
  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card">
        <div className="px-4 py-4 border-b border-border">
          <div className="flex items-center gap-2 text-sm font-bold tracking-tight"><ShieldCheck className="h-5 w-5 text-primary" /> ClaimShield <span className="text-primary">Nexus</span></div>
          <div className="mt-1 text-[10px] uppercase tracking-widest text-muted-foreground">FWA Investigation Intelligence</div>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => cn("flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground", isActive && "bg-accent text-foreground")}>
              <n.icon className="h-4 w-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-1 border-t border-border p-3 text-[10px] leading-4 text-muted-foreground">
          <div className="flex items-center gap-1.5"><span className={cn("h-1.5 w-1.5 rounded-full", h?.status === "ok" ? "bg-green-500" : "bg-red-500")} /> API {h?.status ?? (health.error ? "down" : "...")}</div>
          <div>Second Brain: {h?.second_brain?.using_fallback ? "local fallback" : h?.second_brain?.backend ?? "-"}</div>
          <div>Copilot: {h ? (h.llm_provider === "none" ? "deterministic" : h.llm_provider) : "-"}</div>
          <div className="pt-1 text-amber-400/80">Synthetic data only. Leads for human review - not findings of misconduct.</div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/case/:caseId" element={<Workspace />} />
          <Route path="/network" element={<NetworkExplorer />} />
          <Route path="/network/:center" element={<NetworkExplorer />} />
          <Route path="/provider/:providerId" element={<ProviderProfile />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
