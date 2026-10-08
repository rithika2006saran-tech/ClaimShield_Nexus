"""Feature intelligence: provider behaviour features, peer benchmarking, connection history and monthly panel.

Peer benchmarking compares each provider with providers of the same specialty, geography (region) and
primary facility type (hierarchical fallback when a cell is too small). Deviation is shown as a robust z-score,
percentile and ratio-to-median. Peer deviation alone is NOT evidence of misconduct.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

AS_OF = pd.Timestamp(config.AS_OF)
W90 = AS_OF - pd.Timedelta(days=89)
W180 = AS_OF - pd.Timedelta(days=179)
MIN_PEERS = 10

PEER_METRICS = [
    "claims_per_month_90d", "paid_per_month_90d", "avg_allowed_90d", "claims_per_member_90d", "unique_members_90d",
    "unique_facilities_90d", "high_cx_ratio_180d", "dup_rate_90d", "ref_in_top_share_180d", "ref_out_top_share_180d", "degree",
]


def assign_peer_groups(providers: pd.DataFrame) -> pd.DataFrame:
    p = providers.copy()
    p["peer_group"] = p.specialty + "|" + p.region + "|" + p.primary_facility_type
    sz = p.groupby("peer_group").provider_id.transform("size")
    fb1 = p.specialty + "|" + p.region
    sz1 = fb1.map(fb1.value_counts())
    p.loc[sz < MIN_PEERS, "peer_group"] = fb1[sz < MIN_PEERS]
    sz = p.groupby("peer_group").provider_id.transform("size")
    low = sz < MIN_PEERS
    p.loc[low, "peer_group"] = p.loc[low, "specialty"]
    p["peer_size"] = p.groupby("peer_group").provider_id.transform("size")
    return p[["provider_id", "peer_group", "peer_size"]]


def connection_events(referrals: pd.DataFrame, rels: pd.DataFrame) -> pd.DataFrame:
    """Every provider<->partner connection with the date it was first observed."""
    r = referrals.groupby(["referring_provider_id", "target_provider_id"]).referral_date.min().reset_index()
    a = r.rename(columns={"referring_provider_id": "provider_id", "target_provider_id": "partner_id", "referral_date": "first_seen"})
    a["partner_type"] = "provider"
    a["kind"] = "referred_to"
    b = r.rename(columns={"target_provider_id": "provider_id", "referring_provider_id": "partner_id", "referral_date": "first_seen"})
    b["partner_type"] = "provider"
    b["kind"] = "referred_from"
    w = rels[rels.relationship_type == "works_at"].rename(columns={"entity_a_id": "provider_id", "entity_b_id": "partner_id", "start_date": "first_seen"})
    w = w[["provider_id", "partner_id", "first_seen"]].assign(partner_type="facility", kind="works_at")
    s = rels[rels.relationship_type == "associated_with"]
    s1 = s.rename(columns={"entity_a_id": "provider_id", "entity_b_id": "partner_id", "start_date": "first_seen"})[["provider_id", "partner_id", "first_seen"]]
    s2 = s.rename(columns={"entity_b_id": "provider_id", "entity_a_id": "partner_id", "start_date": "first_seen"})[["provider_id", "partner_id", "first_seen"]]
    s1["partner_type"] = s2["partner_type"] = "provider"
    s1["kind"] = s2["kind"] = "associated_with"
    ev = pd.concat([a, b, w, s1, s2], ignore_index=True)
    # one row per (provider, partner): earliest observation
    ev = ev.sort_values("first_seen").groupby(["provider_id", "partner_id", "partner_type"], as_index=False).agg(first_seen=("first_seen", "min"), kind=("kind", "first"))
    return ev


def _top_share(df: pd.DataFrame, group_col: str, partner_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[group_col, "n", "top_share", "top_partner"])
    cnt = df.groupby([group_col, partner_col]).size().rename("c").reset_index()
    tot = cnt.groupby(group_col).c.sum().rename("n")
    top = cnt.sort_values("c", ascending=False).drop_duplicates(group_col).set_index(group_col)
    out = pd.concat([tot, top.c.rename("top_c"), top[partner_col].rename("top_partner")], axis=1)
    out["top_share"] = out.top_c / out.n
    return out.reset_index()[[group_col, "n", "top_share", "top_partner"]]


def _robust_stats(df: pd.DataFrame, metrics: list[str], group: str = "peer_group") -> pd.DataFrame:
    out = df.copy()
    for m in metrics:
        g = out.groupby(group)[m]
        med = g.transform("median")
        mad = (out[m] - med).abs().groupby(out[group]).transform("median")
        floor = np.maximum(0.15 * med.abs(), 1e-6)
        scale = np.maximum(mad, floor)
        out[f"peer_median__{m}"] = med
        out[f"peer_z__{m}"] = 0.6745 * (out[m] - med) / scale
        out[f"peer_pct__{m}"] = g.rank(pct=True)
        out[f"peer_ratio__{m}"] = np.where(med > 0, out[m] / med, np.nan)
    return out


def build_provider_features(claims: pd.DataFrame, referrals: pd.DataFrame, rels: pd.DataFrame, providers: pd.DataFrame,
                            dup_claim_ids: set[str]) -> pd.DataFrame:
    peers = assign_peer_groups(providers)
    base = providers[["provider_id", "specialty", "region", "primary_facility_type", "name", "display_label"]].merge(peers, on="provider_id")
    c90 = claims[claims.service_date >= W90]
    g = c90.groupby("provider_id")
    f = pd.DataFrame({
        "claims_90d": g.size(), "paid_90d": g.paid_amount.sum(), "avg_allowed_90d": g.allowed_amount.mean(),
        "unique_members_90d": g.member_id.nunique(), "unique_facilities_90d": g.facility_id.nunique(),
    })
    f["claims_per_month_90d"] = f.claims_90d / 3.0
    f["paid_per_month_90d"] = f.paid_90d / 3.0
    f["claims_per_member_90d"] = f.claims_90d / f.unique_members_90d
    d90 = c90[c90.claim_id.isin(dup_claim_ids)].groupby("provider_id").size()
    f["dup_claims_90d"] = d90
    f["dup_claims_90d"] = f.dup_claims_90d.fillna(0)
    f["dup_rate_90d"] = f.dup_claims_90d / f.claims_90d
    c180 = claims[(claims.service_date >= W180) & claims.em_level.notna()]
    em = c180.groupby("provider_id").agg(em_claims_180d=("claim_id", "size"), hi=("em_level", lambda s: (s >= 4).sum()))
    em["high_cx_ratio_180d"] = np.where(em.em_claims_180d >= 20, em.hi / em.em_claims_180d, np.nan)
    f = f.join(em[["em_claims_180d", "high_cx_ratio_180d"]])
    rin = _top_share(referrals[referrals.referral_date >= W180], "target_provider_id", "referring_provider_id")
    rout = _top_share(referrals[referrals.referral_date >= W180], "referring_provider_id", "target_provider_id")
    f = f.join(rin.set_index("target_provider_id").rename(columns={"n": "ref_in_n_180d", "top_share": "ref_in_top_share_180d", "top_partner": "ref_in_top_referrer"}))
    f = f.join(rout.set_index("referring_provider_id").rename(columns={"n": "ref_out_n_180d", "top_share": "ref_out_top_share_180d", "top_partner": "ref_out_top_target"}))
    ce = connection_events(referrals, rels)
    ce = ce[ce.first_seen <= AS_OF]
    deg = ce.groupby("provider_id").size().rename("degree")
    new90 = ce[ce.first_seen >= W90].groupby("provider_id").size().rename("new_connections_90d")
    f = f.join(deg).join(new90)
    f["new_connections_90d"] = f.new_connections_90d.fillna(0)
    f["prior_connections"] = f.degree.fillna(0) - f.new_connections_90d
    f = base.merge(f.reset_index().rename(columns={"index": "provider_id"}), on="provider_id", how="left")
    for col in ["claims_90d", "paid_90d", "unique_members_90d", "unique_facilities_90d", "claims_per_month_90d", "paid_per_month_90d", "dup_claims_90d",
                "em_claims_180d", "ref_in_n_180d", "ref_out_n_180d", "degree", "new_connections_90d", "prior_connections"]:
        f[col] = f[col].fillna(0)
    # only benchmark on providers with enough activity to be meaningful
    low = f.claims_90d < 8
    for m in ["claims_per_month_90d", "paid_per_month_90d", "avg_allowed_90d", "claims_per_member_90d", "unique_members_90d", "unique_facilities_90d"]:
        f.loc[low, m + "_raw"] = f.loc[low, m]
    f = _robust_stats(f, PEER_METRICS)
    f["low_volume"] = low
    f["as_of"] = AS_OF.date()
    f["feature_version"] = config.FEATURE_VERSION
    return f


def build_panel(claims: pd.DataFrame, referrals: pd.DataFrame, rels: pd.DataFrame, providers: pd.DataFrame, flags: pd.DataFrame,
                labels: pd.DataFrame) -> pd.DataFrame:
    """Provider x month feature panel (point-in-time: month m only uses data <= end of month m)."""
    peers = assign_peer_groups(providers)
    months = np.arange(1, config.N_MONTHS + 1)
    grid = pd.MultiIndex.from_product([providers.provider_id, months], names=["provider_id", "month_idx"]).to_frame(index=False)
    c = claims.merge(flags, on="claim_id", how="left").fillna({"f_dup": False, "f_unbundle": False, "f_implaus": False, "f_timing": False})
    g = c.groupby(["provider_id", "month_idx"])
    m = pd.DataFrame({
        "n": g.size(), "paid": g.paid_amount.sum(), "allowed_mean": g.allowed_amount.mean(), "uniq_members": g.member_id.nunique(),
        "uniq_fac": g.facility_id.nunique(), "dup_n": g.f_dup.sum(), "unbundle_n": g.f_unbundle.sum(), "implaus_n": g.f_implaus.sum(),
        "timing_n": g.f_timing.sum(),
    }).reset_index()
    em = c[c.em_level.notna()].groupby(["provider_id", "month_idx"]).agg(em_n=("claim_id", "size"), hi_n=("em_level", lambda s: (s >= 4).sum())).reset_index()
    lab = labels.merge(claims[["claim_id", "provider_id", "month_idx"]], on="claim_id")
    ln = lab[lab.injected_fwa].groupby(["provider_id", "month_idx"]).size().rename("inj_n").reset_index()
    panel = grid.merge(m, on=["provider_id", "month_idx"], how="left").merge(em, on=["provider_id", "month_idx"], how="left") \
        .merge(ln, on=["provider_id", "month_idx"], how="left").merge(peers, on="provider_id")
    num = ["n", "paid", "uniq_members", "uniq_fac", "dup_n", "unbundle_n", "implaus_n", "timing_n", "em_n", "hi_n", "inj_n"]
    panel[num] = panel[num].fillna(0)
    panel = panel.sort_values(["provider_id", "month_idx"]).reset_index(drop=True)

    def roll(col, w):
        return panel.groupby("provider_id")[col].transform(lambda s: s.rolling(w, min_periods=1).sum())

    panel["n_t3"] = roll("n", 3)
    panel["n_prev3"] = panel.groupby("provider_id").n_t3.shift(3).fillna(panel.n_t3)
    panel["paid_t3"] = roll("paid", 3)
    panel["avg_amt_t3"] = panel.paid_t3 / panel.n_t3.replace(0, np.nan)
    panel["uniq_members_t3"] = roll("uniq_members", 3)
    panel["members_per_claim_t3"] = panel.uniq_members_t3 / panel.n_t3.replace(0, np.nan)
    panel["dup_t3"] = roll("dup_n", 3)
    panel["unbundle_t3"] = roll("unbundle_n", 3)
    panel["implaus_t3"] = roll("implaus_n", 3)
    panel["timing_t3"] = roll("timing_n", 3)
    em3, hi3 = roll("em_n", 3), roll("hi_n", 3)
    panel["hi_ratio_t3"] = np.where(em3 >= 8, hi3 / em3.replace(0, np.nan), np.nan)
    panel["dup_rate_t3"] = panel.dup_t3 / panel.n_t3.replace(0, np.nan)
    panel["growth_t3"] = (panel.n_t3 + 1) / (panel.n_prev3 + 1)
    panel["growth_t1"] = (panel.n + 1) / (panel.groupby("provider_id").n.transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean()).fillna(panel.n) + 1)
    # referral concentration & connections (trailing 3 months)
    ref = referrals.copy()
    rows = []
    for mi in months:
        win = ref[(ref.month_idx <= mi) & (ref.month_idx > mi - 3)]
        a = _top_share(win, "target_provider_id", "referring_provider_id").rename(columns={"target_provider_id": "provider_id", "n": "ref_in_n_t3", "top_share": "ref_in_top_t3"})
        b = _top_share(win, "referring_provider_id", "target_provider_id").rename(columns={"referring_provider_id": "provider_id", "n": "ref_out_n_t3", "top_share": "ref_out_top_t3"})
        x = a[["provider_id", "ref_in_n_t3", "ref_in_top_t3"]].merge(b[["provider_id", "ref_out_n_t3", "ref_out_top_t3"]], on="provider_id", how="outer")
        x["month_idx"] = mi
        rows.append(x)
    rr = pd.concat(rows, ignore_index=True)
    panel = panel.merge(rr, on=["provider_id", "month_idx"], how="left")
    for col in ["ref_in_n_t3", "ref_out_n_t3"]:
        panel[col] = panel[col].fillna(0)
    panel["ref_in_top_t3"] = np.where(panel.ref_in_n_t3 >= 8, panel.ref_in_top_t3, 0).astype(float)
    panel["ref_out_top_t3"] = np.where(panel.ref_out_n_t3 >= 8, panel.ref_out_top_t3, 0).astype(float)
    ce = connection_events(referrals, rels)
    ce["first_m"] = ((ce.first_seen.dt.year - config.DATA_START.year) * 12 + ce.first_seen.dt.month - config.DATA_START.month + 1).clip(lower=0)
    cm = ce.groupby(["provider_id", "first_m"]).size().rename("new_conn").reset_index().rename(columns={"first_m": "month_idx"})
    panel = panel.merge(cm, on=["provider_id", "month_idx"], how="left")
    panel["new_conn"] = panel.new_conn.fillna(0)
    pre = ce[ce.first_m <= 0].groupby("provider_id").size().rename("pre_conn")
    panel = panel.merge(pre, on="provider_id", how="left")
    panel["pre_conn"] = panel.pre_conn.fillna(0)
    panel["cum_conn"] = panel.pre_conn + panel.groupby("provider_id").new_conn.cumsum()
    panel["new_conn_t3"] = roll("new_conn", 3)
    # peer-relative features (same peer group, same month)
    for col in ["n_t3", "avg_amt_t3", "members_per_claim_t3", "paid_t3", "hi_ratio_t3"]:
        med = panel.groupby(["peer_group", "month_idx"])[col].transform("median")
        panel[f"{col}_vs_peer"] = np.where(med > 0, panel[col] / med, np.nan)
    panel["hi_ratio_delta"] = panel.hi_ratio_t3 - panel.groupby(["peer_group", "month_idx"]).hi_ratio_t3.transform("median")
    panel["month_start"] = panel.month_idx.map(lambda m: (pd.Timestamp(config.DATA_START) + pd.DateOffset(months=int(m) - 1)).date())
    # labels: same-month and future injected-claim counts
    panel["inj_next1"] = panel.groupby("provider_id").inj_n.transform(lambda s: s.shift(-1))
    panel["inj_next2"] = panel.groupby("provider_id").inj_n.transform(lambda s: s.shift(-1) + s.shift(-2))
    panel["inj_next3"] = panel.groupby("provider_id").inj_n.transform(lambda s: s.shift(-1) + s.shift(-2) + s.shift(-3))
    panel["y_now"] = (panel.inj_n >= 3).astype(int)
    for h, col in ((1, "inj_next1"), (2, "inj_next2"), (3, "inj_next3")):
        panel[f"y_h{h}"] = np.where(panel[col].notna(), (panel[col] >= 3).astype(float), np.nan)
    return panel


MODEL_FEATURES = [
    "n_t3_vs_peer", "avg_amt_t3_vs_peer", "members_per_claim_t3_vs_peer", "paid_t3_vs_peer", "hi_ratio_delta", "growth_t3", "growth_t1",
    "dup_t3", "dup_rate_t3", "unbundle_t3", "implaus_t3", "timing_t3", "ref_in_n_t3", "ref_in_top_t3", "ref_out_n_t3", "ref_out_top_t3",
    "new_conn_t3", "cum_conn",
]
FEATURE_LABELS = {
    "n_t3_vs_peer": "Claim volume vs peers (3-mo)", "avg_amt_t3_vs_peer": "Avg paid per claim vs peers", "members_per_claim_t3_vs_peer": "Member diversity vs peers",
    "paid_t3_vs_peer": "Paid dollars vs peers (3-mo)", "hi_ratio_delta": "High-complexity share vs peers", "growth_t3": "Volume growth (3-mo vs prior 3-mo)",
    "growth_t1": "Volume growth (month vs trailing avg)", "dup_t3": "Duplicate-billing claims (3-mo)", "dup_rate_t3": "Duplicate rate (3-mo)",
    "unbundle_t3": "Unbundling-pattern claims (3-mo)", "implaus_t3": "Implausible-service claims (3-mo)", "timing_t3": "Impossible-timing claims (3-mo)",
    "ref_in_n_t3": "Inbound referrals (3-mo)", "ref_in_top_t3": "Inbound top-referrer share", "ref_out_n_t3": "Outbound referrals (3-mo)",
    "ref_out_top_t3": "Outbound top-target share", "new_conn_t3": "New connections (3-mo)", "cum_conn": "Total connections",
}
