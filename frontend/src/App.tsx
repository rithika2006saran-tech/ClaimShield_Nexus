import { useState, useEffect } from "react";
import { NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { Activity, Brain, ListOrdered, Network, ShieldCheck, Stethoscope, PanelLeftClose, PanelLeftOpen, ChevronDown, Search, Settings, LogOut, User } from "lucide-react";
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
  { 
    id: "workspace", label: "Workspace", icon: ShieldCheck,
    sub: [
      { to: "/case/CASE-1024/overview", label: "Overview & Analytics" },
      { to: "/case/CASE-1024/network", label: "Network & Evidence" }
    ]
  },
  { to: "/network", label: "Network Explorer", icon: Network },
  { to: "/provider/PRV-102", label: "Provider Profile", icon: Stethoscope },
  { to: "/memory", label: "Nexus Memory", icon: Brain },
  { to: "/config", label: "Configuration", icon: Settings },
];

export default function App() {
  const health = useApi<any>("/health");
  const [collapsed, setCollapsed] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(true);
  const location = useLocation();

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
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className={cn("flex shrink-0 flex-col border-r border-border bg-[#101620] transition-all duration-300", collapsed ? "w-[68px]" : "w-[220px]")}>
        <div className={cn("flex items-center px-4 py-3 border-b border-border h-12", collapsed ? "justify-center px-0" : "justify-between")}>
          {!collapsed && (
            <div className="flex items-center gap-2 text-[13px] font-bold tracking-tight text-foreground truncate">
              <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
              <span>ClaimShield <span className="text-primary">Nexus</span></span>
            </div>
          )}
          {collapsed && <ShieldCheck className="h-5 w-5 text-primary shrink-0" />}
          <button onClick={() => setCollapsed(!collapsed)} className="text-muted-foreground hover:text-foreground shrink-0">
            {collapsed ? null : <PanelLeftClose className="h-4 w-4" />}
          </button>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {NAV.map((n: any) => (
            n.sub ? (
              <div key={n.id} className="space-y-1">
                <button onClick={() => setWorkspaceOpen(!workspaceOpen)} className={cn("flex w-full items-center gap-3 rounded-md px-3 py-2 text-[13px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors", (location.pathname.startsWith("/case/") && !collapsed) ? "bg-accent/50 text-foreground font-medium" : "", collapsed && "justify-center px-0")} title={collapsed ? n.label : undefined}>
                  <n.icon className="h-4 w-4 shrink-0" />
                  {!collapsed && <span className="flex-1 text-left truncate">{n.label}</span>}
                  {!collapsed && <ChevronDown className={cn("h-3 w-3 shrink-0 transition-transform", workspaceOpen ? "rotate-180" : "")} />}
                </button>
                {!collapsed && workspaceOpen && (
                  <div className="pl-9 pr-2 space-y-1 mt-1">
                    {n.sub.map((s: any) => (
                      <NavLink key={s.to} to={s.to} className={({ isActive }) => cn("flex items-center gap-2 rounded-md px-3 py-1.5 text-[12px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors", isActive && "bg-accent text-foreground font-medium")}>
                        {s.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <NavLink key={n.to} to={n.to} end={n.end} title={collapsed ? n.label : undefined} className={({ isActive }) => cn("flex items-center gap-3 rounded-md px-3 py-2 text-[13px] text-muted-foreground hover:bg-accent hover:text-foreground transition-colors", isActive && "bg-accent text-foreground font-medium", collapsed && "justify-center px-0")}>
                <n.icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span className="truncate">{n.label}</span>}
              </NavLink>
            )
          ))}
        </nav>
        <div className="p-2 border-t border-border">
          <button onClick={() => setCollapsed(!collapsed)} className={cn("flex w-full items-center justify-center gap-2 rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground", !collapsed && "hidden")}>
             <PanelLeftOpen className="h-4 w-4" />
          </button>
          {!collapsed && (
            <div className="px-3 py-2 text-[11px] uppercase tracking-wider text-muted-foreground/70 font-medium">
              FWA Intelligence
            </div>
          )}
        </div>
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
          <Route path="/case/:caseId" element={<Navigate to="/case/CASE-1024/overview" replace />} />
          <Route path="/case/:caseId/:tabId" element={<Workspace />} />
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
