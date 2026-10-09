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

/** Investigation Workspace (hero): LEFT summary/risk/evidence/timeline - CENTER network - RIGHT Copilot - BOTTOM brief/forecast/decision. */
export default function Workspace() {
  const { caseId = "CASE-1024" } = useParams();
  const { data: d, error, loading, reload } = useApi<any>(`/cases/${caseId}`, [caseId]);
  const [hops, setHops] = useState(1);
  const [sel, setSel] = useState<any>(null);
  const [tab, setTab] = useState("brief");
  const [focus, setFocus] = useState<string | null>(null);
  const [series, setSeries] = useState("claims_30d");
  const net = useApi<any>(`/cases/${caseId}/network?hops=${hops}`, [caseId, hops]);
  const tl = useApi<any>(`/cases/${caseId}/timeline`, [caseId]);
  const models = useApi<any>("/models");

  if (loading) return <Loading label="Loading investigation" />;
  if (error || !d) return <ErrorBox error={error ?? "not found"} />;
  const c = d.case;
  const cite = (id: string) => { setFocus(id); setTab("ledger"); setTimeout(() => document.getElementById("bottom")?.scrollIntoView({ behavior: "smooth" }), 50); };
  const flows = c.network_signals?.[0]?.top_referral_flows ?? [];

  return (
    <Page title={`${c.case_id} - investigation lead on ${c.anchor_provider_id}`}
      actions={<><BandBadge band={c.review_priority} className="text-xs" /><Badge>{c.review_status}</Badge>
        <Button size="sm" variant="outline" onClick={async () => {
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
        <Link to={`/provider/${c.anchor_provider_id}`}><Button size="sm" variant="outline">Provider profile</Button></Link></>}>
      <div className="grid gap-4 xl:grid-cols-12">
        {/* LEFT */}
        <div className="space-y-4 xl:col-span-3">
          <Card><CardHeader><CardTitle>Case summary</CardTitle><span className="text-lg font-semibold tabular-nums">{f2(c.priority_score)}</span></CardHeader>
            <CardContent className="space-y-2 text-xs">
              <p className="leading-relaxed text-muted-foreground">{c.summary}</p>
              <div className="grid grid-cols-2 gap-2">
                <KV k="Exposure" v={money(c.potential_exposure)} /><KV k="Members" v={num(c.member_count)} /><KV k="Claims" v={num(c.claim_count)} /><KV k="Providers" v={c.provider_ids.length} />
                <KV k="FWA risk score" v={<div className="flex items-center gap-2"><Bar value={c.model_score} color="#38bdf8" /><span>{f2(c.model_score)}</span></div>} />
                <KV k="Anomaly score" v={<div className="flex items-center gap-2"><Bar value={c.anomaly_score} color="#38bdf8" /><span>{f2(c.anomaly_score)}</span></div>} />
              </div>
              <div className="flex flex-wrap gap-1">{c.rule_hits.map((r: string) => <Badge key={r} className="text-sky-300">{r.split("_")[0]} {r.split("_").slice(1).join(" ").toLowerCase()}</Badge>)}</div>
            </CardContent></Card>
          <Card><CardHeader><CardTitle>Risk decomposition</CardTitle></CardHeader><CardContent><ComponentBars components={c.components} weights={d.weights} /></CardContent></Card>
          <Card><CardHeader><CardTitle>Evidence ledger summary</CardTitle><button className="text-[11px] text-sky-400 hover:underline" onClick={() => { setFocus(null); setTab("ledger"); }}>open</button></CardHeader>
            <CardContent className="space-y-1 text-xs">
              {Object.entries(d.evidence_summary.reduce((a: any, r: any) => { a[r.evidence_type] = (a[r.evidence_type] ?? 0) + Number(r.n); return a; }, {})).map(([k, v]) => <div key={k} className="flex justify-between"><span>{k}</span><b className="tabular-nums">{v as number}</b></div>)}
            </CardContent></Card>
          <Card><CardHeader><CardTitle>What changed?</CardTitle>
            <select value={series} onChange={(e) => setSeries(e.target.value)} className="h-6 rounded border border-input bg-background text-[10px]">{SERIES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}</select></CardHeader>
            <CardContent>{tl.loading ? <Loading /> : tl.data ? <TimelinePanel timeline={tl.data} series={series} /> : <ErrorBox error={tl.error ?? ""} />}
              </CardContent></Card>
        </div>

        {/* CENTER */}
        <div className="space-y-4 xl:col-span-6">
          <Card><CardHeader><CardTitle>Network intelligence</CardTitle>
            <div className="flex gap-1"><Button size="sm" variant={hops === 1 ? "default" : "outline"} onClick={() => setHops(1)}>1-hop</Button><Button size="sm" variant={hops === 2 ? "default" : "outline"} onClick={() => setHops(2)}>2-hop</Button></div></CardHeader>
            <CardContent>
              {net.loading && <Loading />}{net.error && <ErrorBox error={net.error} />}
              {net.data && <NetworkGraph nodes={net.data.nodes} edges={net.data.edges} center={net.data.center} height={470} onSelect={(k, data) => { setSel({ k, data }); if (data.evidence_ids?.[0]) setFocus(data.evidence_ids[0]); }} />}
              <div className="mt-2 grid gap-2 text-xs md:grid-cols-2">
                <div className="rounded border border-border p-2">{!sel ? <span className="text-muted-foreground">Click a node or edge for details and linked evidence.</span> : sel.k === "node" ? (
                  <div><b className="font-mono">{sel.data.id}</b> <span className="text-muted-foreground">{sel.data.type}{sel.data.specialty ? ` - ${sel.data.specialty}` : ""}</span>
                    {sel.data.risk != null && <div>FWA risk score {f2(sel.data.risk)} - degree {sel.data.degree} - betweenness {sel.data.betweenness?.toFixed(3)}</div>}
                    <div className="mt-1 flex gap-2">{sel.data.type === "provider" && <Link className="text-sky-400 hover:underline" to={`/provider/${sel.data.id}`}>profile</Link>}<Link className="text-sky-400 hover:underline" to={`/network/${sel.data.id}`}>explore</Link>
                      {sel.data.evidence_ids?.map((e: string) => <button key={e} onClick={() => cite(e)} className="text-sky-400 hover:underline"><Mono>{e}</Mono></button>)}</div></div>
                ) : (<div><b>{sel.data.type.replace("_", " ")}</b> <Mono>{sel.data.source} &rarr; {sel.data.target}</Mono><div>{sel.data.label}</div>
                  {sel.data.evidence_ids?.map((e: string) => <button key={e} onClick={() => cite(e)} className="mr-2 text-sky-400 hover:underline"><Mono>{e}</Mono></button>)}</div>)}</div>
                <div className="rounded border border-border p-2"><div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Top Connection Flows</div>
                  {flows.slice(0, 4).map((f: any, i: number) => <div key={i}><Mono>{f.from} &rarr; {f.to}</Mono> <span className="text-muted-foreground">{f.referrals} referrals</span></div>)}
                  <div className="mt-1 text-muted-foreground">Shared facilities: {Object.entries(c.network_signals?.[0]?.shared_facilities ?? {}).map(([k, v]) => `${k} (${v})`).join(", ") || "none"}</div></div>
              </div>
            </CardContent></Card>
          <Card><CardHeader><CardTitle>Providers in case</CardTitle></CardHeader><CardContent className="max-h-64 overflow-auto p-0">
            <table className="w-full text-sm"><thead className="sticky top-0 bg-muted/80 backdrop-blur text-left text-xs uppercase tracking-wider text-muted-foreground"><tr><th className="p-3">Provider</th><th className="p-3">Specialty</th><th className="p-3">FWA risk</th><th className="p-3">Anomaly</th><th className="p-3">Degree</th><th className="p-3">Rule findings</th></tr></thead><tbody className="divide-y divide-border">
              {d.providers.map((p: any) => <tr key={p.provider_id} className="hover:bg-accent/50 transition-colors"><td className="p-3"><Link className="font-mono font-medium text-sky-400 hover:text-sky-300" to={`/provider/${p.provider_id}`}>{p.provider_id}</Link>{p.provider_id === c.anchor_provider_id && <Badge variant="secondary" className="ml-2 text-[10px]">anchor</Badge>}</td>
                <td className="p-3 text-muted-foreground">{p.specialty}</td><td className="p-3"><div className="flex items-center gap-2"><Bar value={p.xgb_risk} color="#38bdf8" /><span className="tabular-nums font-medium">{f2(p.xgb_risk)}</span></div></td><td className="p-3"><div className="flex items-center gap-2"><Bar value={p.anomaly_score} color="#38bdf8" /><span className="tabular-nums font-medium">{f2(p.anomaly_score)}</span></div></td><td className="p-3 text-muted-foreground">{p.degree}</td><td className="p-3 text-muted-foreground">{p.rule_findings}</td></tr>)}
            </tbody></table></CardContent></Card>
        </div>

        {/* RIGHT */}
        <Card className="flex h-[640px] flex-col xl:col-span-3 xl:sticky xl:top-3 xl:self-start"><CardHeader><CardTitle>Nexus Copilot</CardTitle></CardHeader>
          <CardContent className="min-h-0 flex-1"><Copilot caseId={caseId} onCite={cite} /></CardContent></Card>
      </div>

      {/* BOTTOM */}
      <div id="bottom" className="mt-4 grid gap-4 xl:grid-cols-12">
        <Card className="xl:col-span-8"><CardContent>
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList><TabsTrigger value="brief">Investigation Brief</TabsTrigger><TabsTrigger value="ledger">Evidence Ledger</TabsTrigger><TabsTrigger value="similar">Similar cases</TabsTrigger><TabsTrigger value="shap">Model attribution</TabsTrigger></TabsList>
            <TabsContent value="brief"><BriefPanel caseId={caseId} onCite={cite} /></TabsContent>
            <TabsContent value="ledger"><EvidenceTable caseId={caseId} focus={focus} />{focus && <button className="mt-1 text-[11px] text-sky-400" onClick={() => setFocus(null)}>clear focus ({focus})</button>}</TabsContent>
            <TabsContent value="similar">
              <div className="space-y-2 text-xs">
                {d.similar_cases.map((h: any) => (
                  <div key={h.id} className="rounded border border-border p-2"><div className="flex items-center gap-2"><b className="font-mono">{h.id}</b><span>{h.doc.anchor_provider_id} - {h.doc.specialty}</span><Badge>{h.doc.outcome}</Badge>
                    <span className="ml-auto text-muted-foreground">score {h.score.toFixed(4)}</span></div>
                    <div className="mt-1 text-muted-foreground">{h.doc.summary}</div><div className="mt-1">shared rules: {h.shared_rules.join(", ") || "none"}</div></div>))}
                {d.reviewer_memory.length > 0 && <div className="pt-2"><div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Reviewer memory</div>
                  {d.reviewer_memory.map((m: any) => <div key={m.id} className="mb-1 rounded border border-border p-2"><b>{m.doc.decision}</b> on {m.doc.case_id} - {m.doc.rationale}</div>)}</div>}
              </div></TabsContent>
            <TabsContent value="shap"><div className="space-y-1 text-xs">
              {d.shap ? [...d.shap.positive.slice(0, 5), ...d.shap.negative.slice(0, 3)].map((s: any) => (
                <div key={s.feature} className="flex items-center gap-2"><span className="w-56 truncate">{s.label}</span><div className="h-2 flex-1 rounded bg-muted"><div className={`h-full rounded ${s.shap_value >= 0 ? "bg-red-500" : "bg-green-500"}`} style={{ width: `${Math.min(100, Math.abs(s.shap_value) * 20)}%` }} /></div>
                  <span className="w-16 text-right tabular-nums">{s.shap_value.toFixed(2)}</span><span className="w-20 text-right text-muted-foreground">val {Number(s.feature_value).toFixed(2)}</span></div>)) : <span className="text-muted-foreground">No SHAP output for this provider.</span>}
              </div></TabsContent>
          </Tabs></CardContent></Card>
        <div className="space-y-4 xl:col-span-4">
          <Card><CardHeader><CardTitle>30 / 60 / 90 forward risk</CardTitle></CardHeader><CardContent><ForecastPanel forecast={d.forecast} calibration={models.data?.forecast?.metrics} /></CardContent></Card>
          <Card><CardHeader><CardTitle>Human SIU decision</CardTitle></CardHeader><CardContent><DecisionPanel caseId={caseId} status={c.review_status} reviews={d.reviews} onDone={reload} /></CardContent></Card>
        </div>
      </div>
    </Page>
  );
}
const KV = ({ k, v }: { k: string; v: any }) => <div><div className="text-[10px] uppercase tracking-wider text-muted-foreground">{k}</div><div className="text-sm font-semibold tabular-nums">{v}</div></div>;
