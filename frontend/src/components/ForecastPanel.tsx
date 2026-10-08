import { Bar as RBar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";

/** 30/60/90 forward risk. Labelled "probability" only when the calibration test on a later chronological period passed; otherwise "escalation index". */
export default function ForecastPanel({ forecast, calibration }: { forecast: { label: string; d30: number; d60: number; d90: number; provider_id?: string }; calibration?: any }) {
  const isProb = forecast.label === "probability";
  const data = [{ h: "30-day", v: forecast.d30 }, { h: "60-day", v: forecast.d60 }, { h: "90-day", v: forecast.d90 }];
  return (
    <div>
      <div className="mb-1 flex items-center gap-2 text-xs"><Badge className={isProb ? "text-green-400" : "text-amber-400"}>{isProb ? "calibrated probability" : "escalation index (not calibrated)"}</Badge>
        {forecast.provider_id && <span className="text-muted-foreground">driven by {forecast.provider_id}</span>}</div>
      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 30 }}>
          <XAxis type="number" domain={[0, 1]} hide /><YAxis type="category" dataKey="h" tick={{ fontSize: 11, fill: "#94a3b8" }} width={50} />
          <RBar dataKey="v" radius={3}>{data.map((d, i) => <Cell key={i} fill={d.v >= 0.7 ? "#ef4444" : d.v >= 0.4 ? "#f97316" : "#eab308"} />)}<LabelList dataKey="v" position="right" formatter={(v: number) => v.toFixed(2)} style={{ fill: "#e2e8f0", fontSize: 11 }} /></RBar>
        </BarChart>
      </ResponsiveContainer>
      {calibration?.horizons && (
        <div className="text-[10px] leading-4 text-muted-foreground">Held-out chronological test: {Object.entries<any>(calibration.horizons).map(([h, v]) => `${h}d ECE ${v.calibrated.ece.toFixed(3)} / Brier ${v.calibrated.brier.toFixed(3)} (baseline ${v.brier_constant_baseline.toFixed(3)})`).join(" - ")}. Synthetic data.</div>
      )}
    </div>
  );
}
