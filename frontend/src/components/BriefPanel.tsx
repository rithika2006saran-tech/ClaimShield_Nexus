import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/useApi";
import { Loading, ErrorBox, Mono } from "@/components/common";

/** Investigation Brief: 12 sections; every factual statement carries the evidence IDs that support it (validated server-side). */
export default function BriefPanel({ caseId, onCite }: { caseId: string; onCite?: (id: string) => void }) {
  const { data, error, loading } = useApi<any>(`/cases/${caseId}/brief`, [caseId]);
  const [open, setOpen] = useState<string | null>("executive_summary");
  if (loading) return <Loading label="Generating brief" />;
  if (error || !data) return <ErrorBox error={error ?? "no brief"} />;
  const download = async () => {
    const r = await fetch(`/api/cases/${caseId}/brief?format=markdown`).then((x) => x.json());
    const url = URL.createObjectURL(new Blob([r.markdown], { type: "text/markdown" }));
    const a = document.createElement("a"); a.href = url; a.download = `${caseId}_investigation_brief.md`; a.click(); URL.revokeObjectURL(url);
  };
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground"><Badge>{data.generator}</Badge><Badge className="text-green-400">citations validated</Badge></div>
        <Button size="sm" variant="outline" onClick={download}><Download className="h-3.5 w-3.5" /> Markdown</Button>
      </div>
      <div className="divide-y divide-border rounded-md border border-border">
        {data.sections.map((s: any, i: number) => (
          <div key={s.key}>
            <button onClick={() => setOpen(open === s.key ? null : s.key)} className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold hover:bg-accent">
              <span><span className="mr-2 text-muted-foreground">{i + 1}.</span>{s.title}</span><span className="text-muted-foreground">{open === s.key ? "-" : "+"}</span>
            </button>
            {open === s.key && (
              <ul className="space-y-1.5 px-4 pb-3 text-xs">
                {s.items.map((it: any, j: number) => (
                  <li key={j} className="list-disc leading-relaxed text-muted-foreground"><span className="text-foreground/90">{it.text}</span>
                    {it.evidence_ids.map((id: string) => <button key={id} onClick={() => onCite?.(id)} className="ml-1 text-sky-400 hover:underline"><Mono>{id}</Mono></button>)}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
