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

/** Nexus Memory: Second Brain search (BM25 + kNN + structured filters + RRF), pattern memory and reviewer memory. */
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

  const run = async () => {
    setBusy(true); setErr(null);
    const filters: any = {};
    if (index === "cases" && kind) filters.kind = kind;
    if (specialty && (index === "cases" || index === "entities" || index === "review_memory")) filters.specialty = specialty;
    if (outcome && index === "cases") filters.outcome = outcome;
    try { setRes(await post("/brain/search", { query: q, index, mode, filters, size: 10 })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  useEffect(() => { run(); /* initial example search */ // eslint-disable-next-line
  }, []);
  const st = mem.data?.status;
  return (
    <Page title="Nexus Memory" subtitle="Hybrid retrieval over cases, evidence, entities, patterns and reviewer memory.">
      {mem.loading && <Loading />}{mem.error && <ErrorBox error={mem.error} />}
      {st && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-md border border-border bg-card p-3 text-xs">
          <Badge className={st.using_fallback ? "text-amber-400" : "text-green-400"}>{st.backend}</Badge>
          {st.using_fallback && <span className="text-amber-400">Elasticsearch not reachable - in-process fallback with identical BM25 + kNN + RRF semantics.</span>}
          <span className="text-muted-foreground">vectors: {st.vector_mode}</span>
          {Object.entries<number>(st.indices ?? {}).map(([k, v]) => <span key={k}><b>{k}</b> {v}</span>)}
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader><CardTitle>Search the Second Brain</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run(); }}>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Claim ID, provider, case, rule, or behaviour description" className="h-8 min-w-[240px] flex-1 rounded-md border border-input bg-background px-2 text-xs" />
              <select value={index} onChange={(e) => setIndex(e.target.value as any)} className="h-8 rounded-md border border-input bg-background px-1 text-xs">{INDICES.map((i) => <option key={i}>{i}</option>)}</select>
              <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="h-8 rounded-md border border-input bg-background px-1 text-xs">{MODES.map((i) => <option key={i}>{i}</option>)}</select>
              <select value={kind} onChange={(e) => setKind(e.target.value)} className="h-8 rounded-md border border-input bg-background px-1 text-xs"><option value="">any kind</option><option value="historical_investigation">historical investigation</option><option value="current_case">current case</option></select>
              <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="specialty filter" className="h-8 w-32 rounded-md border border-input bg-background px-2 text-xs" />
              <input value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="outcome filter" className="h-8 w-36 rounded-md border border-input bg-background px-2 text-xs" />
              <Button size="sm" type="submit" disabled={busy}><Search className="h-3.5 w-3.5" /> Search</Button>
            </form>
            {err && <ErrorBox error={err} />}
            {res && (
              <div className="space-y-2">
                <div className="text-[11px] text-muted-foreground">{res.hits.length} hits - backend {res.backend} - mode {res.mode} - fused by RRF (k=60) when hybrid</div>
                {res.hits.map((h: any) => (
                  <div key={h.id} className="rounded border border-border p-2 text-xs">
                    <div className="flex flex-wrap items-center gap-2">
                      {h.index === "cases" ? <Link to={h.doc.kind === "current_case" ? `/case/${h.id}` : "/memory"} className="font-mono font-semibold text-sky-400">{h.id}</Link> : <Mono className="font-semibold text-sky-400">{h.id}</Mono>}
                      <Badge>{h.index}</Badge>{h.doc.kind && <Badge>{h.doc.kind.replace("_", " ")}</Badge>}{h.doc.outcome && <Badge>{h.doc.outcome}</Badge>}{h.doc.specialty && <span className="text-muted-foreground">{h.doc.specialty}</span>}
                      <span className="ml-auto text-muted-foreground">RRF {h.score.toFixed(4)} - BM25 #{h.bm25_rank ?? "-"} - kNN #{h.knn_rank ?? "-"}</span></div>
                    <div className="mt-1 text-muted-foreground">{(h.doc.summary || h.doc.text || h.doc.profile || h.doc.description || h.doc.rationale || "").slice(0, 300)}</div>
                  </div>))}
              </div>
            )}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card><CardHeader><CardTitle>Pattern memory</CardTitle></CardHeader><CardContent className="space-y-2 text-xs">
            {mem.data?.patterns.map((p: any) => <div key={p.pattern_id}><b className="font-mono">{p.pattern_id}</b> <span className="text-muted-foreground">support {p.support} past investigations{p.typical_outcomes?.length ? `; typical: ${p.typical_outcomes.join(", ")}` : ""}</span></div>)}</CardContent></Card>
          <Card><CardHeader><CardTitle>Historical outcomes</CardTitle></CardHeader><CardContent className="space-y-1 text-xs">
            {mem.data?.historical_outcomes.map((o: any) => <div key={o.outcome} className="flex justify-between"><span>{o.outcome}</span><span className="tabular-nums">{o.n} - {money(o.amount)}</span></div>)}</CardContent></Card>
          <Card><CardHeader><CardTitle>Reviewer memory</CardTitle></CardHeader><CardContent className="space-y-2 text-xs">
            {mem.data?.reviewer_memory.length ? mem.data.reviewer_memory.map((r: any) => <div key={r.review_id} className="rounded border border-border p-2"><b>{r.decision}</b> on <Link className="font-mono text-sky-400" to={`/case/${r.case_id}`}>{r.case_id}</Link> by {r.reviewer}<div className="text-muted-foreground">{r.rationale}</div></div>) : <span className="text-muted-foreground">No human decisions recorded yet. Decisions made in the Investigation Workspace appear here and are retrievable for similar future cases.</span>}</CardContent></Card>
        </div>
      </div>
    </Page>
  );
}
