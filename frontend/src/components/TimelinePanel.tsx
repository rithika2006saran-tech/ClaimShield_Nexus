import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Mono } from "@/components/common";

const SERIES = [
  { key: "claims_30d", label: "Claims (30d)", color: "#38bdf8" },
  { key: "dup_claims_30d", label: "Duplicate claims (30d)", color: "#ef4444" },
  { key: "ref_in_top_share_90d", label: "Top referrer share (90d)", color: "#c084fc" },
  { key: "connections_cum", label: "Connections (cumulative)", color: "#2dd4bf" },
];

/** "What changed?" - rolling 7/30/90-day behaviour with detected phase onsets. */
export default function TimelinePanel({ timeline, series: s0, height = 190 }: { timeline: any; series?: string; height?: number }) {
  const key = s0 ?? "claims_30d";
  const cfg = SERIES.find((x) => x.key === key) ?? SERIES[0];
  const data = (timeline.series ?? []).map((r: any) => ({ ...r, d: r.week_end }));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <Badge>{timeline.current_phase ?? "-"}</Badge>
        <span className="text-muted-foreground">escalation indicators: <b className="text-foreground">{timeline.active_indicators ?? 0}</b> &middot; escalation score <b className="text-foreground">{timeline.escalation_score ?? "-"}</b></span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ left: -18, right: 8, top: 4 }}>
          <defs><linearGradient id={`g-${key}`} x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={cfg.color} stopOpacity={0.5} /><stop offset="95%" stopColor={cfg.color} stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid stroke="#1e293b" vertical={false} />
          <XAxis dataKey="d" tick={{ fontSize: 9, fill: "#94a3b8" }} minTickGap={40} tickFormatter={(v) => String(v).slice(2, 7)} />
          <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 11 }} />
          <Area type="monotone" dataKey={key} name={cfg.label} stroke={cfg.color} fill={`url(#g-${key})`} strokeWidth={1.5} />
          {(timeline.events ?? []).filter((e: any) => e.indicator !== "HIGH_PRIORITY_INVESTIGATION").map((e: any, i: number) => <ReferenceLine key={i} x={nearest(data, e.date)} stroke="#f97316" strokeDasharray="3 3" />)}
        </AreaChart>
      </ResponsiveContainer>
      <ol className="mt-2 space-y-1.5 border-l border-border pl-3">
        {(timeline.events ?? []).map((e: any, i: number) => (
          <li key={i} className="relative text-xs"><span className="absolute -left-[17px] top-1 h-2 w-2 rounded-full bg-orange-400" />
            <span className="font-semibold">{e.phase}</span> <Mono className="text-muted-foreground">{e.date}</Mono>{e.evidence_id && <Mono className="ml-1 text-sky-400">{e.evidence_id}</Mono>}
            <div className="text-muted-foreground">{e.description}</div></li>
        ))}
      </ol>
    </div>
  );
}
function nearest(data: any[], date: string) {
  const hit = data.find((r) => r.d >= date);
  return (hit ?? data[data.length - 1])?.d;
}
export { SERIES };
