"""Warehouse and results checks on the real data (skipped until `make data pipeline` has run)."""
import json

import pytest

from src import config, data

pytestmark = pytest.mark.skipif(not config.DB_PATH.exists(), reason="run `make pipeline` first")


def test_zones_match_the_mta_list():
    counts = data.row_counts()
    assert counts["zones"] == 265
    assert counts["cbd_zones"] == 38
    boroughs = data.query("SELECT DISTINCT borough FROM zones WHERE in_cbd").borough.tolist()
    assert boroughs == ["Manhattan"]


def test_no_zone_charge_before_the_toll():
    """Charges appear before 5 Jan 2025 only on trips that began late on 4 Jan and ran past midnight."""
    early = data.query("SELECT SUM(trips_with_cbd_fee) AS n FROM trip_days WHERE season = '2023-24' OR rel_day < -1")
    assert early.n[0] == 0
    eve = data.query("SELECT SUM(trips_with_cbd_fee) AS n, SUM(trips) AS trips FROM trip_days "
                     "WHERE season = '2024-25' AND rel_day = -1")
    assert eve.n[0] / eve.trips[0] < 0.01


def test_touching_groups_almost_always_pay_after_the_toll():
    df = data.query("""SELECT trip_group, SUM(trips_with_cbd_fee) / SUM(trips) AS share FROM trip_days
                       WHERE season = '2024-25' AND rel_day >= 7 AND service = 'Uber/Lyft' GROUP BY 1""")
    share = df.set_index("trip_group").share
    assert (share[["Within zone", "Into zone", "Out of zone"]] > 0.95).all()
    assert share["Elsewhere"] < 0.05


def test_aggregate_keeps_every_clean_trip_once():
    q = data.query("SELECT 1")  # warehouse opens
    checks = __import__("pandas").read_csv(config.TABLES / "quality_checks.csv")
    assert data.row_counts()["clean_trips"] == int(checks.rows_kept.sum())


def test_results_are_consistent():
    r = json.loads(config.RESULTS_JSON.read_text())
    t = r["estimates"]["Uber/Lyft"]["trips"]["pooled"]
    assert t["effect_pct_low"] <= t["effect_pct"] <= t["effect_pct_high"]
    m = r["estimates"]["Uber/Lyft"]["money"]["cbd_fee_per_trip"]
    assert 1.3 < m["coef"] <= 1.5            # the $1.50 charge, net of trips through the zone counted as controls
