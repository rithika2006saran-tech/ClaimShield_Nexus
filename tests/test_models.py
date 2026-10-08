from app import db
from app.api.util import jl


def _latest(run_type):
    return jl(db.query_one("SELECT metrics FROM model_runs WHERE run_type=:t ORDER BY run_id DESC LIMIT 1", {"t": run_type})["metrics"])


def test_xgboost_metrics_come_from_a_chronological_run_and_beat_baselines():
    m = _latest("xgboost")
    assert m["split"]["train_months"] == "4-11" and m["split"]["test_months"] == "14-18"
    x = m["xgboost"]
    for k in ("pr_auc", "precision", "recall", "precision_at_50", "recall_at_100"):
        assert 0 <= x[k] <= 1
    assert x["pr_auc"] > m["rules_only_baseline"]["pr_auc"]
    assert x["pr_auc"] > x["base_rate"]


def test_forecast_label_matches_calibration_evidence():
    f = _latest("forecast")
    ok = all(h["calibration_criteria_met"] for h in f["horizons"].values())
    assert f["output_label"] == ("probability" if ok else "escalation index")
    for h in f["horizons"].values():
        if ok:
            assert h["calibrated"]["ece"] <= 0.05 and h["calibrated"]["brier"] < h["brier_constant_baseline"]


def test_forecast_monotone_across_horizons():
    r = db.query_one("SELECT count(*) n FROM provider_forecast WHERE f30 > f60 + 1e-9 OR f60 > f90 + 1e-9")
    assert r["n"] == 0


def test_shap_present_for_hero():
    s = db.query_one("SELECT shap FROM provider_scores WHERE provider_id='PRV-102'")
    shap = jl(s["shap"])
    assert shap["positive"] and "shap_value" in shap["positive"][0]
