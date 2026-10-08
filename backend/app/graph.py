"""Network intelligence (NetworkX analytics + Cytoscape-ready JSON).

Network relationships are investigation LEADS, not proof of misconduct. Graph sizes are capped.
"""
from __future__ import annotations

import threading
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd

from . import config, db
from .features import connection_events

MAX_NODES = 140


# ------------------------------------------------------------------------------------------------------------ build + analyze
def build_edges(claims: pd.DataFrame, referrals: pd.DataFrame, rels: pd.DataFrame) -> pd.DataFrame:
    rows = []
    r = referrals.groupby(["referring_provider_id", "target_provider_id"]).agg(weight=("referral_id", "size"), first_seen=("referral_date", "min"),
                                                                               last_seen=("referral_date", "max")).reset_index()
    for x in r.itertuples():
        rows.append(("provider", x.referring_provider_id, "provider", x.target_provider_id, "referred_to", float(x.weight), x.first_seen, x.last_seen, 0))
    w = claims.groupby(["provider_id", "facility_id"]).agg(n=("claim_id", "size"), last=("service_date", "max")).reset_index()
    start = rels[rels.relationship_type == "works_at"].groupby(["entity_a_id", "entity_b_id"]).start_date.min()
    for x in w.itertuples():
        fs = start.get((x.provider_id, x.facility_id), pd.NaT)
        rows.append(("provider", x.provider_id, "facility", x.facility_id, "works_at", float(x.n), fs, x.last, int(x.n)))
    for x in rels[(rels.relationship_type == "works_at")].itertuples():
        if not ((w.provider_id == x.entity_a_id) & (w.facility_id == x.entity_b_id)).any() and False:
            pass
    a = rels[rels.relationship_type == "associated_with"].copy()
    a["lo"] = a[["entity_a_id", "entity_b_id"]].min(axis=1)
    a["hi"] = a[["entity_a_id", "entity_b_id"]].max(axis=1)
    for x in a.groupby(["lo", "hi"]).start_date.min().reset_index().itertuples():
        rows.append(("provider", x.lo, "provider", x.hi, "associated_with", 1.0, x.start_date, config.AS_OF, 0))
    mp = claims[["member_id", "provider_id"]].drop_duplicates()
    pairs = mp.merge(mp, on="member_id")
    pairs = pairs[pairs.provider_id_x < pairs.provider_id_y]
    sm = pairs.groupby(["provider_id_x", "provider_id_y"]).size().reset_index(name="n")
    sm = sm[sm.n >= 4]
    for x in sm.itertuples():
        rows.append(("provider", x.provider_id_x, "provider", x.provider_id_y, "shared_members", float(x.n), pd.NaT, config.AS_OF, 0))
    df = pd.DataFrame(rows, columns=["src_type", "src_id", "dst_type", "dst_id", "edge_type", "weight", "first_seen", "last_seen", "claim_count"])
    df["edge_id"] = [f"E{i + 1:06d}" for i in range(len(df))]
    return df


def analyze(edges: pd.DataFrame, providers: pd.DataFrame) -> pd.DataFrame:
    G = nx.Graph()
    G.add_nodes_from(providers.provider_id)
    P = nx.Graph()
    P.add_nodes_from(providers.provider_id)
    for e in edges.itertuples():
        G.add_edge(e.src_id, e.dst_id, weight=e.weight)
        if e.dst_type == "provider":      # strong ties only: referrals, associations, shared members
            w = 1.5 if e.edge_type == "associated_with" else np.log1p(e.weight)
            if P.has_edge(e.src_id, e.dst_id):
                P[e.src_id][e.dst_id]["weight"] += w
            else:
                P.add_edge(e.src_id, e.dst_id, weight=w)
    fac_members: dict[str, list[str]] = {}
    for e in edges[edges.edge_type == "works_at"].itertuples():
        fac_members.setdefault(e.dst_id, []).append(e.src_id)
    colo: dict[str, set] = {p: set() for p in providers.provider_id}
    for f, ms in fac_members.items():
        for a, b in combinations(ms, 2):
            colo[a].add(b)
            colo[b].add(a)
    bet = nx.betweenness_centrality(P, k=None, normalized=True)
    deg_c = nx.degree_centrality(P)
    clus = nx.clustering(P)
    comms = nx.community.louvain_communities(P, weight="weight", seed=config.SEED)
    comm_of = {n: i for i, c in enumerate(sorted(comms, key=len, reverse=True)) for n in c}
    comm_size = {i: len(c) for i, c in enumerate(sorted(comms, key=len, reverse=True))}
    comp = {n: i for i, c in enumerate(sorted(nx.connected_components(G), key=len, reverse=True)) for n in c}
    comp_size = pd.Series(comp).value_counts().to_dict()
    ncolo = {p: len(v) for p, v in colo.items()}
    nfac = edges[edges.edge_type == "works_at"].groupby("src_id").dst_id.nunique()
    out = pd.DataFrame({"provider_id": list(providers.provider_id)})
    out["degree"] = out.provider_id.map(dict(P.degree()))
    out["degree_centrality"] = out.provider_id.map(deg_c)
    out["betweenness"] = out.provider_id.map(bet)
    out["clustering"] = out.provider_id.map(clus)
    out["community_id"] = out.provider_id.map(comm_of)
    out["community_size"] = out.community_id.map(comm_size)
    out["component_id"] = out.provider_id.map(comp)
    out["component_size"] = out.component_id.map(comp_size)
    out["facilities"] = out.provider_id.map(nfac).fillna(0).astype(int)
    out["colocated_providers"] = out.provider_id.map(ncolo)
    return out


# ------------------------------------------------------------------------------------------------------------------ store
class GraphStore:
    """Cached graph used by the API for ego networks and case network metrics."""

    def __init__(self):
        self.lock = threading.Lock()
        self.loaded = False

    def load(self):
        with self.lock:
            e = db.query_df("SELECT * FROM network_edges")
            e["first_seen"] = pd.to_datetime(e.first_seen)
            self.edges = e
            self.prov = db.query_df("SELECT provider_id, display_label, name, specialty, region, city, primary_facility_id FROM providers").set_index("provider_id")
            self.fac = db.query_df("SELECT facility_id, name, facility_type, region, city FROM facilities").set_index("facility_id")
            self.net = db.query_df("SELECT * FROM provider_network").set_index("provider_id")
            self.G = nx.Graph()
            for r in e.itertuples():
                self.G.add_edge(r.src_id, r.dst_id)
            self.loaded = True

    def ensure(self):
        if not self.loaded:
            self.load()

    def neighbors(self, node: str, kinds=("referred_to", "works_at", "associated_with", "shared_members")) -> pd.DataFrame:
        e = self.edges
        return e[((e.src_id == node) | (e.dst_id == node)) & e.edge_type.isin(kinds)]

    # ------------------------------------------------------------------------------------------------- ego network
    def ego(self, centers: list[str], hops: int = 1, max_nodes: int = MAX_NODES, risk: dict | None = None, evidence_edges: dict | None = None,
            include_claims: bool = True, case_providers: list[str] | None = None) -> dict:
        self.ensure()
        risk = risk or {}
        case_providers = case_providers or [c for c in centers if c.startswith("PRV-")]
        nodes: dict[str, dict] = {}
        edges: dict[str, dict] = {}

        def add_node(nid: str, **kw):
            if nid not in nodes:
                nodes[nid] = {"id": nid, **kw}

        def prov_node(pid: str, depth: int):
            r = self.prov.loc[pid] if pid in self.prov.index else None
            n = self.net.loc[pid] if pid in self.net.index else None
            add_node(pid, label=pid, type="provider", display=r.display_label if r is not None else pid, specialty=None if r is None else r.specialty,
                     region=None if r is None else r.region, risk=risk.get(pid), in_case=pid in case_providers, depth=depth,
                     betweenness=None if n is None else float(n.betweenness), community=None if n is None else int(n.community_id),
                     degree=None if n is None else int(n.degree))

        def fac_node(fid: str, depth: int):
            r = self.fac.loc[fid] if fid in self.fac.index else None
            add_node(fid, label=fid, type="facility", display=fid, specialty=None if r is None else r.facility_type, region=None if r is None else r.region, depth=depth, risk=None)

        def add_edge(e):
            if e.src_id not in nodes or e.dst_id not in nodes:
                return
            key = f"{e.edge_type}:{e.src_id}>{e.dst_id}"
            if key in edges:
                return
            ev = (evidence_edges or {}).get(key) or (evidence_edges or {}).get(f"{e.edge_type}:{e.dst_id}>{e.src_id}")
            edges[key] = {"id": key, "source": e.src_id, "target": e.dst_id, "type": e.edge_type, "weight": float(e.weight),
                          "label": {"referred_to": f"{int(e.weight)} referrals", "works_at": f"{int(e.weight)} claims", "associated_with": "associated",
                                    "shared_members": f"{int(e.weight)} shared members"}.get(e.edge_type, e.edge_type),
                          "evidence_ids": ev or [], "first_seen": None if pd.isna(e.first_seen) else str(pd.Timestamp(e.first_seen).date())}

        frontier = []
        for cid in centers:
            if cid.startswith("PRV-"):
                prov_node(cid, 0)
            else:
                fac_node(cid, 0)
            frontier.append(cid)
        seen = set(frontier)
        for depth in range(1, hops + 1):
            nxt = []
            for node in frontier:
                nb = self.neighbors(node).sort_values("weight", ascending=False)
                cap = 14 if depth == 1 else 5
                for r in nb.head(cap * 2).itertuples():
                    other = r.dst_id if r.src_id == node else r.src_id
                    if other in nodes:
                        continue
                    if len(nodes) >= max_nodes:
                        break
                    (prov_node if other.startswith("PRV-") else fac_node)(other, depth)
                    nxt.append(other)
                    seen.add(other)
            frontier = nxt
        # include all case providers' direct facility links and inter-provider edges among included nodes
        for pid in case_providers:
            for r in self.neighbors(pid, ("works_at",)).itertuples():
                if r.dst_id not in nodes and len(nodes) < max_nodes:
                    fac_node(r.dst_id, 1)
        ids = set(nodes)
        sub = self.edges[self.edges.src_id.isin(ids) & self.edges.dst_id.isin(ids)]
        for r in sub.itertuples():
            add_edge(r)
        return {"nodes": nodes, "edges": edges}


STORE = GraphStore()


def claim_layer(case_providers: list[str], flagged: pd.DataFrame, nodes: dict, edges: dict, per_provider: int = 5, max_members: int = 14) -> None:
    """Add flagged claim + member nodes (top paid flagged claims per case provider) to an ego network, in place."""
    if flagged.empty:
        return
    top = flagged.sort_values("paid_amount", ascending=False).groupby("provider_id").head(per_provider)
    # members that appear with >=2 case providers are the strongest connecting leads
    shared = flagged.groupby("member_id").provider_id.nunique()
    shared_members = set(shared[shared >= 2].index[:max_members])
    mem_keep = set(top.member_id) | shared_members
    for r in top.itertuples():
        if r.provider_id not in nodes:
            continue
        cid = r.claim_id
        nodes[cid] = {"id": cid, "label": cid, "type": "claim", "display": cid, "specialty": r.procedure_code, "region": None, "risk": None, "in_case": True,
                      "paid": float(r.paid_amount), "service_date": str(pd.Timestamp(r.service_date).date()), "rules": r.rules, "evidence_ids": r.evidence_ids}
        edges[f"submitted:{r.provider_id}>{cid}"] = {"id": f"submitted:{r.provider_id}>{cid}", "source": r.provider_id, "target": cid, "type": "submitted",
                                                     "weight": 1.0, "label": "submitted", "evidence_ids": r.evidence_ids, "first_seen": None}
        mid = r.member_id
        if mid in mem_keep:
            nodes.setdefault(mid, {"id": mid, "label": mid, "type": "member", "display": mid, "specialty": None, "region": None, "risk": None, "in_case": True,
                                   "shared": mid in shared_members})
            edges[f"belongs_to:{cid}>{mid}"] = {"id": f"belongs_to:{cid}>{mid}", "source": cid, "target": mid, "type": "belongs_to", "weight": 1.0,
                                                "label": "belongs to member", "evidence_ids": [], "first_seen": None}
    for r in flagged[flagged.member_id.isin(shared_members)].itertuples():
        if r.provider_id in nodes and r.member_id in nodes:
            k = f"received_from:{r.member_id}>{r.provider_id}"
            edges.setdefault(k, {"id": k, "source": r.member_id, "target": r.provider_id, "type": "received_from", "weight": 1.0, "label": "seen by provider",
                                 "evidence_ids": [], "first_seen": None})
