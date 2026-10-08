"""30/60/90-day forward risk.

Chronological, purged train / calibration / test split. Calibration is evaluated honestly on a later test period.
If (and only if) calibration criteria are met the outputs are labelled 'probability'; otherwise they are an
'escalation index'. Calibration is never assumed.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss

from . import config, db
from .features import MODEL_FEATURES
from .ml import precision_recall_at_k

FORECAST_VERSION = "forecast-1.0.0"
HORIZONS = {30: ("y_h1", 1), 60: ("y_h2", 2), 90: ("y_h3", 3)}
TRAIN = (4, 8)          # snapshots 4..8
CALIB = (9, 11)         # snapshots 9..11
TEST_START = 14         # snapshots >= 14 (label windows of train/calibration end by month 14 -> purged)

ECE_MAX, MIN_TEST_POS = 0.05, 30


def _ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> tuple[float, list[dict]]:
    q = pd.qcut(pd.Series(p).rank(method="first"), bins, labels=False)
    rows, ece = [], 0.0
    for b in range(bins):
        m = (q == b).to_numpy()
        if m.sum() == 0:
            continue
        rows.append({"bin": b, "n": int(m.sum()), "mean_predicted": float(p[m].mean()), "observed_rate": float(y[m].mean())})
        ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(ece), rows


def train_and_score(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    t0 = time.time()
    act = panel[(panel.n_t3 > 0)].copy()
    result = {"version": FORECAST_VERSION, "horizons": {}, "split": {"train_snapshots": TRAIN, "calibration_snapshots": CALIB, "test_snapshots_from": TEST_START,
                                                                      "purged_snapshots": [CALIB[1] + 1, TEST_START - 1]},
              "label": "provider has >=3 injected-FWA claims in the next 30/60/90 days (synthetic ground truth)"}
    scored = panel[["provider_id", "month_idx"]].copy()
    all_pass = True
    models, isos = {}, {}
    for h, (lab, hm) in HORIZONS.items():
        d = act[act[lab].notna()]
        tr = d[(d.month_idx >= TRAIN[0]) & (d.month_idx <= TRAIN[1])]
        ca = d[(d.month_idx >= CALIB[0]) & (d.month_idx <= CALIB[1])]
        te = d[d.month_idx >= TEST_START]
        Xtr, ytr = tr[MODEL_FEATURES].astype(float), tr[lab].astype(int).to_numpy()
        Xca, yca = ca[MODEL_FEATURES].astype(float), ca[lab].astype(int).to_numpy()
        Xte, yte = te[MODEL_FEATURES].astype(float), te[lab].astype(int).to_numpy()
        m = xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.85, colsample_bytree=0.85, min_child_weight=3, reg_lambda=3.0,
                              eval_metric="logloss", early_stopping_rounds=25, random_state=config.SEED, n_jobs=2, tree_method="hist")
        m.fit(Xtr, ytr, eval_set=[(Xca, yca)], verbose=False)
        raw_ca, raw_te = m.predict_proba(Xca)[:, 1], m.predict_proba(Xte)[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw_ca, yca)
        cal_te = iso.predict(raw_te)
        base_rate = float(np.concatenate([ytr, yca]).mean())
        brier_base = float(brier_score_loss(yte, np.full(len(yte), base_rate)))
        out = {"n_train": int(len(ytr)), "n_calibration": int(len(yca)), "n_test": int(len(yte)), "test_positives": int(yte.sum()), "test_base_rate": float(yte.mean()),
               "train_base_rate": float(ytr.mean())}
        for name, p in (("raw", raw_te), ("calibrated", cal_te)):
            e, rel = _ece(yte, p)
            out[name] = {"brier": float(brier_score_loss(yte, p)), "ece": e, "pr_auc": float(average_precision_score(yte, p)), "reliability": rel,
                         "precision_at_50": precision_recall_at_k(yte, p, 50)[0], "recall_at_100": precision_recall_at_k(yte, p, 100)[1]}
        out["brier_constant_baseline"] = brier_base
        ok = (out["calibrated"]["ece"] <= ECE_MAX) and (out["calibrated"]["brier"] < brier_base) and (int(yte.sum()) >= MIN_TEST_POS)
        out["calibration_criteria_met"] = bool(ok)
        out["criteria"] = {"ece_max": ECE_MAX, "brier_must_beat_constant_baseline": True, "min_test_positives": MIN_TEST_POS}
        all_pass &= bool(ok)
        result["horizons"][str(h)] = out
        models[h], isos[h] = m, iso
    label = "probability" if all_pass else "escalation index"
    result["output_label"] = label
    result["note"] = ("All three horizons passed calibration criteria on a later chronological test period; outputs are calibrated probabilities (synthetic data)."
                      if all_pass else "Calibration criteria were NOT met on the held-out test period; outputs are reported as escalation indices, not probabilities.")
    X = panel[MODEL_FEATURES].astype(float)
    prev = None
    for h in (30, 60, 90):
        raw = models[h].predict_proba(X)[:, 1]
        cal = isos[h].predict(raw)
        scored[f"raw_{h}"] = raw
        scored[f"cal_{h}"] = cal
        val = np.clip(cal if all_pass else raw, 0.01, 0.99)     # an empirical calibration never justifies certainty
        if prev is not None:
            val = np.maximum(val, prev)          # risk over a longer window cannot be lower than over a shorter one
        scored[f"f{h}"] = val
        prev = val
    scored["label"] = label
    result["seconds"] = round(time.time() - t0, 2)
    db.log_model_run("forecast", "XGBClassifier+Isotonic", FORECAST_VERSION, metrics=result, params={"features": MODEL_FEATURES},
                     notes=result["note"])
    return scored, result
