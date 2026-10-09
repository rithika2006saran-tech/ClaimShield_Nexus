import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBox, Loading, Mono, Page } from "@/components/common";
import { useApi } from "@/lib/useApi";
import { post } from "@/lib/api";
import { money } from "@/lib/utils";

const INDICES = ["cases", "evidence", "entities", "patterns", "review_memory"] as const;
const MODES = ["hybrid", "bm25", "knn"] as const;

export default function Memory() {
  const mem = useApi<any>("/brain/memory");
  const [q, setQ] = useState("referral concentration shared facility duplicate billing");
  const [index, setIndex] = useState<(typeof INDICES)[number]>("cases");
  const [mode, setMode] = useState<(typeof MODES)[number]>("hybrid");
  const [kind, setKind] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [outcome, setOutcome] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const run = async (currentOffset = offset) => {
    setBusy(true); setErr(null);
    const filters: any = {};
    if (index === "cases" && kind) filters.kind = kind;
    if (specialty && (index === "cases" || index === "entities" || index === "review_memory")) filters.specialty = specialty;
    if (outcome && index === "cases") filters.outcome = outcome;
    try { setRes(await post("/brain/search", { query: q, index, mode, filters, size: 10, offset: currentOffset })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  useEffect(() => { run(0); /* initial example search */ // eslint-disable-next-line
  }, []);
  const st = mem.data?.status;
  return (
    <Page title="Nexus Memory" subtitle="Hybrid retrieval over cases, evidence, entities, patterns and reviewer memory.">
      {mem.loading && <Loading label="Loading Memory" />}
      {mem.error && <ErrorBox error={mem.error} />}
      
      {st && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-border bg-card p-3 text-[11px] uppercase tracking-wider text-muted-foreground shadow-sm">
          <span><b>Documents</b>: {st.document_count}</span>
          <span className="h-3 w-px bg-border"></span>
          <span><b>Cases</b>: {st.index_counts?.cases ?? 0}</span>
          <span><b>Entities</b>: {st.index_counts?.entities ?? 0}</span>
          <span><b>Evidence</b>: {st.index_counts?.evidence ?? 0}</span>
          <span><b>Patterns</b>: {st.index_counts?.patterns ?? 0}</span>
        </div>
      )}
      
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card className="flex flex-col">
          <CardHeader className="py-3"><CardTitle>Search Second Brain</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form className="flex flex-wrap gap-2 items-center" onSubmit={(e) => { e.preventDefault(); setOffset(0); run(0); }}>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Claim ID, provider, case, rule, or behaviour description" className="h-8 min-w-[240px] flex-1 rounded-md border border-input bg-background px-2 text-[12px]" />
              <select value={index} onChange={(e) => setIndex(e.target.value as any)} className="h-8 w-24 rounded-md border border-input bg-background px-1 text-[11px] uppercase tracking-wider">{INDICES.map((i) => <option key={i}>{i}</option>)}</select>
              <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="h-8 w-20 rounded-md border border-input bg-background px-1 text-[11px] uppercase tracking-wider">{MODES.map((i) => <option key={i}>{i}</option>)}</select>
              <select value={kind} onChange={(e) => setKind(e.target.value)} className="h-8 w-28 rounded-md border border-input bg-background px-1 text-[11px] uppercase tracking-wider"><option value="">any kind</option><option value="historical_investigation">historical investigation</option><option value="current_case">current case</option></select>
              <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="specialty" className="h-8 w-28 rounded-md border border-input bg-background px-2 text-[12px]" />
              <input value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="outcome" className="h-8 w-28 rounded-md border border-input bg-background px-2 text-[12px]" />
              <Button size="sm" type="submit" disabled={busy} className="h-8 text-[11px] uppercase tracking-wider"><Search className="h-3 w-3 mr-1" /> Search</Button>
            </form>
            
            {err && <ErrorBox error={err} />}
            
            {res && (
              <div className="space-y-3">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground pb-1 border-b border-border/50 flex justify-between">
                  <span>{res.hits.length} hits • backend {res.backend} • mode {res.mode} • fused by RRF (k=60)</span>
                  <span>offset {res.offset}</span>
                </div>
                {res.hits.map((h: any) => (
                  <div key={h.id} className="rounded border border-border p-3 text-[12px] hover:bg-accent/30 transition-colors">
                    <div className="flex flex-wrap items-center gap-2 mb-1.5">
                      {h.index === "cases" ? <Link to={h.doc.kind === "current_case" ? `/case/${h.id}` : "/memory"} className="font-mono font-medium text-primary hover:underline">{h.id}</Link> : <Mono className="font-medium text-primary">{h.id}</Mono>}
                      <Badge variant="outline" className="text-[9px] bg-transparent">{h.index}</Badge>
                      {h.doc.kind && <Badge variant="outline" className="text-[9px] bg-transparent">{h.doc.kind.replace("_", " ")}</Badge>}
                      {h.doc.outcome && <Badge variant="secondary" className="text-[9px]">{h.doc.outcome}</Badge>}
                      {h.doc.specialty && <span className="text-[10px] uppercase tracking-wider text-muted-foreground ml-1">{h.doc.specialty}</span>}
                      
                      <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                        RRF {h.score.toFixed(4)} <span className="mx-1">•</span> BM25 #{h.bm25_rank ?? "-"} <span className="mx-1">•</span> kNN #{h.knn_rank ?? "-"}
                      </span>
                    </div>
                    <div className="text-muted-foreground leading-relaxed">{(h.doc.summary || h.doc.text || h.doc.profile || h.doc.description || h.doc.rationale || "").slice(0, 350)}...</div>
                  </div>
                ))}
                
                <div className="mt-4 flex gap-2 justify-end">
                  <Button size="sm" variant="outline" className="h-8 text-[11px] uppercase tracking-wider" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - 10)); run(Math.max(0, offset - 10)); }}>Previous</Button>
                  <Button size="sm" variant="outline" className="h-8 text-[11px] uppercase tracking-wider" disabled={res.hits.length < 10} onClick={() => { setOffset(offset + 10); run(offset + 10); }}>Next</Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        
        <div className="space-y-4 flex flex-col">
          <Card>
            <CardHeader className="py-3"><CardTitle>Pattern Memory</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-[12px] pb-4">
              {mem.data?.patterns.map((p: any) => <div key={p.pattern_id} className="flex flex-col gap-0.5"><b className="font-mono text-foreground">{p.pattern_id}</b> <span className="text-muted-foreground text-[11px] leading-snug">support {p.support} past investigations{p.typical_outcomes?.length ? `; typical: ${p.typical_outcomes.join(", ")}` : ""}</span></div>)}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="py-3"><CardTitle>Historical Outcomes</CardTitle></CardHeader>
            <CardContent className="space-y-1.5 text-[12px] pb-4">
              {mem.data?.historical_outcomes.map((o: any) => <div key={o.outcome} className="flex justify-between items-center"><span className="text-muted-foreground">{o.outcome}</span><span className="tabular-nums font-medium text-foreground">{o.n} <span className="text-muted-foreground mx-1">•</span> {money(o.amount)}</span></div>)}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="py-3"><CardTitle>Reviewer Memory</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-[12px] pb-4">
              {mem.data?.reviewer_memory.length ? mem.data.reviewer_memory.map((r: any) => (
                <div key={r.review_id} className="rounded border border-border p-2.5 bg-muted/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={r.decision === "APPROVE" ? "default" : "secondary"} className="text-[9px]">{r.decision}</Badge>
                    <span className="text-[11px] text-muted-foreground">on <Link className="font-mono text-primary hover:underline mx-1" to={`/case/${r.case_id}`}>{r.case_id}</Link> by {r.reviewer}</span>
                  </div>
                  <div className="text-muted-foreground leading-snug italic">"{r.rationale}"</div>
                </div>
              )) : <span className="text-muted-foreground italic">No human decisions recorded yet. Decisions made in the Investigation Workspace appear here.</span>}
            </CardContent>
          </Card>
        </div>
      </div>
    </Page>
  );
}
