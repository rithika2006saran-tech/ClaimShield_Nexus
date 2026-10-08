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
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="PRV-102 or FAC-012" className="h-8 w-40 rounded-md border border-input bg-background px-2 text-xs" />
        <Button size="sm" type="submit">Explore</Button>
        <Button size="sm" type="button" variant={hops === 1 ? "default" : "outline"} onClick={() => setHops(1)}>1-hop</Button>
        <Button size="sm" type="button" variant={hops === 2 ? "default" : "outline"} onClick={() => setHops(2)}>2-hop</Button></form>}>
      {err && <ErrorBox error={err} />}{!g && !err && <Loading />}
      {g && (
        <div className="grid gap-4 xl:grid-cols-4">
          <Card className="xl:col-span-3"><CardHeader><CardTitle>{center} - {g.nodes.length} nodes, {g.edges.length} edges</CardTitle></CardHeader>
            <CardContent><NetworkGraph nodes={g.nodes} edges={g.edges} center={[center]} onSelect={(k, d) => setSel({ k, d })} height={560} /></CardContent></Card>
          <div className="space-y-4">
            <Card><CardHeader><CardTitle>Selection</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">
              {!sel && <div className="text-muted-foreground">Click a node or edge.</div>}
              {sel?.k === "node" && <>
                <div className="font-mono text-sm">{sel.d.id}</div><div>{sel.d.type} {sel.d.specialty ? `- ${sel.d.specialty}` : ""}</div>
                {sel.d.risk != null && <div>FWA risk score {f2(sel.d.risk)} <span className="text-muted-foreground">(model output)</span></div>}
                {sel.d.degree != null && <div>degree {sel.d.degree} - betweenness {sel.d.betweenness?.toFixed(3)} - community {sel.d.community}</div>}
                <div className="flex gap-2 pt-1"><Button size="sm" variant="outline" onClick={() => nav(`/network/${sel.d.id}`)}>Recenter</Button>
                  {sel.d.type === "provider" && <Button size="sm" variant="outline" onClick={() => nav(`/provider/${sel.d.id}`)}>Profile</Button>}</div></>}
              {sel?.k === "edge" && <><div className="font-semibold">{sel.d.type.replace("_", " ")}</div><div><Mono>{sel.d.source} &rarr; {sel.d.target}</Mono></div><div>{sel.d.label}</div></>}
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Shortest path</CardTitle></CardHeader><CardContent className="space-y-2 text-xs">
              <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); api(`/network/path?a=${center}&b=${pathTo.trim().toUpperCase()}`).then(setPath); }}>
                <input value={pathTo} onChange={(e) => setPathTo(e.target.value)} placeholder="to e.g. PRV-087" className="h-7 w-full rounded-md border border-input bg-background px-2 text-xs" /><Button size="sm" type="submit">Go</Button></form>
              {path && (path.path ? <div><Mono>{path.path.join(" > ")}</Mono><div className="text-muted-foreground">{path.length} hops; common neighbours: {path.common_neighbors?.length ?? 0}</div></div> : <div className="text-muted-foreground">No path.</div>)}
            </CardContent></Card>
          </div>
        </div>
      )}
    </Page>
  );
}
