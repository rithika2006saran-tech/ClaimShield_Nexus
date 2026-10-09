import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, LabelList } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BandBadge } from "@/components/ui/badge";
import { ErrorBox, Loading, Page, Stat } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { BAND_HEX, money, num, pct } from "@/lib/utils";

export default function CommandCenter() {
  const { data: d, error, loading } = useApi<any>("/command-center");
  
  if (loading) return <Loading label="Loading Command Center" />;
  if (error || !d) return <ErrorBox error={error ?? "no data"} />;
  
  const max = d.funnel[0].count;

  return (
    <Page title="Command Center" subtitle={`Alert compression funnel and workload overview — as of ${d.as_of}`}>
      
      {/* KPI Row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7 mb-4">
        <Stat label="Claims" value={num(d.counts.claims)} sub={`${num(d.counts.quarantined)} quarantined`} />
        <Stat label="Providers" value={num(d.counts.providers)} />
        <Stat label="Members" value={num(d.counts.members)} />
        <Stat label="Facilities" value={num(d.counts.facilities)} />
        <Stat label="Referrals" value={num(d.counts.referrals)} />
        <Stat label="Evidence" value={num(d.counts.evidence)} />
        <Stat label="Exposure" value={money(d.total_potential_exposure)} className="border-primary/20 bg-primary/5" />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {/* Funnel */}
        <Card className="xl:col-span-2">
          <CardHeader className="py-3">
            <div className="flex justify-between items-center w-full">
              <CardTitle>Alert Compression Funnel</CardTitle>
              <span className="text-[11px] font-medium text-muted-foreground bg-muted/30 px-2 py-0.5 rounded">
                {num(d.funnel[0].count)} claims &rarr; {d.funnel[5].count} SIU priorities
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 pb-4">
            {d.funnel.map((f: any, i: number) => (
              <div key={f.stage} title={f.definition}>
                <div className="mb-1 flex items-baseline justify-between text-[12px]">
                  <span className="font-semibold text-foreground">{f.stage}</span>
                  <span className="tabular-nums font-medium">{num(f.count)} <span className="text-muted-foreground text-[10px] ml-1">{i > 0 ? `(${pct(f.count / d.funnel[i - 1].count, f.count / d.funnel[i - 1].count < 0.01 ? 2 : 1)} of prev)` : ""}</span></span>
                </div>
                <div className="h-4 overflow-hidden rounded-full bg-muted">
                  <div className="flex h-full items-center rounded-full bg-gradient-to-r from-primary to-primary/70" style={{ width: `${Math.max(1, (Math.log10(f.count + 1) / Math.log10(max + 1)) * 100)}%` }} />
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground/70 leading-tight">{f.definition}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Priority Band Distribution */}
        <Card className="flex flex-col">
          <CardHeader className="py-3"><CardTitle>Cases by Priority</CardTitle></CardHeader>
          <CardContent className="flex-1 pb-4 relative min-h-[250px]">
            <div className="absolute inset-0 px-6 pb-2 pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => ({ b, n: d.bands.find((x: any) => x.band === b)?.n ?? 0 }))} barCategoryGap="15%" margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" opacity={0.5} />
                  <XAxis dataKey="b" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))", fontWeight: 500 }} tickLine={false} axisLine={false} tickMargin={12} />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} width={40} tickLine={false} axisLine={false} />
                  <Tooltip 
                    cursor={{ fill: "hsl(var(--muted)/0.2)" }} 
                    content={({ active, payload, label }: any) => {
                      if (active && payload && payload.length) {
                        return (
                          <div className="rounded-md border border-border bg-card/95 backdrop-blur px-3 py-2 text-xs shadow-xl">
                            <div className="font-semibold text-foreground mb-0.5">{label} Priority</div>
                            <div className="text-muted-foreground flex items-center gap-1.5">
                              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: payload[0].payload.fill || payload[0].color }} />
                              <span className="font-medium text-foreground">{payload[0].value}</span> active cases
                            </div>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar dataKey="n" radius={[6, 6, 0, 0]} maxBarSize={75}>
                    {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((b) => <Cell key={b} fill={BAND_HEX[b]} />)}
                    <LabelList dataKey="n" position="top" fill="hsl(var(--muted-foreground))" fontSize={11} fontWeight={600} offset={10} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Top Investigation Leads */}
        <Card className="xl:col-span-2">
          <CardHeader className="py-3 flex flex-row items-center justify-between">
            <CardTitle>Top Investigation Leads</CardTitle>
            <Link to="/queue" className="text-[11px] font-semibold text-primary uppercase tracking-wider hover:underline">View Queue &rarr;</Link>
          </CardHeader>
          <CardContent className="p-0 overflow-auto">
            <table className="w-full text-[12px]">
              <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                <tr><th className="px-4 py-2 font-medium">Case</th><th className="px-4 py-2 font-medium">Anchor</th><th className="px-4 py-2 font-medium">Specialty</th><th className="px-4 py-2 font-medium">Priority</th><th className="px-4 py-2 font-medium text-right">Exposure</th><th className="px-4 py-2 font-medium">Patterns</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.top_cases.map((c: any) => (
                  <tr key={c.case_id} className="hover:bg-accent/40 transition-colors">
                    <td className="px-4 py-2"><Link to={`/case/${c.case_id}`} className="font-mono font-medium text-primary hover:underline">{c.case_id}</Link></td>
                    <td className="px-4 py-2 font-mono text-muted-foreground">{c.anchor_provider_id}</td>
                    <td className="px-4 py-2 text-muted-foreground truncate max-w-[120px]">{c.specialty}</td>
                    <td className="px-4 py-2"><div className="flex items-center gap-2"><BandBadge band={c.review_priority} /> <span className="tabular-nums text-[10px] text-muted-foreground">{c.priority_score.toFixed(2)}</span></div></td>
                    <td className="px-4 py-2 text-right tabular-nums font-medium">{money(c.potential_exposure)}</td>
                    <td className="px-4 py-2 max-w-[200px] truncate text-[11px] text-muted-foreground" title={c.patterns.join(", ")}>{c.patterns.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Rule Findings */}
        <Card className="flex flex-col">
          <CardHeader className="py-3"><CardTitle>Rule Findings (Evidence)</CardTitle></CardHeader>
          <CardContent className="flex-1 pb-4 pr-6 relative min-h-[200px]">
            <div className="absolute inset-0 px-6 pb-4 pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={Object.values(d.rule_hits.reduce((a: any, r: any) => { a[r.rule_id] = a[r.rule_id] ?? { rule: r.rule_id.split("_")[0], n: 0 }; a[r.rule_id].n += r.n; return a; }, {}))} barCategoryGap="20%">
                  <XAxis type="number" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="rule" width={40} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} interval={0} />
                  <Tooltip cursor={{ fill: "hsl(var(--muted)/0.4)" }} contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: 11 }} formatter={(value: number) => [`${value} hits`, "Evidence"]} />
                  <Bar dataKey="n" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]} maxBarSize={24} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </Page>
  );
}
