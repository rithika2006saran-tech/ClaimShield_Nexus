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
    <Page title={p ? `${p.provider_id} (${p.display_label}) - ${p.name}` : "Provider Profile"} subtitle={p ? `${p.specialty} • ${p.region} • ${p.city}` : undefined}
      actions={<div className="relative"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find provider (ID / name)" className="h-8 w-52 rounded-md border border-input bg-card px-2 text-[12px]" />
        {list.data && q.length > 1 && <div className="absolute right-0 z-10 mt-1 w-72 rounded-md border border-border bg-card shadow-lg">{list.data.map((r) => <button key={r.provider_id} onClick={() => { setQ(""); nav(`/provider/${r.provider_id}`); }} className="block w-full px-2 py-1.5 text-left text-[12px] hover:bg-accent">{r.provider_id} - {r.name} <span className="text-muted-foreground">({r.specialty})</span></button>)}</div>}</div>}>
      {loading && <Loading label="Loading Provider Profile" />}
      {error && <ErrorBox error={error} />}
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="FWA Risk" value={f2(d.scores.fwa_risk_score)} sub="XGBoost score" className="border-primary/20 bg-primary/5" />
            <Stat label="Anomaly" value={f2(d.scores.anomaly_score)} sub="Isolation Forest" />
            <Stat label="Peer Group" value={<span className="text-[13px] font-mono text-muted-foreground">{d.peer_group}</span>} sub={`${d.peer_size} peers`} />
            <Stat label="Network Degree" value={d.network?.degree ?? "-"} sub={`btw ${d.network?.betweenness?.toFixed(3) ?? "-"}`} />
            <Stat label={`30/60/90 ${d.forecast?.label ?? ""}`} value={<span className="text-[16px]">{d.forecast ? [d.forecast.f30, d.forecast.f60, d.forecast.f90].map((v: number) => v.toFixed(2)).join(" / ") : "-"}</span>} />
          </div>
          {d.cases.length === 0 && <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 text-[12px] text-green-300 flex items-center gap-2"><span>No active investigations.</span> <span className="text-green-300/80">Peer deviation alone does not establish misconduct.</span></div>}
          
          <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
            <Card className="flex flex-col border-none shadow-sm bg-card/50">
              <CardHeader className="py-3 flex-none"><CardTitle>Peer Benchmarking</CardTitle><div className="text-[11px] text-muted-foreground mt-0.5">Specialty • Region • Facility Type</div></CardHeader>
              <CardContent className="p-0 flex-1 overflow-x-auto">
                <table className="w-full text-[12px] whitespace-nowrap">
                  <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <tr><th className="px-4 py-2 font-medium">Metric</th><th className="px-4 py-2 font-medium">Provider</th><th className="px-4 py-2 font-medium">Peer Median</th><th className="px-4 py-2 font-medium">Ratio</th><th className="px-4 py-2 font-medium">Robust Z</th><th className="px-4 py-2 font-medium w-48">Percentile</th></tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {d.peer_benchmarks.map((m: any) => (
                      <tr key={m.metric} className="hover:bg-accent/40 transition-colors">
                        <td className="px-4 py-2 font-medium text-foreground">{m.label}</td>
                        <td className="px-4 py-2 tabular-nums font-medium text-primary">{fmt(m.value)}</td>
                        <td className="px-4 py-2 tabular-nums text-muted-foreground">{fmt(m.peer_median)}</td>
                        <td className="px-4 py-2 tabular-nums font-medium text-foreground">{m.ratio != null ? `${m.ratio.toFixed(1)}x` : "-"}</td>
                        <td className={`px-4 py-2 tabular-nums font-bold ${m.z >= 3 ? "text-[#f59e0b]" : "text-muted-foreground"}`}>{m.z != null ? (m.z > 99 ? ">99" : m.z.toFixed(1)) : "-"}</td>
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-3">
                            <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden"><div className="h-full rounded-full bg-primary" style={{ width: pct(m.percentile) }} /></div>
                            <span className="w-10 text-right tabular-nums text-muted-foreground text-[11px]">{pct(m.percentile)}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
            
            <div className="space-y-4 flex flex-col">
              <Card>
                <CardHeader className="py-3 flex flex-row items-center justify-between"><CardTitle>Cases</CardTitle><Link to={`/network/${p.provider_id}`}><Button size="sm" variant="outline" className="h-6 text-[10px] px-2 uppercase tracking-wider">Network &rarr;</Button></Link></CardHeader>
                <CardContent className="space-y-2 text-[12px] pb-4">
                  {d.cases.length ? d.cases.map((c: any) => <div key={c.case_id} className="flex items-center justify-between"><Link className="font-mono text-primary hover:underline font-medium" to={`/case/${c.case_id}`}>{c.case_id}</Link><div className="flex items-center gap-2"><BandBadge band={c.review_priority} /> <Badge variant="outline" className="text-[9px] bg-transparent">{c.review_status}</Badge></div></div>) : <span className="text-muted-foreground">None</span>}
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader className="py-3"><CardTitle>Rule Findings</CardTitle></CardHeader>
                <CardContent className="space-y-1.5 text-[12px] pb-4">
                  {d.rule_findings.length ? d.rule_findings.map((r: any, i: number) => <div key={i} className="flex justify-between items-center"><span className="text-foreground">{r.rule_id}</span><div className="flex items-center gap-2"><Badge variant="outline" className="text-[9px]">{r.severity}</Badge> <b className="tabular-nums">{r.n}</b></div></div>) : <span className="text-muted-foreground">No rule findings attached to a case.</span>}
                </CardContent>
              </Card>
              
              <Card>
                <CardHeader className="py-3"><CardTitle>Historical</CardTitle></CardHeader>
                <CardContent className="space-y-1.5 text-[12px] pb-4">
                  {d.historical_investigations.length ? d.historical_investigations.map((i: any) => <div key={i.investigation_id} className="flex items-center justify-between"><div className="flex items-center gap-2"><b className="font-mono text-muted-foreground">{i.investigation_id}</b> <Badge variant="outline" className="text-[9px]">{i.outcome}</Badge></div> <span className="text-muted-foreground text-[10px]">{i.opened_date}</span></div>) : <span className="text-muted-foreground">None</span>}
                </CardContent>
              </Card>
            </div>
          </div>
          
          <div className="grid gap-4 xl:grid-cols-2 items-start">
            <Card>
              <CardHeader className="py-3"><CardTitle>Temporal Intelligence</CardTitle></CardHeader>
              <CardContent className="p-2 pt-0">{d.timeline ? <TimelinePanel timeline={d.timeline} /> : <div className="p-2 text-[12px] text-muted-foreground">No timeline data available.</div>}</CardContent>
            </Card>
            <Card className="h-fit">
              <CardHeader className="py-3"><CardTitle>Model Attribution (SHAP)</CardTitle></CardHeader>
              <CardContent className="pb-4 pr-6">
                {d.shap ? <ResponsiveContainer width="100%" height={260}>
                  <BarChart layout="vertical" data={[...d.shap.positive.slice(0, 6), ...d.shap.negative.slice(0, 4)]} margin={{ left: 40 }}>
                    <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="label" width={170} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                    <Tooltip cursor={{ fill: "hsl(var(--muted))" }} contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: 11 }} />
                    <ReferenceLine x={0} stroke="hsl(var(--border))" />
                    <RBar dataKey="shap_value" radius={2}>{[...d.shap.positive.slice(0, 6), ...d.shap.negative.slice(0, 4)].map((s: any, i: number) => <Cell key={i} fill={s.shap_value >= 0 ? "#f04452" : "#22c55e"} />)}</RBar>
                  </BarChart>
                </ResponsiveContainer> : <span className="text-[12px] text-muted-foreground">No SHAP output available.</span>}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}

const fmt = (v: any) => (v == null ? "-" : Math.abs(v) >= 100 ? Number(v).toFixed(0) : Number(v).toFixed(2));
