import { useState, useEffect } from "react";
import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { Activity, Brain, ListOrdered, Network, ShieldCheck, Stethoscope, Search, Settings, LogOut, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { useApi } from "@/lib/useApi";
import { supabase } from "@/lib/supabase";
import CommandCenter from "@/pages/CommandCenter";
import Queue from "@/pages/Queue";
import Workspace from "@/pages/Workspace";
import NetworkExplorer from "@/pages/NetworkExplorer";
import ProviderProfile from "@/pages/ProviderProfile";
import Memory from "@/pages/Memory";
import Config from "@/pages/Config";
import Login from "@/pages/Login";
import { GlobalSearch } from "@/components/GlobalSearch";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LiveEvents } from "@/components/LiveEvents";

const NAV = [
  { to: "/", label: "Command Center", icon: Activity, end: true },
  { to: "/queue", label: "SIU Queue", icon: ListOrdered },
  { to: "/case/CASE-1024", label: "Investigation Workspace", icon: ShieldCheck },
  { to: "/network", label: "Network Explorer", icon: Network },
  { to: "/provider/PRV-102", label: "Provider Profile", icon: Stethoscope },
  { to: "/memory", label: "Nexus Memory", icon: Brain },
  { to: "/config", label: "Configuration", icon: Settings },
];

export default function App() {
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  if (loading) return null;

  if (!session) {
    return <Login onLogin={() => {}} />;
  }

  const email = session.user.email;

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
      </aside>
      <main className="min-w-0 flex-1 flex flex-col h-screen">
        <header className="flex h-14 items-center justify-between border-b border-border bg-card/50 px-4 shrink-0">
          <GlobalSearch />
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-accent/50 px-2 py-1 rounded-md">
              <User className="h-3 w-3" /> {email}
            </div>
            <button onClick={() => supabase.auth.signOut()} className="text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors">
              <LogOut className="h-4 w-4" /> Sign Out
            </button>
            <ThemeToggle />
          </div>
        </header>
        <div className="flex-1 overflow-y-auto">
          <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/queue" element={<Queue />} />
          <Route path="/case/:caseId" element={<Workspace />} />
          <Route path="/network" element={<NetworkExplorer />} />
          <Route path="/network/:center" element={<NetworkExplorer />} />
          <Route path="/provider/:providerId" element={<ProviderProfile />} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/config" element={<Config />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
        </div>
      </main>
      <LiveEvents />
    </div>
  );
}
