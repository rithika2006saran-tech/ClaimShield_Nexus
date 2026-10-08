import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { post } from "@/lib/api";

const OPTS = [
  { v: "ESCALATE", label: "Escalate", cls: "bg-red-600 hover:bg-red-600/90 text-white" },
  { v: "REQUEST_DOCUMENTATION", label: "Request Documentation", cls: "bg-orange-500 hover:bg-orange-500/90 text-white" },
  { v: "MONITOR", label: "Monitor", cls: "bg-sky-600 hover:bg-sky-600/90 text-white" },
  { v: "CLOSE", label: "Close", cls: "bg-slate-600 hover:bg-slate-600/90 text-white" },
] as const;

/** Mandatory human decision. Stored in PostgreSQL and written to reviewer memory in the Second Brain. */
export default function DecisionPanel({ caseId, status, reviews, onDone }: { caseId: string; status: string; reviews: any[]; onDone: () => void }) {
  const [decision, setDecision] = useState<string>("");
  const [why, setWhy] = useState("");
  const [who, setWho] = useState("siu.reviewer");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await post(`/cases/${caseId}/review`, { decision, rationale: why, reviewer: who });
      setMsg(`Recorded: ${r.review.decision} -> status ${r.case_status}. Added to reviewer memory (${r.reviewer_memory.backend}).`);
      setWhy(""); setDecision(""); onDone();
    } catch (e: any) { setMsg(`Failed: ${e.message}`); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">Case status: <Badge>{status}</Badge></div>
      <div className="flex flex-wrap gap-1.5">{OPTS.map((o) => <Button key={o.v} size="sm" variant="outline" onClick={() => setDecision(o.v)} className={decision === o.v ? o.cls : ""}>{o.label}</Button>)}</div>
      <textarea value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Rationale (required) - stored as reviewer memory" rows={3} className="w-full rounded-md border border-input bg-background p-2 text-xs outline-none focus:ring-1 focus:ring-ring" />
      <div className="flex items-center gap-2">
        <input value={who} onChange={(e) => setWho(e.target.value)} className="h-8 w-40 rounded-md border border-input bg-background px-2 text-xs" aria-label="reviewer" />
        <Button size="sm" disabled={!decision || why.trim().length < 3 || busy} onClick={submit}>Submit human decision</Button>
      </div>
      {msg && <div className="flex items-start gap-1 text-green-400"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5" /> {msg}</div>}
      {reviews?.length > 0 && (
        <div className="border-t border-border pt-2">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Decision history</div>
          {reviews.slice().reverse().map((r) => <div key={r.review_id} className="mb-1 text-muted-foreground"><b className="text-foreground">{r.decision}</b> by {r.reviewer} - {r.rationale}</div>)}
        </div>
      )}
      <p className="text-[10px] text-muted-foreground">The system never auto-denies claims, suspends providers or makes legal conclusions. Only a human decision changes case status.</p>
    </div>
  );
}
