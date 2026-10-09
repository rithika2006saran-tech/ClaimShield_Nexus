import { useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { BandBadge, Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Bar, ErrorBox, Loading, Page, Stat } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { money, pct } from "@/lib/utils";

export default function Queue() {
  const [cap, setCap] = useState(10);
  const [offset, setOffset] = useState(0);
  const [reviewed, setReviewed] = useState(false);
  const { data, error, loading } = useApi<any>(`/queue?capacity=${cap}&offset=${offset}&include_reviewed=${reviewed}`);
  return (
    <Page title="SIU Queue" subtitle="Highest-value investigation priorities based on selected capacity."
      actions={<>
        <Button size="sm" variant={reviewed ? "secondary" : "outline"} onClick={() => { setReviewed(!reviewed); setOffset(0); }} className={reviewed ? "bg-accent text-[11px] uppercase tracking-wider h-8" : "text-muted-foreground text-[11px] uppercase tracking-wider h-8"}>Include Closed / Working</Button>
        <div className="flex bg-muted rounded p-0.5">{(["All", 5, 10, 20] as const).map((c) => {
          const isAll = c === "All";
          const capValue = isAll ? 10000 : (c as number);
          return <Button key={c} size="sm" variant={cap === capValue ? "secondary" : "ghost"} className="h-7 text-[11px] px-3" onClick={() => { setCap(capValue); setOffset(0); }}>{isAll ? "All" : `Top ${c}`}</Button>
        })}</div></>}>
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Capacity" value={data.cases.length} sub={`of ${data.total_cases_available} cases available`} />
            <Stat label="Exposure in queue" value={money(data.selected_exposure)} sub={`${pct(data.exposure_coverage)} of total potential exposure`} className="border-primary/20 bg-primary/5" />
            <Stat label="Policy version" value={<span className="text-[13px] font-mono text-muted-foreground">{data.policy_version}</span>} />
            <Stat label="Weights" value={<div className="flex flex-wrap gap-x-2 gap-y-1 mt-1 text-[10px] text-muted-foreground leading-tight">{Object.entries<number>(data.weights).map(([k, v]) => {
              const label = { model_risk: "Model Risk", rule_evidence: "Rules", peer_deviation: "Peer Deviation", network: "Network", temporal: "Timeline", anomaly: "Anomaly", evidence_strength: "Evidence Quality", exposure: "Exposure", member_impact: "Member Impact" }[k] || k.replace("_", " ");
              return <span key={k}>{label}: <b className="text-primary">{Math.round(v * 100)}%</b></span>;
            })}</div>} />
          </div>
          <Card className="overflow-hidden border border-border shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-[12px] whitespace-nowrap">
                <thead className="bg-muted/30 text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                  <tr>
                    <th className="px-4 py-3 font-medium">#</th>
                    <th className="px-4 py-3 font-medium">Case</th>
                    <th className="px-4 py-3 font-medium">Anchor</th>
                    <th className="px-4 py-3 font-medium">Specialty</th>
                    <th className="px-4 py-3 font-medium">Priority</th>
                    <th className="px-4 py-3 font-medium w-28">Score</th>
                    <th className="px-4 py-3 font-medium text-right">Exposure</th>
                    <th className="px-4 py-3 font-medium text-right">Members</th>
                    <th className="px-4 py-3 font-medium text-right" title="30, 60, 90 day forward risk">30/60/90</th>
                    <th className="px-4 py-3 font-medium">Top Drivers</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.cases.map((c: any) => (
                    <tr key={c.case_id} className="hover:bg-accent/40 transition-colors">
                      <td className="px-4 py-2 tabular-nums text-muted-foreground">{c.rank}</td>
                      <td className="px-4 py-2"><Link to={`/case/${c.case_id}`} className="font-mono font-medium text-primary hover:underline">{c.case_id}</Link></td>
                      <td className="px-4 py-2 font-mono text-muted-foreground"><Link to={`/provider/${c.anchor_provider_id}`} className="hover:underline">{c.anchor_provider_id}</Link></td>
                      <td className="px-4 py-2 text-muted-foreground truncate max-w-[120px]" title={c.specialty}>{c.specialty}</td>
                      <td className="px-4 py-2"><BandBadge band={c.review_priority} /></td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <Bar value={c.priority_score} className="w-10" color="hsl(var(--primary))" />
                          <span className="tabular-nums font-medium">{c.priority_score.toFixed(2)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums font-medium">{money(c.potential_exposure)}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">{c.member_count}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted-foreground text-[11px]" title={c.forecast_label}>{[c.forecast_30d, c.forecast_60d, c.forecast_90d].map((v: number) => v?.toFixed(2)).join(" / ")}</td>
                      <td className="px-4 py-2 max-w-[180px] truncate text-[11px] text-muted-foreground" title={c.top_drivers.join(", ")}>{c.top_drivers.join(", ").replaceAll("_", " ")}</td>
                      <td className="px-4 py-2"><Badge variant="outline" className="bg-transparent text-[10px]">{c.review_status}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              Showing {data.offset + 1} to {Math.min(data.offset + data.cases.length, data.total_cases_available)} of {data.total_cases_available}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - cap))}>Previous</Button>
              <Button size="sm" variant="outline" disabled={data.offset + data.cases.length >= data.total_cases_available} onClick={() => setOffset(offset + cap)}>Next</Button>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
