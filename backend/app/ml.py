"""ML layer.

  * Isolation Forest  -> complementary ANOMALY SCORE (never a fraud probability)
  * XGBoost           -> primary supervised FWA RISK SCORE trained on injected synthetic scenarios, chronological split
  * SHAP              -> model attribution for XGBoost (explanation, NOT proof)

Every metric reported here is computed from the actual run and stored in model_runs.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.preprocessing import StandardScaler

from . import config, db
from .features import FEATURE_LABELS, MODEL_FEATURES

XGB_VERSION = "xgb-fwa-risk-1.0.0"
IF_VERSION = "iforest-anomaly-1.0.0"

# month-index boundaries for the chronological split (month 1 = Apr 2025, month 18 = Sep 2026)
TRAIN_END, VAL_END = 11, 13           # train <= 11 < val <= 13 < test (14..18)

IF_FEATURES = ["claims_per_month_90d", "avg_allowed_90d", "paid_per_month_90d", "claims_per_member_90d", "unique_members_90d",
               "unique_facilities_90d", "dup_rate_90d", "ref_in_top_share_180d", "ref_out_top_share_180d", "degree", "new_connections_90d",
               "high_cx_ratio_180d"]


# ---------------------------------------------------------------------------------------------------------------- metrics
def precision_recall_at_k(y: np.ndarray, score: np.ndarray, k: int) -> tuple[float, float]:
    k = min(k, len(y))
    order = np.argsort(-score, kind="stable")[:k]
    tp = float(y[order].sum())
    return tp / k, tp / max(float(y.sum()), 1.0)


def eval_scores(y: np.ndarray, score: np.ndarray, threshold: float | None, ks=(25, 50, 100)) -> dict:
    out = {"n": int(len(y)), "positives": int(y.sum()), "base_rate": float(y.mean()) if len(y) else None,
           "pr_auc": float(average_precision_score(y, score)) if y.sum() > 0 else None}
    if threshold is not None:
        pred = score >= threshold
        tp = float((pred & (y == 1)).sum())
        out.update({"threshold": float(threshold), "precision": tp / max(pred.sum(), 1), "recall": tp / max(y.sum(), 1), "flagged": int(pred.sum())})
    for k in ks:
        p, r = precision_recall_at_k(y, score, k)
        out[f"precision_at_{k}"], out[f"recall_at_{k}"] = p, r
    return out


def best_f1_threshold(y: np.ndarray, score: np.ndarray) -> float:
    p, r, t = precision_recall_curve(y, score)
    f1 = 2 * p[:-1] * r[:-1] / np.maximum(p[:-1] + r[:-1], 1e-9)
    return float(t[int(np.nanargmax(f1))]) if len(t) else 0.5


# ------------------------------------------------------------------------------------------------------- Isolation Forest
def run_isolation_forest(feats: pd.DataFrame) -> pd.DataFrame:
    t0 = time.time()
    X = feats[IF_FEATURES].copy()
    for c in IF_FEATURES:
        X[c] = X[c].fillna(X[c].median() if X[c].notna().any() else 0.0)
    skew = ["claims_per_month_90d", "avg_allowed_90d", "paid_per_month_90d", "claims_per_member_90d", "unique_members_90d", "unique_facilities_90d", "degree", "new_connections_90d"]
    X[skew] = np.log1p(X[skew])
    Xs = StandardScaler().fit_transform(X)
    iso = IsolationForest(n_estimators=300, contamination="auto", random_state=config.SEED, n_jobs=2)
    iso.fit(Xs)
    raw = -iso.score_samples(Xs)                       # higher = more anomalous
    out = pd.DataFrame({"provider_id": feats.provider_id.to_numpy(), "anomaly_raw": raw})
    out["anomaly_score"] = out.anomaly_raw.rank(pct=True)   # percentile among all providers, 0..1
    # inactive providers are not scored as anomalous
    out.loc[feats.claims_90d.to_numpy() < 8, "anomaly_score"] = 0.0
    db.log_model_run("isolation_forest", "IsolationForest", IF_VERSION,
                     metrics={"n_providers": len(out), "seconds": round(time.time() - t0, 2),
                              "note": "Anomaly score (percentile rank of -score_samples). NOT a fraud probability."},
                     params={"n_estimators": 300, "features": IF_FEATURES, "contamination": "auto"})
    return out


# ------------------------------------------------------------------------------------------------------------- XGBoost
def _xy(df: pd.DataFrame, label: str):
    d = df[df[label].notna()]
    return d[MODEL_FEATURES].astype(float), d[label].astype(int).to_numpy(), d


def train_xgb_risk(panel: pd.DataFrame) -> tuple[xgb.XGBClassifier, dict, pd.DataFrame]:
    t0 = time.time()
    act = panel[(panel.n_t3 > 0) & (panel.month_idx >= 4)]
    tr, va, te = act[act.month_idx <= TRAIN_END], act[(act.month_idx > TRAIN_END) & (act.month_idx <= VAL_END)], act[act.month_idx > VAL_END]
    Xtr, ytr, _ = _xy(tr, "y_now")
    Xva, yva, _ = _xy(va, "y_now")
    Xte, yte, dte = _xy(te, "y_now")
    spw = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    model = xgb.XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.85, colsample_bytree=0.85, min_child_weight=2,
                              reg_lambda=2.0, scale_pos_weight=min(spw, 20.0), eval_metric="aucpr", early_stopping_rounds=30, random_state=config.SEED,
                              n_jobs=2, tree_method="hist")
    model.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    s_va, s_te = model.predict_proba(Xva)[:, 1], model.predict_proba(Xte)[:, 1]
    thr = best_f1_threshold(yva, s_va)
    metrics = {"split": {"train_months": f"4-{TRAIN_END}", "validation_months": f"{TRAIN_END + 1}-{VAL_END}", "test_months": f"{VAL_END + 1}-{config.N_MONTHS}",
                         "n_train": int(len(ytr)), "n_val": int(len(yva)), "n_test": int(len(yte))},
               "label": "provider-month has >=3 injected-FWA claims (synthetic ground truth)",
               "xgboost": eval_scores(yte, s_te, thr), "xgboost_at_0.5": eval_scores(yte, s_te, 0.5, ks=()),
               "best_iteration": int(model.best_iteration), "validation_threshold": thr}
    # baselines on the SAME test rows
    rules_flag = ((te.loc[dte.index, ["dup_t3", "unbundle_t3", "implaus_t3", "timing_t3"]] >= 3).any(axis=1)).astype(float).to_numpy()
    metrics["rules_only_baseline"] = eval_scores(yte, rules_flag, 0.5)
    iso = IsolationForest(n_estimators=200, random_state=config.SEED, n_jobs=2).fit(Xtr.fillna(0))
    s_if = -iso.score_samples(Xte.fillna(0))
    metrics["isolation_forest_baseline"] = eval_scores(yte, s_if, float(np.quantile(s_if, 1 - max(ytr.mean(), 0.02))))
    imp = dict(zip(MODEL_FEATURES, model.feature_importances_.astype(float)))
    metrics["feature_importance"] = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
    metrics["seconds"] = round(time.time() - t0, 2)
    db.log_model_run("xgboost", "XGBClassifier", XGB_VERSION, metrics=metrics,
                     params={"features": MODEL_FEATURES, "scale_pos_weight": min(spw, 20.0)},
                     notes="XGBoost FWA risk score. Synthetic labels; metrics do not imply real-world performance.")
    return model, metrics, panel


def score_panel(model: xgb.XGBClassifier, panel: pd.DataFrame) -> pd.Series:
    return pd.Series(model.predict_proba(panel[MODEL_FEATURES].astype(float))[:, 1], index=panel.index)


def shap_top(model: xgb.XGBClassifier, rows: pd.DataFrame, n_pos: int = 4, n_neg: int = 3) -> dict[str, dict]:
    """Per-provider SHAP attribution (top positive and negative contributors). Attribution is NOT proof of misconduct."""
    X = rows[MODEL_FEATURES].astype(float)
    expl = shap.TreeExplainer(model)
    sv = expl.shap_values(X)
    base = float(np.ravel(expl.expected_value)[0])
    out = {}
    for i, pid in enumerate(rows.provider_id.to_numpy()):
        vals = sv[i]
        order = np.argsort(-vals)
        pos = [j for j in order if vals[j] > 0][:n_pos]
        neg = [j for j in order[::-1] if vals[j] < 0][:n_neg]
        def row(j):
            return {"feature": MODEL_FEATURES[j], "label": FEATURE_LABELS[MODEL_FEATURES[j]], "feature_value": None if pd.isna(X.iloc[i, j]) else float(X.iloc[i, j]),
                    "shap_value": float(vals[j]), "direction": "raises risk" if vals[j] > 0 else "lowers risk"}
        out[pid] = {"base_value": base, "positive": [row(j) for j in pos], "negative": [row(j) for j in neg]}
    return out
