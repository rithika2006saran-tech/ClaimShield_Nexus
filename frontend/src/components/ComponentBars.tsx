import { Bar } from "@/components/common";

const LABEL: Record<string, string> = { model_risk: "FWA model risk", rule_evidence: "Rule evidence", peer_deviation: "Peer deviation", network: "Network severity", temporal: "Temporal escalation",
  anomaly: "Anomaly score", evidence_strength: "Evidence strength", exposure: "Potential exposure", member_impact: "Member impact" };

/** Risk decomposition: every bar is a real component of the priority score with its policy weight. */
export default function ComponentBars({ components, weights }: { components: Record<string, number>; weights: Record<string, number> }) {
  const rows = Object.keys(weights).map((k) => ({ k, v: components[k] ?? 0, w: weights[k] })).sort((a, b) => b.v * b.w - a.v * a.w);
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.k}>
          <div className="mb-0.5 flex justify-between text-[11px]"><span>{LABEL[r.k] ?? r.k}</span><span className="tabular-nums text-muted-foreground">{r.v.toFixed(2)} x {r.w.toFixed(2)} = <b className="text-foreground">{(r.v * r.w).toFixed(3)}</b></span></div>
          <Bar value={r.v} />
        </div>
      ))}
    </div>
  );
}
