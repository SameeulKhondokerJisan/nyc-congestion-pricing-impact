"""The recalculated Excel model is internally consistent (skipped until the workbook has cached values)."""
import json

import pytest
from openpyxl import load_workbook

from src import config

pytestmark = pytest.mark.skipif(not config.EXCEL_PATH.exists() or not config.RESULTS_JSON.exists(),
                                reason="run `make pipeline` first")


def test_unit_economics_match_results():
    wb = load_workbook(config.EXCEL_PATH, data_only=True)
    ws = wb["Unit economics"]
    if ws["B9"].value is None:
        pytest.skip("workbook not recalculated yet")
    r = json.loads(config.RESULTS_JSON.read_text())
    ue = {(u["season"], u["service"], u["touches_zone"], u["period"]): u for u in r["unit_economics"]}
    before = ue[(config.TOLL_SEASON, "Uber/Lyft", True, "Before")]
    assert ws["B9"].value == pytest.approx(before["passenger_cost"], rel=1e-9)
    assert ws["B11"].value == pytest.approx(before["base_fare"] - before["driver_pay"], rel=1e-9)
    sc = wb["Toll scenarios"]
    assert sc["D6"].value == pytest.approx(before["trips_per_day"], rel=1e-9)      # no charge, no response
