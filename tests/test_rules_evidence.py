import pytest
from app import config, db

RULES = ["R001_DUPLICATE", "R002_UPCODING", "R003_UNBUNDLING", "R004_IMPLAUSIBLE_SERVICE", "R005_EXCESSIVE_UTILIZATION", "R006_IMPOSSIBLE_TIMING", "R007_REFERRAL_CONCENTRATION", "R008_NETWORK_EXPANSION"]


@pytest.mark.parametrize("rule", RULES)
def test_every_rule_fires_with_structured_evidence(rule):
    rows = db.query_rows("SELECT * FROM evidence WHERE rule_id=:r", {"r": rule})
    assert rows, f"{rule} produced no evidence"
    for e in rows[:50]:
        for f in ("evidence_id", "rule_id", "severity", "source_table", "source_row_id", "feature", "explanation", "event_ts", "rule_version", "provider_id"):
            assert e[f] not in (None, ""), (rule, f)
        assert e["observed_value"] is not None and e["expected_value"] is not None
        assert e["rule_version"] == config.RULE_VERSION


def test_claim_level_rules_cite_claims():
    for rule in ("R001_DUPLICATE", "R003_UNBUNDLING", "R004_IMPLAUSIBLE_SERVICE", "R006_IMPOSSIBLE_TIMING"):
        rows = db.query_rows("SELECT claim_ids FROM evidence WHERE rule_id=:r LIMIT 40", {"r": rule})
        assert all(len(r["claim_ids"]) >= 1 for r in rows), rule


def test_evidence_claim_ids_exist():
    bad = db.query_one("""SELECT count(*) n FROM (SELECT unnest(claim_ids) cid FROM evidence WHERE evidence_type='RULE' LIMIT 20000) x
                          LEFT JOIN claims c ON c.claim_id=x.cid WHERE c.claim_id IS NULL""")["n"]
    assert bad == 0


def test_anomaly_never_called_probability():
    rows = db.query_rows("SELECT explanation FROM evidence WHERE evidence_type='ANOMALY' LIMIT 20")
    assert rows and all("not a fraud probability" in r["explanation"] for r in rows)
    shap = db.query_rows("SELECT explanation FROM evidence WHERE evidence_type='SHAP' LIMIT 20")
    assert all("not evidence of misconduct" in r["explanation"] for r in shap)
