import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BandBadge } from "@/components/ui/badge";
import { ErrorBox, Loading, Page, Stat } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { BAND_HEX, money, num, pct } from "@/lib/utils";

export default function CommandCenter() {
  const { data: d, error, loading } = useApi<any>("/command-center");
  if (loading) return <Loading label="Loading command center" />;
  if (error || !d) return <ErrorBox error={error ?? "no data"} />;
  const max = d.funnel[0].count;
  const xgb = d.model_headline.xgboost, rules = d.model_headline.rules_only_baseline, iso = d.model_headline.isolation_forest_baseline;
  return (
    <Page title="Command Center" subtitle={`Alert compression funnel computed from the executed pipeline - as of ${d.as_of}`}>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="Claims" value={num(d.counts.claims)} sub={`${num(d.counts.quarantined)} quarantined at ingest`} />
        <Stat label="Providers" value={num(d.counts.providers)} /><Stat label="Members" value={num(d.counts.members)} /><Stat label="Facilities" value={num(d.counts.facilities)} />
        <Stat label="Referrals" value={num(d.counts.referrals)} /><Stat label="Evidence objects" value={num(d.counts.evidence)} />
        <Stat label="Potential exposure (cases)" value={money(d.total_potential_exposure)} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader><CardTitle>Alert compression funnel</CardTitle><span className="text-[11px] text-muted-foreground">{num(d.funnel[0].count)} claims &rarr; {d.funnel[5].count} SIU priorities</span></CardHeader>
          <CardContent className="space-y-2.5">
            {d.funnel.map((f: any, i: number) => (
              <div key={f.stage} title={f.definition}>
                <div className="mb-0.5 flex items-baseline justify-between text-xs"><span className="font-medium">{f.stage}</span><span className="tabular-nums">{num(f.count)} <span className="text-muted-foreground">{i > 0 ? `(${pct(f.count / d.funnel[i - 1].count, f.count / d.funnel[i - 1].count < 0.01 ? 2 : 1)} of previous)` : ""}</span></span></div>
                <div className="h-6 overflow-hidden rounded bg-muted"><div className="flex h-full items-center rounded bg-gradient-to-r from-sky-600 to-sky-400 px-2 text-[10px] font-semibold text-slate-950" style={{ width: `${Math.max(2.5, (Math.log10(f.count + 1) / Math.log10(max + 1)) * 100)}%` }}>{i === 0 ? "" : ""}</div></div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">{f.definition}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card><CardHeader><CardTitle>Cases by priority band</CardTitle></CardHeader><CardContent>
            <ResponsiveContainer width="100%" height={150}><BarChart data={["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => ({ b, n: d.bands.find((x: any) => x.band === b)?.n ?? 0 }))}>
              <XAxis dataKey="b" tick={{ fontSize: 10, fill: "#94a3b8" }} /><YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} allowDecimals={false} width={24} /><Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 11 }} />
              <Bar dataKey="n" radius={3}>{["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => <Cell key={b} fill={BAND_HEX[b]} />)}</Bar></BarChart></ResponsiveContainer>
          </CardContent></Card>
        </div>
        <Card className="xl:col-span-2">
          <CardHeader><CardTitle>Top investigation leads</CardTitle><Link to="/queue" className="text-xs text-sky-400 hover:underline">Open SIU queue</Link></CardHeader>
          <CardContent className="p-0"><table className="w-full text-xs"><thead className="text-left text-[10px] uppercase text-muted-foreground"><tr><th className="p-2">Case</th><th>Anchor</th><th>Specialty</th><th>Priority</th><th>Exposure</th><th>Patterns</th></tr></thead><tbody>
            {d.top_cases.map((c: any) => <tr key={c.case_id} className="border-t border-border hover:bg-accent"><td className="p-2"><Link to={`/case/${c.case_id}`} className="font-mono text-sky-400 hover:underline">{c.case_id}</Link></td><td>{c.anchor_provider_id}</td><td>{c.specialty}</td>
              <td><BandBadge band={c.review_priority} /> <span className="tabular-nums text-muted-foreground">{c.priority_score.toFixed(2)}</span></td><td className="tabular-nums">{money(c.potential_exposure)}</td><td className="max-w-[260px] truncate text-muted-foreground">{c.patterns.join(", ")}</td></tr>)}
          </tbody></table></CardContent>
        </Card>
        <Card><CardHeader><CardTitle>Rule findings (evidence ledger)</CardTitle></CardHeader><CardContent>
          <ResponsiveContainer width="100%" height={240}><BarChart layout="vertical" data={Object.values(d.rule_hits.reduce((a: any, r: any) => { a[r.rule_id] = a[r.rule_id] ?? { rule: r.rule_id.split("_")[0], n: 0 }; a[r.rule_id].n += r.n; return a; }, {}))}>
            <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} /><YAxis type="category" dataKey="rule" width={36} tick={{ fontSize: 10, fill: "#94a3b8" }} /><Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 11 }} /><Bar dataKey="n" fill="#38bdf8" radius={3} /></BarChart></ResponsiveContainer>
        </CardContent></Card>
      </div>
    </Page>
  );
}
const Row = ({ k, v }: { k: string; v: any }) => <div className="flex justify-between"><span className="text-muted-foreground">{k}</span><b className="tabular-nums">{v ?? "-"}</b></div>;
