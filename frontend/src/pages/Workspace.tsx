import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, BandBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import NetworkGraph from "@/components/NetworkGraph";
import ComponentBars from "@/components/ComponentBars";
import TimelinePanel, { SERIES } from "@/components/TimelinePanel";
import Copilot from "@/components/Copilot";
import BriefPanel from "@/components/BriefPanel";
import ForecastPanel from "@/components/ForecastPanel";
import DecisionPanel from "@/components/DecisionPanel";
import EvidenceTable from "@/components/EvidenceTable";
import { Bar, ErrorBox, Loading, Mono, Page } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { f2, money, num } from "@/lib/utils";

export default function Workspace() {
  const { caseId = "CASE-1024", tabId = "overview" } = useParams();
  const { data: d, error, loading, reload } = useApi<any>(`/cases/${caseId}`, [caseId]);
  const [hops, setHops] = useState(1);
  const [sel, setSel] = useState<any>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [series, setSeries] = useState("claims_30d");
  const net = useApi<any>(`/cases/${caseId}/network?hops=${hops}`, [caseId, hops]);
  const tl = useApi<any>(`/cases/${caseId}/timeline`, [caseId]);
  const models = useApi<any>("/models");

  if (loading) return <Loading label="Loading investigation" />;
  if (error || !d) return <ErrorBox error={error ?? "not found"} />;
  const c = d.case;
  const cite = (id: string) => { setFocus(id); };
  const flows = c.network_signals?.[0]?.top_referral_flows ?? [];

  return (
    <Page fullWidth title={`${c.case_id}`} subtitle={`Lead on ${c.anchor_provider_id} - ${c.specialty} • ${c.review_status}`}
      actions={<>
        <BandBadge band={c.review_priority} className="text-xs" />
        <Badge variant="outline">Score {f2(c.priority_score)}</Badge>
        <Button size="sm" variant="outline" className="h-8" onClick={async () => {
          try {
            const res = await fetch(`/api/cases/${c.case_id}/brief?format=markdown`);
            const data = await res.json();
            const blob = new Blob([data.markdown], { type: "text/markdown" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${c.case_id}_Report.md`;
            a.click();
            URL.revokeObjectURL(url);
          } catch (e) { alert("Failed to export report"); }
        }}>Export Report</Button>
        <Link to={`/provider/${c.anchor_provider_id}`}><Button size="sm" variant="outline" className="h-8">Provider Profile</Button></Link>
      </>}>
      
      {tabId === "overview" && (
        <div className="grid gap-4 xl:grid-cols-[1fr_400px] items-start">
          {/* LEFT: Intelligence & Overview */}
          <div className="space-y-4">
            <Card className="overflow-hidden">
              <CardHeader className="py-4 border-b border-border/50 bg-muted/5"><CardTitle>Case Summary</CardTitle></CardHeader>
              <CardContent className="p-0">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-y md:divide-y-0 md:divide-x divide-border/50">
                  <div className="p-5 xl:p-6"><KV k="Exposure" v={money(c.potential_exposure)} /></div>
                  <div className="p-5 xl:p-6"><KV k="Members" v={num(c.member_count)} /></div>
                  <div className="p-5 xl:p-6"><KV k="Claims" v={num(c.claim_count)} /></div>
                  <div className="p-5 xl:p-6"><KV k="Providers" v={c.provider_ids.length} /></div>
                  
                  <div className="p-5 xl:p-6">
                    <div className="flex flex-col">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">FWA Risk</div>
                      <div className="text-2xl font-semibold tracking-tight text-red-400 mb-2 leading-none">{f2(c.model_score)}</div>
                      <Bar value={c.model_score} className="w-full max-w-[100px] h-1" color="#f04452" />
                    </div>
                  </div>
                  
                  <div className="p-5 xl:p-6">
                    <div className="flex flex-col">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Anomaly</div>
                      <div className="text-2xl font-semibold tracking-tight text-amber-500 mb-2 leading-none">{f2(c.anomaly_score)}</div>
                      <Bar value={c.anomaly_score} className="w-full max-w-[100px] h-1" color="#f59e0b" />
                    </div>
                  </div>
                </div>
                
                {c.rule_hits.length > 0 && (
                  <div className="bg-muted/10 px-5 xl:px-6 py-3 border-t border-border/50 flex flex-wrap items-center gap-x-4 gap-y-2">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Rule Findings</span>
                    <div className="flex flex-wrap gap-2">
                      {c.rule_hits.map((r: string) => <Badge key={r} variant="outline" className="text-[10px] bg-background border-border/60 px-2 py-0.5 text-muted-foreground shadow-sm">{r.split("_").slice(1).join(" ")}</Badge>)}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader><CardTitle>Risk Decomposition</CardTitle></CardHeader>
              <CardContent><ComponentBars components={c.components} weights={d.weights} /></CardContent>
            </Card>
              
            <div className="grid gap-4 md:grid-cols-2 items-start">
              <Card className="flex flex-col h-full">
                <CardHeader className="py-3"><CardTitle>Forward Risk Forecast</CardTitle></CardHeader>
                <CardContent className="flex-1 p-4 pt-0"><ForecastPanel forecast={d.forecast} calibration={models.data?.forecast?.metrics} /></CardContent>
              </Card>

              <Card className="flex flex-col h-full">
                <CardHeader className="py-3"><CardTitle>Model Attribution (SHAP)</CardTitle></CardHeader>
                <CardContent className="flex-1 p-4 pt-0">
                  <div className="space-y-2 text-[12px]">
                    {d.shap ? [...d.shap.positive.slice(0, 5), ...d.shap.negative.slice(0, 3)].map((s: any) => (
                      <div key={s.feature} className="flex items-center gap-3"><span className="w-40 truncate font-medium text-muted-foreground">{s.label}</span><div className="h-1.5 flex-1 rounded-full bg-muted"><div className={`h-full rounded-full ${s.shap_value >= 0 ? "bg-red-500" : "bg-green-500"}`} style={{ width: `${Math.min(100, Math.abs(s.shap_value) * 20)}%` }} /></div>
                        <span className="w-12 text-right tabular-nums font-medium">{s.shap_value.toFixed(2)}</span><span className="w-16 text-right text-muted-foreground tabular-nums">val {Number(s.feature_value).toFixed(2)}</span></div>)) : <span className="text-muted-foreground">No SHAP output available.</span>}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader className="py-3"><CardTitle>Investigation Brief</CardTitle></CardHeader>
              <CardContent className="p-4 pt-0"><BriefPanel caseId={caseId} onCite={cite} /></CardContent>
            </Card>
          </div>

          {/* RIGHT: Temporal Intelligence */}
          <div className="space-y-4 xl:sticky xl:top-4">
            <Card>
              <CardHeader className="py-3 flex flex-row items-center justify-between">
                <CardTitle>Temporal Intelligence</CardTitle>
                <select value={series} onChange={(e) => setSeries(e.target.value)} className="h-6 rounded border border-border bg-muted text-[10px] outline-none px-1">
                  {SERIES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
                </select>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                {tl.loading ? <Loading label="Loading timeline" /> : tl.data ? <TimelinePanel timeline={tl.data} series={series} /> : <ErrorBox error={tl.error ?? ""} />}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {tabId === "network" && (
        <div className="grid gap-4 xl:grid-cols-[1fr_380px] items-start">
          {/* LEFT: Graph & Ledger */}
          <div className="space-y-4 flex flex-col min-w-0">
            <Card className="flex-1 flex flex-col min-h-[500px]">
              <CardHeader className="py-2">
                <CardTitle>Network Intelligence</CardTitle>
                <div className="flex gap-1 bg-muted rounded p-0.5">
                  <Button size="sm" variant={hops === 1 ? "secondary" : "ghost"} className="h-6 text-[10px] px-2" onClick={() => setHops(1)}>1-hop</Button>
                  <Button size="sm" variant={hops === 2 ? "secondary" : "ghost"} className="h-6 text-[10px] px-2" onClick={() => setHops(2)}>2-hop</Button>
                </div>
              </CardHeader>
              <CardContent className="p-0 flex-1 relative bg-[#0d121a]">
                {net.loading && <div className="absolute inset-0 bg-background/50 z-10 flex items-center justify-center"><Loading /></div>}
                {net.error && <ErrorBox error={net.error} />}
                {net.data && <NetworkGraph nodes={net.data.nodes} edges={net.data.edges} center={net.data.center} height={400} onSelect={(k, data) => { setSel({ k, data }); if (data.evidence_ids?.[0]) setFocus(data.evidence_ids[0]); }} />}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-0">
                <Tabs defaultValue="ledger">
                  <div className="border-b border-border bg-muted/20 px-2">
                    <TabsList className="bg-transparent h-10 justify-start rounded-none p-0">
                      <TabsTrigger value="ledger" className="h-10 text-[12px] rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Evidence Ledger</TabsTrigger>
                      <TabsTrigger value="similar" className="h-10 text-[12px] rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent">Historical Cases</TabsTrigger>
                    </TabsList>
                  </div>
                  <TabsContent value="ledger" className="p-0 m-0"><EvidenceTable caseId={caseId} focus={focus} />{focus && <div className="p-2 border-t border-border bg-muted/10"><button className="text-[11px] font-medium text-primary hover:underline" onClick={() => setFocus(null)}>Clear highlight: {focus}</button></div>}</TabsContent>
                  <TabsContent value="similar" className="p-4 m-0">
                    <div className="space-y-3">
                      {d.similar_cases.map((h: any) => (
                        <div key={h.id} className="rounded-md border border-border bg-card p-3 shadow-sm"><div className="flex items-center gap-3 mb-2"><b className="font-mono text-sm text-foreground">{h.id}</b><span className="text-[13px] text-muted-foreground">{h.doc.anchor_provider_id} • {h.doc.specialty}</span><Badge variant="outline">{h.doc.outcome}</Badge><span className="ml-auto text-[11px] text-muted-foreground font-mono">sim {h.score.toFixed(3)}</span></div>
                          <div className="text-[13px] text-foreground leading-relaxed">{h.doc.summary}</div><div className="mt-2 flex gap-2 text-[11px]"><span className="text-muted-foreground">Shared rules:</span> <span className="font-mono text-foreground">{h.shared_rules.join(", ") || "none"}</span></div></div>))}
                      {d.reviewer_memory.length > 0 && <div className="pt-4 border-t border-border mt-4"><div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Reviewer Memory</div>
                        <div className="space-y-2">{d.reviewer_memory.map((m: any) => <div key={m.id} className="rounded border border-border/50 bg-muted/20 p-2 text-[12px] text-muted-foreground"><strong className="text-foreground font-medium">{m.doc.decision}</strong> on <span className="font-mono">{m.doc.case_id}</span> &mdash; {m.doc.rationale}</div>)}</div></div>}
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>

          {/* RIGHT: Copilot, Evidence Summary, Selection Details, Decision */}
          <div className="space-y-4 flex flex-col xl:sticky xl:top-4 max-h-[calc(100vh-80px)] overflow-y-auto pb-4 hide-scrollbar">
            
            <Card className="flex-1 flex flex-col min-h-[450px]">
              <CardHeader className="py-3"><CardTitle>Nexus Copilot</CardTitle></CardHeader>
              <CardContent className="p-4 pt-0 flex-1 flex flex-col min-h-0 overflow-hidden">
                <Copilot caseId={caseId} onCite={cite} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Evidence Summary</CardTitle></CardHeader>
              <CardContent className="space-y-1 text-[11px] text-muted-foreground">
                {Object.entries(d.evidence_summary.reduce((a: any, r: any) => { a[r.evidence_type] = (a[r.evidence_type] ?? 0) + Number(r.n); return a; }, {})).map(([k, v]) => <div key={k} className="flex justify-between items-center"><span className="truncate pr-2">{k}</span><b className="tabular-nums text-foreground">{v as number}</b></div>)}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-0">
                <Tabs defaultValue="details">
                  <div className="border-b border-border bg-muted/20">
                    <TabsList className="bg-transparent h-10 w-full justify-start rounded-none border-b-0 p-0 overflow-x-auto hide-scrollbar">
                      <TabsTrigger value="details" className="h-10 text-[11px] rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent shrink-0">Details</TabsTrigger>
                      <TabsTrigger value="providers" className="h-10 text-[11px] rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent shrink-0">Providers ({d.providers.length})</TabsTrigger>
                      <TabsTrigger value="flows" className="h-10 text-[11px] rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent shrink-0">Flows</TabsTrigger>
                    </TabsList>
                  </div>
                  
                  <TabsContent value="details" className="p-4 m-0 min-h-[120px]">
                    {!sel ? <div className="text-[13px] text-muted-foreground flex items-center h-full">Select a node or edge in the graph to view details and linked evidence.</div> : sel.k === "node" ? (
                      <div className="text-[13px]">
                        <div className="flex items-center gap-2 mb-2"><b className="font-mono text-sm text-foreground">{sel.data.id}</b> <Badge variant="outline" className="text-[10px]">{sel.data.type}</Badge></div>
                        {sel.data.specialty && <div className="text-muted-foreground mb-2">{sel.data.specialty}</div>}
                        {sel.data.risk != null && <div className="text-muted-foreground mb-2 flex items-center gap-4"><span>Risk: <strong className="text-foreground">{f2(sel.data.risk)}</strong></span> <span>Degree: <strong className="text-foreground">{sel.data.degree}</strong></span></div>}
                        <div className="flex flex-wrap gap-2 items-center">
                          {sel.data.type === "provider" && <Link className="text-[11px] uppercase tracking-wider font-semibold text-primary hover:underline" to={`/provider/${sel.data.id}`}>Profile &rarr;</Link>}
                          <Link className="text-[11px] uppercase tracking-wider font-semibold text-primary hover:underline" to={`/network/${sel.data.id}`}>Explore &rarr;</Link>
                          {sel.data.evidence_ids?.map((e: string) => <button key={e} onClick={() => cite(e)} className="text-[11px] text-muted-foreground hover:text-foreground font-mono bg-accent px-1.5 py-0.5 rounded">{e}</button>)}
                        </div>
                      </div>
                    ) : (
                      <div className="text-[13px]">
                        <div className="mb-2"><b className="text-foreground uppercase tracking-wider text-[11px] mr-2">{sel.data.type.replace("_", " ")}</b> <Mono className="text-muted-foreground">{sel.data.source} &rarr; {sel.data.target}</Mono></div>
                        <div className="text-foreground mb-2">{sel.data.label}</div>
                        <div className="flex flex-wrap gap-1">{sel.data.evidence_ids?.map((e: string) => <button key={e} onClick={() => cite(e)} className="text-[11px] text-muted-foreground hover:text-foreground font-mono bg-accent px-1.5 py-0.5 rounded">{e}</button>)}</div>
                      </div>
                    )}
                  </TabsContent>
                  
                  <TabsContent value="providers" className="p-0 m-0 max-h-[300px] overflow-auto hide-scrollbar">
                    <table className="w-full text-[12px]"><thead className="sticky top-0 bg-muted/90 backdrop-blur text-left text-[10px] uppercase tracking-wider text-muted-foreground"><tr><th className="px-3 py-2 font-medium">Provider / Risk</th></tr></thead><tbody className="divide-y divide-border">
                      {d.providers.map((p: any) => <tr key={p.provider_id} className="hover:bg-accent/30 transition-colors"><td className="px-3 py-2 flex flex-col gap-1"><div className="flex justify-between items-center"><Link className="font-mono text-primary hover:underline" to={`/provider/${p.provider_id}`}>{p.provider_id}</Link>{p.provider_id === c.anchor_provider_id && <Badge variant="outline" className="text-[9px] bg-accent/50">anchor</Badge>}</div><div className="text-muted-foreground text-[11px] truncate">{p.specialty}</div><div className="flex items-center gap-2 mt-1"><Bar value={p.xgb_risk} className="w-8" color="#f04452" /><span className="tabular-nums text-[10px]">Risk: {f2(p.xgb_risk)}</span></div></td></tr>)}
                    </tbody></table>
                  </TabsContent>
                  
                  <TabsContent value="flows" className="p-4 m-0 text-[13px]">
                    <div className="grid gap-2">
                      {flows.slice(0, 5).map((f: any, i: number) => <div key={i} className="flex flex-col py-1 border-b border-border/50 last:border-0"><Mono className="text-[11px]">{f.from}</Mono><div className="flex justify-between text-[11px]"><Mono className="text-muted-foreground">&rarr; {f.to}</Mono> <span className="font-medium text-foreground">{f.referrals} refs</span></div></div>)}
                      {flows.length === 0 && <div className="text-muted-foreground text-[13px]">No extreme referral flows.</div>}
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            <Card className="mt-auto">
              <CardHeader className="py-3"><CardTitle>Human SIU Decision</CardTitle></CardHeader>
              <CardContent className="p-4 pt-0">
                <DecisionPanel caseId={caseId} status={c.review_status} reviews={d.reviews} onDone={reload} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}

    </Page>
  );
}

const KV = ({ k, v }: { k: string; v: any }) => <div className="flex flex-col"><div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">{k}</div><div className="text-2xl font-semibold tracking-tight text-foreground leading-none">{v}</div></div>;
