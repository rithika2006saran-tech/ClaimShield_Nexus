from app import config, db


def test_scale_within_targets():
    n = db.query_one("""SELECT (SELECT count(*) FROM claims) c, (SELECT count(*) FROM providers) p, (SELECT count(*) FROM members) m,
                        (SELECT count(*) FROM facilities) f, (SELECT count(*) FROM referrals) r, (SELECT count(*) FROM investigations) i""")
    assert 50_000 <= n["c"] <= 100_000
    assert 1_000 <= n["p"] <= 2_000
    assert 10_000 <= n["m"] <= 15_000
    assert 200 <= n["f"] <= 300
    assert 3_000 <= n["r"] <= 5_000
    assert 100 <= n["i"] <= 500


def test_ingestion_quarantines_invalid_rows_with_reasons():
    rows = db.query_rows("SELECT reason, count(*) n FROM quarantine GROUP BY reason")
    assert sum(r["n"] for r in rows) > 0
    assert all(r["reason"] for r in rows)


def test_canonical_provider_id():
    p = db.query_one("SELECT provider_id, display_label FROM providers WHERE provider_id='PRV-102'")
    assert p and p["display_label"] == "P102"


def test_ground_truth_not_in_feature_tables():
    cols = {r["column_name"] for r in db.query_rows("SELECT column_name FROM information_schema.columns WHERE table_name='provider_features'")}
    assert not any("injected" in c or c in ("role", "scenario") for c in cols)
