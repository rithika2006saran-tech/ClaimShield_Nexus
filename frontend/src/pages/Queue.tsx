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
  const [reviewed, setReviewed] = useState(false);
  const { data, error, loading } = useApi<any>(`/queue?capacity=${cap}&include_reviewed=${reviewed}`);
  return (
    <Page title="SIU Queue" subtitle="Highest-value investigations for the selected investigator capacity."
      actions={<>
        <Button size="sm" variant={reviewed ? "secondary" : "outline"} onClick={() => setReviewed(!reviewed)} className={reviewed ? "bg-accent" : "text-muted-foreground"}>Include Closed / Working</Button>
        <div className="flex gap-1">{[5, 10, 20].map((c) => <Button key={c} size="sm" variant={cap === c ? "default" : "outline"} onClick={() => setCap(c)}>Top {c}</Button>)}</div></>}>
      {loading && <Loading />}{error && <ErrorBox error={error} />}
      {data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Capacity" value={data.cases.length} sub={`of ${data.total_cases_available} cases available`} />
            <Stat label="Exposure in queue" value={money(data.selected_exposure)} sub={`${pct(data.exposure_coverage)} of total potential exposure`} />
            <Stat label="Policy version" value={<span className="text-sm">{data.policy_version}</span>} />
            <Stat label="Weights" value={<div className="flex flex-wrap gap-x-2 gap-y-0.5 mt-1 text-[10px] text-muted-foreground leading-tight">{Object.entries<number>(data.weights).map(([k, v]) => {
              const label = { model_risk: "Model Risk", rule_evidence: "Rules", peer_deviation: "Peer Deviation", network: "Network", temporal: "Timeline", anomaly: "Anomaly", evidence_strength: "Evidence Quality", exposure: "Exposure", member_impact: "Member Impact" }[k] || k.replace("_", " ");
              return <span key={k}>{label}: <b className="text-sky-400">{Math.round(v * 100)}%</b></span>;
            })}</div>} />
          </div>
          <Card className="overflow-x-auto border-none shadow-sm bg-card/50">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
                <tr><th className="p-3">#</th><th className="p-3">Case</th><th className="p-3">Anchor</th><th className="p-3">Specialty</th><th className="p-3">Priority</th><th className="p-3 w-32">Score</th><th className="p-3">Exposure</th><th className="p-3">Members</th><th className="p-3">30/60/90</th><th className="p-3">Top drivers</th><th className="p-3">Status</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.cases.map((c: any) => (
                  <tr key={c.case_id} className="hover:bg-accent/50 transition-colors">
                    <td className="p-3 tabular-nums text-muted-foreground">{c.rank}</td>
                    <td className="p-3"><Link to={`/case/${c.case_id}`} className="font-mono font-bold text-sky-400 hover:text-sky-300">{c.case_id}</Link></td>
                    <td className="p-3"><Link to={`/provider/${c.anchor_provider_id}`} className="font-medium hover:underline">{c.anchor_provider_id}</Link></td><td className="p-3 text-muted-foreground">{c.specialty}</td>
                    <td className="p-3"><BandBadge band={c.review_priority} /></td><td className="p-3"><div className="flex items-center gap-2"><Bar value={c.priority_score} color="#38bdf8" /><span className="tabular-nums font-medium">{c.priority_score.toFixed(2)}</span></div></td>
                    <td className="p-3 tabular-nums font-medium">{money(c.potential_exposure)}</td><td className="p-3 tabular-nums text-muted-foreground">{c.member_count}</td>
                    <td className="p-3 tabular-nums text-muted-foreground" title={c.forecast_label}>{[c.forecast_30d, c.forecast_60d, c.forecast_90d].map((v: number) => v?.toFixed(2)).join(" / ")}</td>
                    <td className="p-3 max-w-[240px] text-muted-foreground truncate">{c.top_drivers.join(", ").replaceAll("_", " ")}</td><td className="p-3"><Badge variant="outline" className="bg-background/50">{c.review_status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

        </>
      )}
    </Page>
  );
}
