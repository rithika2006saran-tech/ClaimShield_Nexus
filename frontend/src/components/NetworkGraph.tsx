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
export default function NetworkGraph({ nodes, edges, center, onSelect, height = "100%" }: { nodes: GNode[]; edges: GEdge[]; center?: string[]; onSelect?: (kind: "node" | "edge", data: any) => void; height?: number | string }) {
  const ref = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    
    // Destroy previous instance if it exists
    if (cy.current) {
      cy.current.destroy();
    }

    const inst = cytoscape({
      container: ref.current,
      elements: [
        ...nodes.map((n) => ({ 
          data: { 
            ...n, 
            color: n.type === "facility" ? "#334155" : riskColor(n.risk), 
            size: n.type === "facility" ? 28 : 20 + Math.min(24, (n.risk ?? 0) * 20), 
            isCenter: center?.includes(n.id) ? 1 : 0 
          } 
        })),
        ...edges.map((e) => ({ 
          data: { 
            ...e, 
            w: Math.max(1, Math.min(4, Math.log1p(e.weight) * 0.7)), 
            ec: EDGE_COLOR[e.type] ?? "#475569", 
            hasEv: e.evidence_ids?.length ? 1 : 0 
          } 
        })),
      ],
      style: [
        // Base Node Style
        { 
          selector: "node", 
          style: { 
            "background-color": "data(color)", 
            label: "data(display)", 
            color: "#e2e8f0", 
            "font-size": 10, 
            "font-family": "monospace",
            "text-valign": "bottom", 
            "text-margin-y": 4, 
            width: "data(size)", 
            height: "data(size)", 
            "border-width": 1.5, 
            "border-color": "#0f172a", 
            "text-outline-width": 2.5, 
            "text-outline-color": "#0f172a",
            "min-zoomed-font-size": 6
          } 
        },
        // Facility Node
        { selector: "node[type = 'facility']", style: { shape: "round-rectangle", "background-color": "#1e293b", "border-color": "#64748b" } },
        // In-Case Node
        { selector: "node[?in_case]", style: { "border-width": 3, "border-color": "#38bdf8" } },
        // Center Node
        { selector: "node[isCenter = 1]", style: { "border-width": 4, "border-color": "#f8fafc", width: 36, height: 36, "font-size": 12, "z-index": 100 } },
        // Base Edge Style
        { selector: "edge", style: { width: "data(w)", "line-color": "data(ec)", opacity: 0.4, "curve-style": "bezier", "target-arrow-shape": "none", "arrow-scale": 0.8 } },
        // Directed Referral
        { selector: "edge[type = 'referred_to']", style: { "target-arrow-shape": "triangle", "target-arrow-color": "data(ec)" } },
        // Undirected works_at
        { selector: "edge[type = 'works_at']", style: { "line-style": "dashed", opacity: 0.3 } },
        // Evidence Highlight
        { selector: "edge[hasEv = 1]", style: { opacity: 0.8 } },
        
        // Interactive States
        { selector: "node.dimmed", style: { opacity: 0.2, "text-opacity": 0 } },
        { selector: "edge.dimmed", style: { opacity: 0.05 } },
        { selector: "node.highlighted", style: { "border-width": 3, "border-color": "#fff", "z-index": 99 } },
        { selector: "edge.highlighted", style: { opacity: 1, width: "calc(data(w) + 1)", "z-index": 98 } },
        { selector: ":selected", style: { "overlay-color": "#38bdf8", "overlay-opacity": 0.2, "overlay-padding": 5 } },
      ],
      layout: { 
        name: "fcose", 
        animate: false, 
        randomize: true, // Still use randomize to avoid starting nodes at exact same coordinates
        quality: "proof", // Better layout quality
        nodeRepulsion: 12000, 
        idealEdgeLength: 80, 
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        padding: 40,
        nodeSeparation: 80,
        piTol: 0.0000001,
      } as any,
      wheelSensitivity: 0.2,
      minZoom: 0.1,
      maxZoom: 3,
    });

    // Handle Selection & Dimming
    inst.on("tap", (ev) => {
      if (ev.target === inst) {
        // Clicked background: reset
        inst.elements().removeClass("dimmed highlighted");
        onSelect?.("node", null);
      }
    });

    inst.on("tap", "node", (ev) => {
      const node = ev.target;
      onSelect?.("node", node.data());
      
      // Dim logic
      inst.elements().removeClass("dimmed highlighted");
      inst.elements().addClass("dimmed");
      
      node.removeClass("dimmed").addClass("highlighted");
      node.connectedEdges().removeClass("dimmed").addClass("highlighted");
      node.connectedEdges().connectedNodes().removeClass("dimmed").addClass("highlighted");
    });

    inst.on("tap", "edge", (ev) => {
      const edge = ev.target;
      onSelect?.("edge", edge.data());
      
      inst.elements().removeClass("dimmed highlighted");
      inst.elements().addClass("dimmed");
      
      edge.removeClass("dimmed").addClass("highlighted");
      edge.connectedNodes().removeClass("dimmed").addClass("highlighted");
    });

    cy.current = inst;
    
    // Handle resizing gracefully
    const resizeObserver = new ResizeObserver(() => {
      if (cy.current) {
        cy.current.resize();
        // Do not re-layout on simple resize to maintain spatial memory,
        // just fit to the new bounding box if needed, but cytoscape usually handles it ok.
      }
    });
    resizeObserver.observe(ref.current);

    return () => { 
      resizeObserver.disconnect();
      if (cy.current) {
        cy.current.destroy(); 
        cy.current = null; 
      }
    };
  }, [nodes, edges, center]);

  return (
    <div className="relative h-full w-full">
      <div ref={ref} style={{ height }} className="w-full h-full rounded-md bg-[#0b1220]" data-testid="cytoscape-canvas" />
      <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-x-3 gap-y-1 rounded-md border border-slate-800 bg-slate-950/80 backdrop-blur-sm px-3 py-2 text-[10px] text-slate-300 shadow-lg">
        <span className="flex items-center"><i className="mr-1.5 inline-block h-2 w-2 rounded-full bg-red-500" />Risk &ge;0.8</span>
        <span className="flex items-center"><i className="mr-1.5 inline-block h-2 w-2 rounded-full bg-orange-500" />&ge;0.5</span>
        <span className="flex items-center"><i className="mr-1.5 inline-block h-2 w-2 rounded-full bg-green-500" />Low</span>
        <span className="flex items-center"><i className="mr-1.5 inline-block h-2 w-2 rounded-sm bg-slate-600" />Facility</span>
        <span className="flex items-center ml-2 border-l border-slate-700 pl-3" style={{ color: EDGE_COLOR.referred_to }}>— Referral</span>
        <span className="flex items-center" style={{ color: EDGE_COLOR.associated_with }}>— Associated</span>
        <span className="flex items-center" style={{ color: EDGE_COLOR.shared_members }}>— Shared Members</span>
      </div>
    </div>
  );
}
