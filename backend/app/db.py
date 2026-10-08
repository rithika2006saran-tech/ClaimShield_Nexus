"""Database helpers (SQLAlchemy + pandas)."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from . import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@lru_cache(maxsize=1)
def engine() -> Engine:
    return create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5, connect_args={"options": "-c statement_timeout=600000"})


def reset_engine() -> None:
    engine.cache_clear()


@contextmanager
def begin():
    with engine().begin() as conn:
        yield conn


def execute(sql: str, params: dict | None = None) -> None:
    with begin() as conn:
        conn.execute(text(sql), params or {})


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def query_rows(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    with engine().connect() as conn:
        res = conn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in res]


def query_one(sql: str, params: dict | None = None) -> dict[str, Any] | None:
    rows = query_rows(sql, params)
    return rows[0] if rows else None


def apply_schema() -> None:
    sql = SCHEMA_PATH.read_text()
    raw = engine().raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(sql)
        raw.commit()
    finally:
        raw.close()


def table_exists(name: str) -> bool:
    r = query_one("SELECT to_regclass(:n) AS t", {"n": f"public.{name}"})
    return bool(r and r["t"])


def write_df(df: pd.DataFrame, table: str, if_exists: str = "replace", dtype: dict | None = None) -> None:
    with begin() as conn:
        df.to_sql(table, conn, if_exists=if_exists, index=False, method="multi", chunksize=max(1, 60000 // max(len(df.columns), 1)), dtype=dtype)


def copy_df(df: pd.DataFrame, table: str, columns: Iterable[str]) -> None:
    """Fast bulk load using COPY."""
    cols = list(columns)
    raw = engine().raw_connection()
    try:
        with raw.cursor() as cur:
            with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
                for row in df[cols].itertuples(index=False, name=None):
                    cp.write_row([None if (isinstance(v, float) and v != v) or v is pd.NaT else v for v in row])
        raw.commit()
    finally:
        raw.close()


def log_model_run(run_type: str, model_name: str, model_version: str, metrics: dict | None = None,
                  params: dict | None = None, notes: str | None = None) -> int:
    import json
    with begin() as conn:
        r = conn.execute(
            text(
                """INSERT INTO model_runs (run_type, model_name, model_version, dataset_version, finished_at,
                   metrics, params, notes) VALUES (:rt,:mn,:mv,:dv, now(), CAST(:m AS jsonb), CAST(:p AS jsonb), :n)
                   RETURNING run_id"""
            ),
            {
                "rt": run_type, "mn": model_name, "mv": model_version, "dv": config.DATASET_VERSION,
                "m": json.dumps(metrics or {}, default=_json_default),
                "p": json.dumps(params or {}, default=_json_default), "n": notes,
            },
        )
        return int(r.scalar_one())


def _json_default(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)
