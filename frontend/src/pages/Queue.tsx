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
    <Page title="SIU Queue" subtitle="Highest-value investigations for the selected investigator capacity. Ranked by a nine-component priority policy, not model score alone."
      actions={<>
        <label className="flex items-center gap-1 text-xs text-muted-foreground"><input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} /> include closed</label>
        <div className="flex gap-1">{[5, 10, 20].map((c) => <Button key={c} size="sm" variant={cap === c ? "default" : "outline"} onClick={() => setCap(c)}>Top {c}</Button>)}</div></>}>
      {loading && <Loading />}{error && <ErrorBox error={error} />}
      {data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Capacity" value={data.cases.length} sub={`of ${data.total_cases_available} cases available`} />
            <Stat label="Exposure in queue" value={money(data.selected_exposure)} sub={`${pct(data.exposure_coverage)} of total potential exposure`} />
            <Stat label="Policy version" value={<span className="text-sm">{data.policy_version}</span>} />
            <Stat label="Weights" value={<span className="text-[10px] font-normal leading-4">{Object.entries<number>(data.weights).map(([k, v]) => `${k.replace("_", " ")} ${v}`).join(" - ")}</span>} />
          </div>
          <Card className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-left text-[10px] uppercase text-muted-foreground"><tr><th className="p-2">#</th><th>Case</th><th>Anchor</th><th>Specialty</th><th>Priority</th><th className="w-28">Score</th><th>Exposure</th><th>Members</th><th>30/60/90</th><th>Top drivers</th><th>Status</th></tr></thead>
              <tbody>
                {data.cases.map((c: any) => (
                  <tr key={c.case_id} className="border-t border-border hover:bg-accent">
                    <td className="p-2 tabular-nums text-muted-foreground">{c.rank}</td>
                    <td><Link to={`/case/${c.case_id}`} className="font-mono font-semibold text-sky-400 hover:underline">{c.case_id}</Link></td>
                    <td><Link to={`/provider/${c.anchor_provider_id}`} className="hover:underline">{c.anchor_provider_id}</Link></td><td>{c.specialty}</td>
                    <td><BandBadge band={c.review_priority} /></td><td><div className="flex items-center gap-2"><Bar value={c.priority_score} color="#38bdf8" /><span className="tabular-nums">{c.priority_score.toFixed(2)}</span></div></td>
                    <td className="tabular-nums">{money(c.potential_exposure)}</td><td className="tabular-nums">{c.member_count}</td>
                    <td className="tabular-nums" title={c.forecast_label}>{[c.forecast_30d, c.forecast_60d, c.forecast_90d].map((v: number) => v?.toFixed(2)).join(" / ")}</td>
                    <td className="max-w-[200px] text-muted-foreground">{c.top_drivers.join(", ").replaceAll("_", " ")}</td><td><Badge>{c.review_status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="mt-2 text-[11px] text-muted-foreground">{data.policy_note} Queue entries are investigation leads requiring human review.</p>
        </>
      )}
    </Page>
  );
}
