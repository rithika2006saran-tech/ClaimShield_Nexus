import { Fragment, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Mono } from "@/components/common";

const SEV: Record<string, string> = { CRITICAL: "text-red-400", HIGH: "text-orange-400", MEDIUM: "text-yellow-400", LOW: "text-green-400" };
const TYPES = ["", "RULE", "PEER", "MODEL", "ANOMALY", "SHAP", "NETWORK", "TEMPORAL", "FORECAST"];

/** Evidence ledger: canonical evidence objects (the same ones used by the Brief and the Copilot). */
export default function EvidenceTable({ caseId, focus }: { caseId: string; focus?: string | null }) {
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const [limit, setLimit] = useState(40);

  useEffect(() => {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (type) qs.set("type", type);
    const query = focus || q;
    if (query) qs.set("q", query);
    api(`/cases/${caseId}/evidence?${qs}`).then((r) => { setRows(r.items); setTotal(r.total); if (focus && r.items[0]) setOpen(r.items[0].evidence_id); });
  }, [caseId, type, q, focus, limit]);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <select value={type} onChange={(e) => setType(e.target.value)} className="h-7 rounded-md border border-input bg-background px-1 text-xs">{TYPES.map((t) => <option key={t} value={t}>{t || "All types"}</option>)}</select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search claim ID / text" className="h-7 w-44 rounded-md border border-input bg-background px-2 text-xs" />
        <span className="text-[11px] text-muted-foreground">{rows.length} of {total} evidence objects</span>
      </div>
      <div className="max-h-80 overflow-auto rounded-md border border-border">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-muted text-left text-muted-foreground"><tr><th className="p-1.5">ID</th><th>Type</th><th>Rule / feature</th><th>Sev</th><th>Observed</th><th>Expected</th><th>Provider</th><th>Date</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r.evidence_id}>
                <tr onClick={() => setOpen(open === r.evidence_id ? null : r.evidence_id)} className="cursor-pointer border-t border-border hover:bg-accent">
                  <td className="p-1.5"><Mono className="text-sky-400">{r.evidence_id}</Mono></td><td><Badge>{r.evidence_type}</Badge></td>
                  <td className="max-w-[170px] truncate" title={r.rule_id ?? r.feature}>{r.rule_id ?? r.feature}</td><td className={SEV[r.severity]}>{r.severity ?? "-"}</td>
                  <td className="tabular-nums">{r.observed_value != null ? Number(r.observed_value).toFixed(2) : "-"}</td><td className="tabular-nums">{r.expected_value != null ? Number(r.expected_value).toFixed(2) : "-"}</td>
                  <td>{r.provider_id}</td><td>{r.event_ts?.slice(0, 10)}</td>
                </tr>
                {open === r.evidence_id && (
                  <tr className="bg-muted/40"><td colSpan={8} className="space-y-1 p-2 text-[11px]">
                    <div>{r.explanation}</div>
                    <div className="text-muted-foreground">source: <Mono>{r.source_table}#{r.source_row_id}</Mono> - feature <Mono>{r.feature}</Mono> {r.rule_version && <>- <Mono>{r.rule_version}</Mono></>} {r.model_version && <>- <Mono>{r.model_version}</Mono></>}</div>
                    {r.claim_ids?.length > 0 && <div className="text-muted-foreground">claims: <Mono>{r.claim_ids.join(", ")}</Mono></div>}
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length < total && <button className="mt-1 text-[11px] text-sky-400 hover:underline" onClick={() => setLimit(limit + 80)}>Load more</button>}
    </div>
  );
}
