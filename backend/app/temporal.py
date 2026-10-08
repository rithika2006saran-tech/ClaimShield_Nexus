"""Temporal intelligence: rolling 7/30/90-day behaviour, 'What Changed?' phases and escalation indicators."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

AS_OF = pd.Timestamp(config.AS_OF)
START = pd.Timestamp(config.DATA_START)

INDICATORS = [
    ("UTILIZATION_INCREASE", "Utilization increase"),
    ("REFERRAL_CONCENTRATION", "Referral concentration"),
    ("DUPLICATE_ACTIVITY", "Duplicate activity"),
    ("NEW_FACILITY_RELATIONSHIPS", "New facility relationships"),
    ("HIGH_VALUE_PROCEDURE_INCREASE", "High-value procedure increase"),
    ("NETWORK_EXPANSION", "Network expansion"),
]


def _first_sustained(flag: pd.Series, dates: pd.Series, run: int = 2):
    """First date where `flag` is True for `run` consecutive weekly points."""
    arr = flag.to_numpy()
    for i in range(len(arr) - run + 1):
        if arr[i:i + run].all():
            return dates.iloc[i]
    return None


def provider_timeline(pid: str, claims: pd.DataFrame, referrals: pd.DataFrame, conn: pd.DataFrame, dup_ids: set[str]) -> dict:
    """Weekly rolling features for one provider + detected behavioural phase onsets."""
    c = claims[claims.provider_id == pid]
    days = pd.date_range(START, AS_OF, freq="D")
    daily = pd.DataFrame(index=days)
    daily["claims"] = c.groupby("service_date").size().reindex(days, fill_value=0)
    daily["paid"] = c.groupby("service_date").paid_amount.sum().reindex(days, fill_value=0.0)
    daily["allowed"] = c.groupby("service_date").allowed_amount.sum().reindex(days, fill_value=0.0)
    daily["dups"] = c[c.claim_id.isin(dup_ids)].groupby("service_date").size().reindex(days, fill_value=0)
    daily["hv"] = c[c.allowed_amount >= 3000].groupby("service_date").size().reindex(days, fill_value=0)
    r7, r30, r90 = (daily.rolling(w, min_periods=1).sum() for w in (7, 30, 90))
    weeks = days[days.dayofweek == 6]            # week ending Sunday
    weeks = weeks[weeks >= START + pd.Timedelta(days=13)]
    if weeks[-1] != AS_OF:
        weeks = weeks.append(pd.DatetimeIndex([AS_OF]))
    ref_in = referrals[referrals.target_provider_id == pid]
    ref_out = referrals[referrals.referring_provider_id == pid]
    ce = conn[conn.provider_id == pid]
    rows = []
    for w in weeks:
        lo = w - pd.Timedelta(days=89)
        ri = ref_in[(ref_in.referral_date >= lo) & (ref_in.referral_date <= w)]
        ro = ref_out[(ref_out.referral_date >= lo) & (ref_out.referral_date <= w)]
        top_in = (ri.referring_provider_id.value_counts(normalize=True).iloc[0] if len(ri) >= 10 else 0.0)
        top_out = (ro.target_provider_id.value_counts(normalize=True).iloc[0] if len(ro) >= 10 else 0.0)
        c30 = r30.loc[w, "claims"]
        rows.append({
            "week_end": w, "claims_7d": r7.loc[w, "claims"], "claims_30d": c30, "claims_90d": r90.loc[w, "claims"], "paid_30d": r30.loc[w, "paid"],
            "avg_allowed_30d": (r30.loc[w, "allowed"] / c30) if c30 > 0 else 0.0, "dup_claims_30d": r30.loc[w, "dups"], "high_value_30d": r30.loc[w, "hv"],
            "ref_in_top_share_90d": float(top_in), "ref_out_top_share_90d": float(top_out), "ref_in_90d": len(ri), "ref_out_90d": len(ro),
            "connections_cum": int((ce.first_seen <= w).sum()), "facilities_cum": int(((ce.first_seen <= w) & (ce.partner_type == "facility")).sum()),
            "new_connections_90d": int(((ce.first_seen > lo) & (ce.first_seen <= w)).sum()),
        })
    ts = pd.DataFrame(rows)
    base = ts[ts.week_end <= START + pd.Timedelta(days=26 * 7)]
    base_claims = max(float(base.claims_30d.median()), 1.0)
    base_allowed = max(float(base.avg_allowed_30d[base.claims_30d > 0].mean()) if (base.claims_30d > 0).any() else 1.0, 1.0)
    base_fac = int(base.facilities_cum.max())
    base_conn = int(base.connections_cum.max())
    onset = {}
    onset["UTILIZATION_INCREASE"] = _first_sustained((ts.claims_30d >= np.maximum(2 * base_claims, base_claims + 8)) & (ts.week_end > base.week_end.max()), ts.week_end)
    onset["REFERRAL_CONCENTRATION"] = _first_sustained(((ts.ref_in_top_share_90d >= 0.5) & (ts.ref_in_90d >= 12)) | ((ts.ref_out_top_share_90d >= 0.6) & (ts.ref_out_90d >= 12)), ts.week_end)
    onset["DUPLICATE_ACTIVITY"] = _first_sustained(ts.dup_claims_30d >= 4, ts.week_end)
    onset["NEW_FACILITY_RELATIONSHIPS"] = _first_sustained(ts.facilities_cum >= base_fac + 2, ts.week_end, run=1)
    base_hv = float(base.high_value_30d.max())
    onset["HIGH_VALUE_PROCEDURE_INCREASE"] = _first_sustained((ts.high_value_30d >= max(4.0, 2 * base_hv + 2)) & (ts.week_end > base.week_end.max()), ts.week_end)
    onset["NETWORK_EXPANSION"] = _first_sustained((ts.new_connections_90d >= 5) | (ts.connections_cum >= base_conn + 8), ts.week_end, run=1)
    events = []
    labels = dict(INDICATORS)
    for key, when in sorted(onset.items(), key=lambda kv: (kv[1] is None, kv[1])):
        if when is None:
            continue
        row = ts[ts.week_end == when].iloc[0]
        det = {
            "UTILIZATION_INCREASE": (f"30-day claim volume reached {row.claims_30d:.0f} versus a baseline of {base_claims:.0f}", row.claims_30d, base_claims, "claims/30d"),
            "REFERRAL_CONCENTRATION": (f"One partner accounts for {max(row.ref_in_top_share_90d, row.ref_out_top_share_90d):.0%} of referrals in the trailing 90 days", max(row.ref_in_top_share_90d, row.ref_out_top_share_90d), 0.3, "share"),
            "DUPLICATE_ACTIVITY": (f"{row.dup_claims_30d:.0f} duplicate-pattern claims in 30 days", row.dup_claims_30d, 0.0, "claims/30d"),
            "NEW_FACILITY_RELATIONSHIPS": (f"{int(row.facilities_cum)} facility relationships versus {base_fac} at baseline", row.facilities_cum, base_fac, "facilities"),
            "HIGH_VALUE_PROCEDURE_INCREASE": (f"{row.high_value_30d:.0f} high-value claims (allowed >= $3,000) in 30 days versus at most {base_hv:.0f} in any baseline month; average allowed per claim ${row.avg_allowed_30d:,.0f} (baseline ${base_allowed:,.0f})", row.high_value_30d, base_hv, "claims/30d"),
            "NETWORK_EXPANSION": (f"{int(row.new_connections_90d)} new connections in 90 days ({int(row.connections_cum)} total vs {base_conn} at baseline)", row.new_connections_90d, 0.0, "connections"),
        }[key]
        sample = []
        if key == "DUPLICATE_ACTIVITY":
            win = c[(c.service_date > when - pd.Timedelta(days=30)) & (c.service_date <= when) & c.claim_id.isin(dup_ids)]
            sample = win.claim_id.tolist()[:6]
        elif key == "HIGH_VALUE_PROCEDURE_INCREASE":
            win = c[(c.service_date > when - pd.Timedelta(days=30)) & (c.service_date <= when) & (c.allowed_amount >= 3000)]
            sample = win.claim_id.tolist()[:6]
        events.append({"indicator": key, "phase": labels[key], "date": str(when.date()), "description": det[0], "observed": float(det[1]), "baseline": float(det[2]),
                       "unit": det[3], "claim_ids": sample})
    active = len(events)
    last = ts.iloc[-1]
    recent = sum(1 for e in events if (AS_OF - pd.Timestamp(e["date"])).days <= 150)
    slope = float(np.clip(((last.claims_30d + 1) / (ts.iloc[-14].claims_30d + 1) - 1) / 3.0, 0, 1)) if len(ts) > 14 else 0.0
    escalation = float(np.clip(0.6 * active / len(INDICATORS) + 0.2 * recent / len(INDICATORS) + 0.2 * slope, 0, 1))
    phase = ["Normal", "Early drift", "Emerging pattern", "Emerging pattern", "Active multi-signal pattern", "Active multi-signal pattern", "Sustained high-priority escalation"][min(active, 6)]
    if active >= 4:
        hp = sorted(pd.Timestamp(e["date"]) for e in events)[3]
        events.append({"indicator": "HIGH_PRIORITY_INVESTIGATION", "phase": "High-priority investigation lead", "date": str(hp.date()),
                       "description": f"Four or more behavioural indicators were active at the same time ({active} of {len(INDICATORS)} now active)",
                       "observed": float(active), "baseline": 0.0, "unit": "indicators", "claim_ids": []})
        events.sort(key=lambda e: e["date"])
    series = ts.assign(week_end=ts.week_end.dt.strftime("%Y-%m-%d")).round(3).to_dict(orient="records")
    return {"provider_id": pid, "series": series, "events": events, "active_indicators": active, "escalation_score": escalation, "current_phase": phase,
            "baseline": {"claims_30d": base_claims, "avg_allowed": base_allowed, "facilities": base_fac, "connections": base_conn},
            "first_onset": events[0]["date"] if events else None}
