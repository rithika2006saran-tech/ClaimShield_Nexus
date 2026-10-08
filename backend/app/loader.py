"""Shared, cached loaders for enriched claim data (read-only, from PostgreSQL)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, db

AS_OF = pd.Timestamp(config.AS_OF)
START = pd.Timestamp(config.DATA_START)


def month_idx(ts: pd.Series) -> pd.Series:
    return ((ts.dt.year - START.year) * 12 + ts.dt.month - START.month + 1).astype(int)


def month_start(m: int) -> pd.Timestamp:
    return START + pd.DateOffset(months=m - 1)


def month_end(m: int) -> pd.Timestamp:
    return month_start(m) + pd.offsets.MonthEnd(0)


def load_enriched() -> pd.DataFrame:
    sql = """
    SELECT c.claim_id, c.member_id, c.provider_id, c.referring_provider_id, c.facility_id, c.service_date, c.submit_date,
           c.procedure_code, c.units, c.billed_amount::float AS billed_amount, c.allowed_amount::float AS allowed_amount,
           c.paid_amount::float AS paid_amount, c.service_minutes, c.claim_type,
           p.specialty, p.region AS provider_region, p.primary_facility_type,
           f.facility_type, f.region AS facility_region, f.lat AS fac_lat, f.lon AS fac_lon,
           pr.em_level, pr.bundle_group, pr.is_bundle_parent, pr.allowed_sex, pr.min_age, pr.max_age,
           array_to_string(pr.facility_types, '|') AS proc_facility_types, pr.category, pr.base_amount::float AS base_amount,
           m.age AS member_age, m.sex AS member_sex, m.death_date
    FROM claims c
    JOIN providers p USING (provider_id)
    JOIN facilities f ON f.facility_id = c.facility_id
    JOIN procedures pr ON pr.code = c.procedure_code
    JOIN members m USING (member_id)
    """
    df = db.query_df(sql)
    for col in ("service_date", "submit_date", "death_date"):
        df[col] = pd.to_datetime(df[col])
    df["month_idx"] = month_idx(df.service_date)
    return df


def load_referrals() -> pd.DataFrame:
    df = db.query_df("SELECT * FROM referrals")
    df["referral_date"] = pd.to_datetime(df.referral_date)
    df["month_idx"] = month_idx(df.referral_date)
    return df


def load_relationships() -> pd.DataFrame:
    df = db.query_df("SELECT * FROM relationships")
    df["start_date"] = pd.to_datetime(df.start_date)
    return df


def load_providers() -> pd.DataFrame:
    return db.query_df("SELECT * FROM providers")


def load_facilities() -> pd.DataFrame:
    return db.query_df("SELECT * FROM facilities")


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
