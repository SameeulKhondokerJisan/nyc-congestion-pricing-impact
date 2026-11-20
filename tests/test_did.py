"""Unit tests for the difference-in-differences code on synthetic data with a known effect."""
import numpy as np
import pandas as pd
import pytest

from src import config, did


def _flow_week(effect=-0.10, seed=0):
    """Two seasons, 12 zones x 2 groups, a seasonal winter dip shared by all, and a true toll effect."""
    rng = np.random.default_rng(seed)
    rows = []
    weeks = range(config.REL_WEEKS[0], config.REL_WEEKS[1] + 1)
    for zone in range(1, 13):
        for group in ("Into zone", "Elsewhere"):
            base = rng.uniform(300, 900)
            for season in (config.BASE, config.TOLL_SEASON):
                growth = 1.05 if season == config.TOLL_SEASON else 1.0
                for w in weeks:
                    seasonal = 0.85 if w >= 0 else 1.0          # winter dip, identical in both seasons
                    seasonal *= 0.9 if (group == "Into zone" and w >= 0) else 1.0   # zone trips dip more each winter
                    toll = np.exp(effect) if (season == config.TOLL_SEASON and group == "Into zone" and w >= 0) else 1.0
                    trips = base * growth * seasonal * toll * np.exp(rng.normal(0, 0.01))
                    rows.append({"season": season, "service": "Uber/Lyft", "pu_zone": zone, "trip_group": group,
                                 "rel_week": w, "trips": trips, "miles": trips * 4, "hours": trips * 0.3,
                                 "base_fare": trips * 30, "passenger_cost": trips * 38, "cbd_fee": 0.0,
                                 "driver_pay": trips * 22})
    return pd.DataFrame(rows)


def test_yoy_did_recovers_the_true_effect_and_removes_seasonality():
    fw = _flow_week(effect=-0.10)
    est = did.trips_did(did.yoy_panel(fw, "Uber/Lyft"))["pooled"]
    assert est["coef"] == pytest.approx(-0.10, abs=0.01)
    naive = did.single_season(fw, "Uber/Lyft")["estimate"]
    assert naive["coef"] == pytest.approx(-0.10 + np.log(0.9), abs=0.01)   # naive design absorbs the zone's winter dip


def test_no_effect_gives_zero_and_placebo_is_null():
    fw = _flow_week(effect=0.0, seed=1)
    est = did.trips_did(did.yoy_panel(fw, "Uber/Lyft"))["pooled"]
    assert abs(est["coef"]) < 0.01
    assert abs(did.placebo(fw, "Uber/Lyft")["coef"]) < 0.01


def test_event_study_is_flat_before_and_shows_the_effect_after():
    fw = _flow_week(effect=-0.10, seed=2)
    es, test = did.event_study(did.yoy_panel(fw, "Uber/Lyft"))
    pre = es[(es.rel_week < 0) & ~es.holiday]
    post = es[es.rel_week >= 0]
    assert pre.coef.abs().max() < 0.02
    assert post.coef.mean() == pytest.approx(-0.10, abs=0.01)


def test_flows_below_the_volume_floor_are_dropped():
    fw = _flow_week()
    fw.loc[fw.pu_zone == 1, "trips"] = 10.0
    panel = did.yoy_panel(fw, "Uber/Lyft")
    assert not panel.index.get_level_values("flow").str.startswith("1|").any()
