import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/useApi";
import { Loading, ErrorBox, Mono } from "@/components/common";

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
    <div className="flex flex-col h-full">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold tracking-tight text-foreground">Investigation Brief</h3>
          <Badge variant="outline" className="text-[9px] uppercase tracking-wider text-muted-foreground bg-accent/30">{data.generator}</Badge>
          <Badge variant="outline" className="text-[9px] uppercase tracking-wider text-green-400 border-green-500/20 bg-green-500/10">citations validated</Badge>
        </div>
        <Button size="sm" variant="outline" onClick={download} className="h-7 text-[11px]"><Download className="mr-2 h-3 w-3" /> Markdown</Button>
      </div>
      <div className="divide-y divide-border rounded-md border border-border flex-1">
        {data.sections.map((s: any, i: number) => (
          <div key={s.key}>
            <button onClick={() => setOpen(open === s.key ? null : s.key)} className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold hover:bg-accent transition-colors">
              <span><span className="mr-2 text-muted-foreground font-mono font-normal">{i + 1}.</span>{s.title}</span><span className="text-muted-foreground text-base leading-none">{open === s.key ? "-" : "+"}</span>
            </button>
            {open === s.key && (
              <ul className="space-y-2 px-4 pb-4 pt-1 text-[13px]">
                {s.items.map((it: any, j: number) => (
                  <li key={j} className="list-disc leading-relaxed text-muted-foreground"><span className="text-foreground/90">{it.text}</span>
                    {it.evidence_ids.map((id: string) => <button key={id} onClick={() => onCite?.(id)} className="ml-1.5 text-primary hover:underline font-medium"><Mono>{id}</Mono></button>)}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
