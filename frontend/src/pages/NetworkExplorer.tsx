import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import NetworkGraph from "@/components/NetworkGraph";
import { api } from "@/lib/api";
import { ErrorBox, Loading, Page, Mono } from "@/components/common";
import { f2 } from "@/lib/utils";

export default function NetworkExplorer() {
  const { center: param } = useParams();
  const nav = useNavigate();
  const [center, setCenter] = useState(param ?? "PRV-102");
  const [input, setInput] = useState(param ?? "PRV-102");
  const [hops, setHops] = useState(1);
  const [g, setG] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<any>(null);
  const [pathTo, setPathTo] = useState("");
  const [path, setPath] = useState<any>(null);

  useEffect(() => { setG(null); setErr(null); api(`/network/ego?center=${center}&hops=${hops}`).then(setG).catch((e) => setErr(e.message)); }, [center, hops]);
  useEffect(() => { if (param) { setCenter(param); setInput(param); } }, [param]);

  return (
    <Page title="Network Explorer" subtitle="Selected entity - 1-hop relationships, optional 2-hop expansion. Relationships are investigation leads, not proof of misconduct."
      actions={<form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); nav(`/network/${input.trim().toUpperCase()}`); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="PRV-102 or FAC-012" className="h-8 w-40 rounded-md border border-input bg-card px-2 text-[12px] font-mono" />
        <Button size="sm" type="submit" className="h-8 text-[11px] uppercase tracking-wider">Explore</Button>
        <div className="flex bg-muted rounded p-0.5 ml-2">
          <Button size="sm" type="button" variant={hops === 1 ? "secondary" : "ghost"} className="h-7 text-[11px] px-3" onClick={() => setHops(1)}>1-hop</Button>
          <Button size="sm" type="button" variant={hops === 2 ? "secondary" : "ghost"} className="h-7 text-[11px] px-3" onClick={() => setHops(2)}>2-hop</Button>
        </div>
      </form>}>
      
      {err && <ErrorBox error={err} />}
      {!g && !err && <Loading />}
      
      {g && (
        <div className="grid gap-4 xl:grid-cols-[1fr_320px] items-start h-[calc(100vh-140px)] min-h-[500px]">
          <Card className="flex flex-col h-full min-h-0">
            <CardHeader className="py-3 flex-none"><CardTitle className="flex justify-between items-center"><span>Network Graph</span> <span className="font-mono text-muted-foreground">{center} ({g.nodes.length} nodes, {g.edges.length} edges)</span></CardTitle></CardHeader>
            <CardContent className="p-0 flex-1 relative bg-[#0d121a]">
              <NetworkGraph nodes={g.nodes} edges={g.edges} center={[center]} onSelect={(k, d) => setSel({ k, d })} height="100%" />
            </CardContent>
          </Card>
          
          <div className="space-y-4 flex flex-col h-full overflow-y-auto pr-1 pb-4">
            <Card>
              <CardHeader className="py-3"><CardTitle>Selection Details</CardTitle></CardHeader>
              <CardContent className="text-[12px]">
                {!sel && <div className="text-muted-foreground py-2">Click a node or edge in the graph.</div>}
                {sel?.k === "node" && <div className="space-y-2">
                  <div className="flex items-center gap-2"><div className="font-mono text-sm font-semibold text-foreground">{sel.d.id}</div><div className="text-[10px] uppercase tracking-wider text-muted-foreground border border-border px-1.5 py-0.5 rounded">{sel.d.type} {sel.d.specialty ? `• ${sel.d.specialty}` : ""}</div></div>
                  {sel.d.risk != null && <div className="flex justify-between items-center border-b border-border/50 pb-1"><span>FWA Risk</span><span className="font-semibold text-primary">{f2(sel.d.risk)}</span></div>}
                  {sel.d.degree != null && (
                    <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground">
                      <div>Degree: <strong className="text-foreground">{sel.d.degree}</strong></div>
                      <div>Betweenness: <strong className="text-foreground">{sel.d.betweenness?.toFixed(3)}</strong></div>
                      <div className="col-span-2">Community: <strong className="text-foreground">{sel.d.community}</strong></div>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 pt-2">
                    <Button size="sm" variant="secondary" className="h-7 text-[10px] uppercase tracking-wider" onClick={() => nav(`/network/${sel.d.id}`)}>Recenter Graph</Button>
                    {sel.d.type === "provider" && <Button size="sm" variant="default" className="h-7 text-[10px] uppercase tracking-wider" onClick={() => nav(`/provider/${sel.d.id}`)}>Provider Profile</Button>}
                  </div>
                </div>}
                {sel?.k === "edge" && <div className="space-y-2">
                  <div className="font-semibold uppercase tracking-wider text-[11px] text-muted-foreground">{sel.d.type.replace("_", " ")}</div>
                  <div className="text-foreground"><Mono>{sel.d.source} &rarr; {sel.d.target}</Mono></div>
                  <div className="text-muted-foreground leading-snug">{sel.d.label}</div>
                </div>}
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader className="py-3"><CardTitle>Shortest Path Query</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-[12px]">
                <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); api(`/network/path?a=${center}&b=${pathTo.trim().toUpperCase()}`).then(setPath); }}>
                  <input value={pathTo} onChange={(e) => setPathTo(e.target.value)} placeholder="Target ID (e.g. PRV-087)" className="h-8 w-full rounded-md border border-input bg-card px-2 text-[12px] font-mono" />
                  <Button size="sm" type="submit" className="h-8">Find</Button>
                </form>
                {path && (path.path ? <div className="bg-muted/20 p-2 rounded border border-border space-y-1">
                  <div className="text-primary font-mono text-[11px] leading-relaxed break-words">{path.path.join(" ➔ ")}</div>
                  <div className="text-muted-foreground text-[10px] uppercase tracking-wider pt-1 border-t border-border/50">{path.length} hops • {path.common_neighbors?.length ?? 0} common neighbors</div>
                </div> : <div className="text-muted-foreground italic">No path found between entities.</div>)}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
