import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
// @ts-ignore - no bundled types
import fcose from "cytoscape-fcose";

cytoscape.use(fcose);

const riskColor = (r?: number | null) => (r == null ? "#64748b" : r >= 0.8 ? "#ef4444" : r >= 0.5 ? "#f97316" : r >= 0.25 ? "#eab308" : "#22c55e");
const EDGE_COLOR: Record<string, string> = { referred_to: "#38bdf8", works_at: "#475569", associated_with: "#c084fc", shared_members: "#2dd4bf" };

export interface GNode { id: string; type: string; label: string; display?: string; risk?: number | null; in_case?: boolean; specialty?: string; evidence_ids?: string[]; [k: string]: any }
export interface GEdge { id: string; source: string; target: string; type: string; weight: number; label: string; evidence_ids?: string[] }

/** Cytoscape.js investigation graph: selected entity -> 1-hop (optional 2-hop). Relationships are leads, not proof. */
export default function NetworkGraph({ nodes, edges, center, onSelect, height = 420 }: { nodes: GNode[]; edges: GEdge[]; center?: string[]; onSelect?: (kind: "node" | "edge", data: any) => void; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const inst = cytoscape({
      container: ref.current,
      elements: [
        ...nodes.map((n) => ({ data: { ...n, color: n.type === "facility" ? "#334155" : riskColor(n.risk), size: n.type === "facility" ? 22 : 18 + Math.min(18, (n.risk ?? 0) * 20), isCenter: center?.includes(n.id) ? 1 : 0 } })),
        ...edges.map((e) => ({ data: { ...e, w: 1 + Math.min(5, Math.log1p(e.weight)), ec: EDGE_COLOR[e.type] ?? "#475569", hasEv: e.evidence_ids?.length ? 1 : 0 } })),
      ],
      style: [
        { selector: "node", style: { "background-color": "data(color)", label: "data(display)", color: "#cbd5e1", "font-size": 9, "text-valign": "bottom", "text-margin-y": 3, width: "data(size)", height: "data(size)", "border-width": 1, "border-color": "#0f172a", "text-outline-width": 2, "text-outline-color": "#0b1220" } },
        { selector: "node[type = 'facility']", style: { shape: "round-rectangle", "background-color": "#334155", "border-color": "#64748b" } },
        { selector: "node[?in_case]", style: { "border-width": 3, "border-color": "#38bdf8" } },
        { selector: "node[isCenter = 1]", style: { "border-width": 4, "border-color": "#f8fafc" } },
        { selector: "edge", style: { width: "data(w)", "line-color": "data(ec)", opacity: 0.65, "curve-style": "bezier", "target-arrow-shape": "none" } },
        { selector: "edge[type = 'referred_to']", style: { "target-arrow-shape": "triangle", "target-arrow-color": "data(ec)" } },
        { selector: "edge[type = 'works_at']", style: { "line-style": "dashed" } },
        { selector: "edge[hasEv = 1]", style: { opacity: 1 } },
        { selector: ":selected", style: { "overlay-color": "#38bdf8", "overlay-opacity": 0.25, "overlay-padding": 6 } },
      ],
      layout: { name: "fcose", animate: false, randomize: true, nodeRepulsion: 9000, idealEdgeLength: 70, quality: "default" } as any,
      wheelSensitivity: 0.25,
    });
    inst.on("tap", "node", (ev) => onSelect?.("node", ev.target.data()));
    inst.on("tap", "edge", (ev) => onSelect?.("edge", ev.target.data()));
    cy.current = inst;
    return () => { inst.destroy(); cy.current = null; };
  }, [nodes.length, edges.length, center?.join()]);

  return (
    <div className="relative">
      <div ref={ref} style={{ height }} className="w-full rounded-md bg-[#0b1220]" data-testid="cytoscape-canvas" />
      <div className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap gap-x-3 gap-y-1 rounded bg-black/50 px-2 py-1 text-[10px] text-slate-300">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />risk &ge;0.8</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-orange-500" />&ge;0.5</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-green-500" />low</span><span><i className="mr-1 inline-block h-2 w-2 rounded-sm bg-slate-600" />facility</span>
        <span style={{ color: EDGE_COLOR.referred_to }}>— referral</span><span style={{ color: EDGE_COLOR.associated_with }}>— associated</span><span style={{ color: EDGE_COLOR.shared_members }}>— shared members</span>
      </div>
    </div>
  );
}
