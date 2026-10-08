import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar as RBar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, BandBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import TimelinePanel from "@/components/TimelinePanel";
import { ErrorBox, Loading, Page, Stat } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { f2, pct } from "@/lib/utils";

export default function ProviderProfile() {
  const { providerId = "PRV-102" } = useParams();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const { data: d, error, loading } = useApi<any>(`/providers/${providerId}`, [providerId]);
  const list = useApi<any[]>(q.length > 1 ? `/providers?q=${encodeURIComponent(q)}&limit=6` : null, [q]);
  const p = d?.provider;
  return (
    <Page title={p ? `${p.provider_id} (${p.display_label}) - ${p.name}` : "Provider Profile"} subtitle={p ? `${p.specialty} - ${p.region} - ${p.city}` : undefined}
      actions={<div className="relative"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find provider (ID / name)" className="h-8 w-52 rounded-md border border-input bg-background px-2 text-xs" />
        {list.data && q.length > 1 && <div className="absolute right-0 z-10 mt-1 w-72 rounded-md border border-border bg-card shadow-lg">{list.data.map((r) => <button key={r.provider_id} onClick={() => { setQ(""); nav(`/provider/${r.provider_id}`); }} className="block w-full px-2 py-1.5 text-left text-xs hover:bg-accent">{r.provider_id} - {r.name} <span className="text-muted-foreground">({r.specialty})</span></button>)}</div>}</div>}>
      {loading && <Loading />}{error && <ErrorBox error={error} />}
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="FWA risk score" value={f2(d.scores.fwa_risk_score)} sub="XGBoost (not a probability of fraud)" /><Stat label="Anomaly score" value={f2(d.scores.anomaly_score)} sub="Isolation Forest percentile" />
            <Stat label="Peer group" value={<span className="text-sm">{d.peer_group}</span>} sub={`${d.peer_size} peers`} /><Stat label="Network degree" value={d.network?.degree ?? "-"} sub={`betweenness ${d.network?.betweenness?.toFixed(3) ?? "-"}`} />
            <Stat label={`30/60/90 ${d.forecast?.label ?? ""}`} value={<span className="text-base">{d.forecast ? [d.forecast.f30, d.forecast.f60, d.forecast.f90].map((v: number) => v.toFixed(2)).join(" / ") : "-"}</span>} />
          </div>
          {d.cases.length === 0 && <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 text-xs text-green-300">This provider is not part of any investigation case. Peer deviation alone does not establish misconduct - for example, oncology infusion cycles and physical-therapy episodes legitimately produce high utilization.</div>}
          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2 border-none shadow-sm bg-card/50"><CardHeader><CardTitle>Peer benchmarking</CardTitle><div className="text-sm text-muted-foreground mt-1">Specialty | Region | Facility Type</div></CardHeader><CardContent className="p-0">
              <table className="w-full text-sm"><thead className="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="p-3">Metric</th><th className="p-3">Provider</th><th className="p-3">Peer median</th><th className="p-3">Ratio</th><th className="p-3">Robust z</th><th className="p-3 w-48">Percentile</th></tr></thead><tbody className="divide-y divide-border">
                {d.peer_benchmarks.map((m: any) => <tr key={m.metric} className="hover:bg-accent/50 transition-colors"><td className="p-3 font-medium">{m.label}</td><td className="p-3 tabular-nums font-medium text-sky-400">{fmt(m.value)}</td><td className="p-3 tabular-nums text-muted-foreground">{fmt(m.peer_median)}</td><td className="p-3 tabular-nums font-medium">{m.ratio != null ? `${m.ratio.toFixed(1)}x` : "-"}</td>
                  <td className={`p-3 tabular-nums font-bold ${m.z >= 3 ? "text-orange-400" : ""}`}>{m.z != null ? (m.z > 99 ? ">99" : m.z.toFixed(1)) : "-"}</td><td className="p-3"><div className="flex items-center gap-3"><div className="h-2 flex-1 rounded-full bg-muted overflow-hidden"><div className="h-full rounded-full bg-sky-500" style={{ width: pct(m.percentile) }} /></div><span className="w-10 text-right tabular-nums text-muted-foreground">{pct(m.percentile)}</span></div></td></tr>)}
              </tbody></table>
              </CardContent></Card>
            <div className="space-y-4">
              <Card><CardHeader><CardTitle>Cases</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">{d.cases.length ? d.cases.map((c: any) => <div key={c.case_id} className="flex items-center justify-between"><Link className="font-mono text-sky-400 hover:underline" to={`/case/${c.case_id}`}>{c.case_id}</Link><span><BandBadge band={c.review_priority} /> <Badge>{c.review_status}</Badge></span></div>) : <span className="text-muted-foreground">None</span>}
                <Link to={`/network/${p.provider_id}`}><Button size="sm" variant="outline" className="mt-2 w-full">Open in Network Explorer</Button></Link></CardContent></Card>
              <Card><CardHeader><CardTitle>Rule findings</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">{d.rule_findings.length ? d.rule_findings.map((r: any, i: number) => <div key={i} className="flex justify-between"><span>{r.rule_id}</span><span><Badge>{r.severity}</Badge> <b className="tabular-nums">{r.n}</b></span></div>) : <span className="text-muted-foreground">No rule findings attached to a case.</span>}</CardContent></Card>
              <Card><CardHeader><CardTitle>Historical investigations</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">{d.historical_investigations.length ? d.historical_investigations.map((i: any) => <div key={i.investigation_id}><b className="font-mono">{i.investigation_id}</b> {i.outcome} <span className="text-muted-foreground">({i.opened_date})</span></div>) : <span className="text-muted-foreground">None</span>}</CardContent></Card>
            </div>
          </div>
          <div className="grid gap-4 xl:grid-cols-2 items-start">
            <Card><CardHeader><CardTitle>Behavioural timeline</CardTitle></CardHeader><CardContent>{d.timeline ? <TimelinePanel timeline={d.timeline} /> : "-"}</CardContent></Card>
            <Card className="h-fit"><CardHeader><CardTitle>Model attribution (SHAP, log-odds)</CardTitle></CardHeader><CardContent>
              {d.shap ? <ResponsiveContainer width="100%" height={260}><BarChart layout="vertical" data={[...d.shap.positive.slice(0, 6), ...d.shap.negative.slice(0, 4)]} margin={{ left: 40 }}>
                <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} /><YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 10, fill: "#94a3b8" }} /><Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 11 }} /><ReferenceLine x={0} stroke="#475569" />
                <RBar dataKey="shap_value" radius={2}>{[...d.shap.positive.slice(0, 6), ...d.shap.negative.slice(0, 4)].map((s: any, i: number) => <Cell key={i} fill={s.shap_value >= 0 ? "#ef4444" : "#22c55e"} />)}</RBar></BarChart></ResponsiveContainer> : <span className="text-xs text-muted-foreground">No SHAP output.</span>}
              </CardContent></Card>
          </div>
        </div>
      )}
    </Page>
  );
}
const fmt = (v: any) => (v == null ? "-" : Math.abs(v) >= 100 ? Number(v).toFixed(0) : Number(v).toFixed(2));
