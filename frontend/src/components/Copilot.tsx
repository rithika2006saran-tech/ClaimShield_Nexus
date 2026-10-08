import { useRef, useState } from "react";
import { Send, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { post } from "@/lib/api";
import { Mono } from "@/components/common";

const SUGGESTED = ["Why was this case prioritized?", "What evidence supports the investigation lead?", "Which claims are relevant?", "What changed over time?", "Which providers and facilities are connected?",
  "Are there similar historical cases?", "What evidence is missing?", "What should the investigator review next?"];

interface Msg { role: "user" | "copilot"; text: string; meta?: any }

/** Nexus Copilot: evidence-grounded answers with citations. Not a fraud detector; it only explains retrieved case evidence. */
export default function Copilot({ caseId, onCite }: { caseId: string; onCite?: (evidenceId: string) => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ(""); setBusy(true);
    try {
      const r = await post(`/cases/${caseId}/copilot`, { question });
      setMsgs((m) => [...m, { role: "copilot", text: r.answer, meta: r }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "copilot", text: `Request failed: ${e.message}` }]);
    } finally { setBusy(false); setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth" }), 50); }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {msgs.length === 0 && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Ask about this case. Answers use only the case evidence, model outputs, network findings and retrieved similar cases.</p>
            {SUGGESTED.map((s) => <button key={s} onClick={() => ask(s)} className="block w-full rounded border border-border px-2 py-1.5 text-left text-xs hover:bg-accent">{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "ml-6 rounded-md bg-primary/15 px-3 py-2 text-xs" : "rounded-md border border-border bg-muted/40 px-3 py-2 text-xs"}>
            {m.role === "copilot" && m.meta?.insufficient && <div className="mb-1 flex items-center gap-1 text-amber-400"><ShieldAlert className="h-3.5 w-3.5" /> Insufficient evidence</div>}
            <Rendered text={m.text} onCite={onCite} />
            {m.meta && (
              <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-border pt-1.5">
                <Badge>{m.meta.mode}</Badge>{m.meta.intent && <Badge>intent: {m.meta.intent}</Badge>}
                {m.meta.note && <span className="text-[10px] text-amber-400">{m.meta.note}</span>}
                {(m.meta.citations ?? []).slice(0, 8).map((c: any) => <button key={c.evidence_id} title={c.explanation} onClick={() => onCite?.(c.evidence_id)} className="rounded border border-sky-500/40 px-1 text-[10px] text-sky-400 hover:bg-sky-500/10"><Mono>{c.evidence_id}</Mono></button>)}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="text-xs text-muted-foreground">Retrieving evidence...</div>}
        <div ref={end} />
      </div>
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about claim IDs, rules, timeline..." className="h-8 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-ring" />
        <Button size="sm" type="submit" disabled={busy}><Send className="h-3.5 w-3.5" /></Button>
      </form>
      <p className="mt-1.5 text-[10px] text-muted-foreground">Decision support only. The Copilot never denies claims or concludes misconduct; human SIU review is required.</p>
    </div>
  );
}

function Rendered({ text, onCite }: { text: string; onCite?: (id: string) => void }) {
  return (
    <div className="space-y-1">
      {text.split("\n").filter(Boolean).map((line, i) => (
        <div key={i} className="leading-relaxed">
          {line.replace(/^- /, "").split(/(\[EV-\d{6}\]|\*\*.*?\*\*)/g).map((p, j) => /^\[EV-\d{6}\]$/.test(p)
            ? <button key={j} onClick={() => onCite?.(p.slice(1, -1))} className="mx-0.5 text-sky-400 hover:underline"><Mono>{p}</Mono></button> 
            : /^\*\*.*?\*\*$/.test(p) ? <strong key={j} className="text-slate-200">{p.slice(2, -2)}</strong> 
            : <span key={j}>{p}</span>)}
        </div>
      ))}
    </div>
  );
}
