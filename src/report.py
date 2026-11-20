"""Render README.md and reports/memo.md from reports/results.json (numbers never typed by hand)."""
from __future__ import annotations

from src import config


def _p(x: float, d: int = 1, sign: bool = False) -> str:
    return f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def _ci(r: dict, d: int = 1) -> str:
    return f"95% CI {_p(r['effect_pct_low'], d, True)} to {_p(r['effect_pct_high'], d, True)}"


def _usd(x: float, d: int = 2, sign: bool = False) -> str:
    s = f"${abs(x):,.{d}f}"
    return (("+" if x >= 0 else "-") + s) if sign else s


def render(results: dict) -> None:
    f, y = results["estimates"]["Uber/Lyft"], results["estimates"]["Yellow taxi"]
    ft, yt = f["trips"]["pooled"], y["trips"]["pooled"]
    m, sp, ysp = f["money"], f["speed"], y["speed"]
    b = results["business"]
    ue = {(r["season"], r["service"], r["touches_zone"], r["period"]): r for r in results["unit_economics"]}
    s1 = config.TOLL_SEASON
    before, after = ue[(s1, "Uber/Lyft", True, "Before")], ue[(s1, "Uber/Lyft", True, "After")]
    fee = {(r["service"], r["trip_group"]): r["share_with_cbd_fee"] for r in results["cbd_fee_share_after"]}
    spp = results["speed_by_toll_period"]
    n_trips = b["clean_trips"]
    sig = lambda r: r["effect_pct_low"] > 0 or r["effect_pct_high"] < 0  # noqa: E731
    fpl, ypl = f["placebo"], y["placebo"]
    pre_f = f["pre_trend_test"]["max_abs_regular_pre_pct"]
    elasticity = f.get("implied_price_elasticity")

    trips_line = (
        f"**Ride-hail demand for zone trips barely moved.** Uber/Lyft trips to, from and within the zone changed by "
        f"{_p(ft['effect_pct'], 1, True)} relative to trips with no end in the zone, net of last year's seasonal "
        f"change ({_ci(ft)}). "
        + ("The interval includes zero. " if not sig(ft) else "")
        + f"For scale, the MTA reports {_p(results['mta_vehicle_reduction'], 0)} fewer vehicles entering the zone in the "
          f"toll's first year: ride-hail trips pay a $1.50 charge, not the $9 car toll, so their volume fell far less.")
    speed_line = (
        f"**Trips inside the zone got faster.** Uber/Lyft trips with both ends in the zone sped up "
        f"{_p(sp['effect_pct'], 1)} relative to trips inside Manhattan north of 60th Street, net of last year "
        f"({_ci(sp)}); average speed went from {sp['mph_treated_before']:.1f} to {sp['mph_treated_after']:.1f} mph. "
        f"Yellow taxis show the same gain ({_p(ysp['effect_pct'], 1)}). The gain is "
        f"{spp['toll_peak_hours_pts'] * 100:.1f} points in tolled peak hours against "
        f"{spp['overnight_hours_pts'] * 100:.1f} overnight.")
    price_line = (
        f"**Riders paid {_usd(m['passenger_cost_per_trip']['coef'])} more per zone trip, not $1.50.** The zone charge "
        f"added {_usd(m['cbd_fee_per_trip']['coef'])} per trip, but base fares fell "
        f"{_usd(-m['base_fare_per_trip']['coef'])} relative to other trips (net of last year), because faster trips "
        f"take less time and both Uber/Lyft fares and TLC driver-pay rules include a per-minute component.")
    driver_line = (
        f"**Drivers earned less per trip but more per hour.** Driver pay per zone trip fell "
        f"{_usd(-m['driver_pay_per_trip']['coef'])} ({_usd(m['driver_pay_per_trip']['ci_low'], sign=True)} to "
        f"{_usd(m['driver_pay_per_trip']['ci_high'], sign=True)}), while pay per hour on trip rose "
        f"{_usd(m['driver_pay_per_hour']['coef'])} ({_usd(m['driver_pay_per_hour']['ci_low'], sign=True)} to "
        f"{_usd(m['driver_pay_per_hour']['ci_high'], sign=True)}) from a base of "
        f"{_usd(m['driver_pay_per_hour']['treated_pre_mean_s1'], 0)} per hour.")
    taxi_line = (
        f"**Yellow taxis: no clear change in zone trips.** The estimate is {_p(yt['effect_pct'], 1, True)} ({_ci(yt)}), "
        f"but a placebo start date in December gives {_p(ypl['effect_pct'], 1, True)}, so this is not evidence of riders "
        f"switching to the cheaper $0.75 taxi charge.")
    design_line = (
        f"**A single-season before/after comparison would mislead.** Comparing Jan-Mar 2025 with Oct-Dec 2024 alone "
        f"puts the speed gain at {_p(sp['single_season_effect_pct'], 1)} (double the estimate net of last year) and "
        f"fails a placebo test ({_p(f['single_season']['placebo']['effect_pct'], 1, True)} 'effect' at a fake start "
        f"date), because Manhattan's holiday season moves zone trips differently. Using Oct-Mar 2023-24 as the "
        f"seasonal baseline fixes this: the placebo gives {_p(fpl['effect_pct'], 1, True)} (p = {fpl['p_value']:.2f}).")
    findings = [trips_line, speed_line, price_line, driver_line, taxi_line, design_line]
    recs = [
        "Do not cut Uber/Lyft fares to offset the zone charge: zone trip volume held up, and riders' net price rose by "
        "less than half the charge because faster trips cost less.",
        "Use the faster zone trips in driver supply messages: pay per hour on zone trips rose, so zone-specific "
        "driver bonuses are not needed to keep supply.",
        "Review the time-based part of the fare and driver pay formulas: faster trips cut base fares by about "
        f"{_usd(-m['base_fare_per_trip']['coef'])} per zone trip.",
        "Refresh the analysis as TLC publishes new months (about two months' delay) and watch the event study for a "
        "delayed demand response.",
    ]
    elast_txt = (f"{elasticity:.2f}" if elasticity is not None else "n/a")
    readme = f"""# Congestion Pricing and New York Taxi and Ride-Hail Trips

**How did Manhattan's congestion toll change trips, speeds, fares and driver pay inside and outside the zone?**
New York started charging vehicles entering Manhattan south of 60th Street (the Congestion Relief Zone) on
5 January 2025; Uber/Lyft riders pay $1.50 and yellow taxi riders $0.75 per trip to, from, within or through the
zone. This project cleans {n_trips / 1e6:,.0f} million TLC trip records (Oct-Mar 2024-25 and the same months a
year earlier), and estimates the toll's effect with a difference-in-differences design that uses last year as the
seasonal baseline. Written for a ride-hail operator setting prices and driver incentives.

**Tools:** SQL (DuckDB over 24 Parquet files, window functions) · Python (pandas, linearmodels, statsmodels,
GeoPandas) · Statistics (difference-in-differences with flow and week fixed effects, event study, placebo test,
clustered and Newey-West standard errors) · Excel (unit economics and toll scenarios) · Tableau (zone map,
heatmap, event study)

![Event study](reports/figures/02_event_study_trips.png)

## Findings

""" + "\n".join(f"{i}. {t}" for i, t in enumerate(findings, 1)) + """

![Speed by hour](reports/figures/04_speed_change_heatmap.png)

![Price per trip](reports/figures/06_price_breakdown.png)

## Recommendations

""" + "\n".join(f"{i}. {t}" for i, t in enumerate(recs, 1)) + f"""

## Deliverables

| Deliverable | Where |
|---|---|
| Tableau dashboard: zone map, speed heatmap, event study, daily trips, price per trip | `dashboards/tableau/congestion_pricing_impact.twbx` |
| Excel model: unit economics before and after, toll scenarios with the measured price response ({elast_txt}) | `excel/trip_unit_economics.xlsx` |
| Analysis notebook with outputs | `notebooks/congestion_pricing_analysis.ipynb` |
| One-page memo | `reports/memo.md` |
| SQL: Parquet view, cleaning rules, aggregates, panels | `sql/` |
| Result tables and figures | `reports/tables/`, `reports/figures/` |

![Tableau dashboard](dashboards/tableau/dashboard_preview.png)

## How it works

1. **Cleaning** (`sql/02-04`): one DuckDB view reads the 24 monthly Parquet files in place
   ({b['rows_read'] / 1e6:,.1f} million rows). Rules drop trips outside the study windows, under a minute or over three
   hours, with zero or 100+ miles, implausible speeds, unknown zones or non-positive fares; {_p(b['rows_kept'] / b['rows_read'])}
   of rows pass ([`docs/data_quality_log.md`](docs/data_quality_log.md)). Kept trips are aggregated in one pass to
   season x service x date x hour x pickup zone x trip group.
2. **Trip groups**: the MTA's list of the {b['cbd_zones']} taxi zones inside the Congestion Relief Zone sorts every trip
   into within, into, out of, upper Manhattan, or elsewhere. In Jan-Mar 2025, {_p(fee[('Uber/Lyft', 'Within zone')])} of
   Uber/Lyft trips within the zone carry the charge, against {_p(fee[('Uber/Lyft', 'Elsewhere')])} of trips elsewhere
   (trips passing through), which confirms the grouping.
3. **Design** (`src/did.py`): each flow (pickup zone x trip group) is compared with the same week a year earlier
   (weeks aligned 52 weeks apart), then flows touching the zone are compared with other flows before and after
   5 January: flow and week fixed effects, weights by pre-period volume, standard errors clustered by pickup zone.
   Thanksgiving falls in different weeks in the two seasons, so those two weeks are left out of the main estimate.
4. **Checks**: event study by week, a placebo start date in December, all-weeks and unweighted versions, and the
   naive single-season design for comparison. Regular pre-period weeks stay within {_p(pre_f, 1)} of their average
   for Uber/Lyft; holiday weeks move more, so effects of a few percent cannot be separated from weekly noise.
5. **Speeds**: daily distance-weighted speed inside the zone against upper Manhattan, as a year-over-year
   difference, regressed on the post period with Newey-West standard errors.
6. **Business tools**: Excel unit economics and toll scenarios (formulas over pasted results); Tableau workbook
   generated by `src/tableau_workbook.py` with Hyper extracts.

Details: [`docs/methodology.md`](docs/methodology.md) · data dictionary: [`docs/data_dictionary.md`](docs/data_dictionary.md)

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make all        # download 6.6 GB of Parquet, build the warehouse, run the analysis, notebook and tests
```

## Project structure

```
├── data/                 raw/ and processed/ (git-ignored); README with sources
├── sql/                  DuckDB SQL: zones, Parquet view, quality rules, aggregates, panels, unit economics
├── src/                  pipeline: data, DiD, figures, zones, Excel, Tableau, report
├── notebooks/            executed analysis notebook
├── excel/                trip unit economics and toll scenarios
├── dashboards/tableau/   .twbx workbook, CSV extracts, preview
├── reports/              results.json, memo, figures, tables
├── docs/                 methodology, data dictionary, data quality log
└── tests/                pytest suite
```

## Data

* NYC Taxi & Limousine Commission, [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page):
  yellow taxi and high-volume for-hire (Uber, Lyft) trips, Oct 2023-Mar 2024 and Oct 2024-Mar 2025, plus the taxi
  zone lookup and zone shapefile.
* MTA, [Central Business District Taxi Zones](https://data.ny.gov/d/yfdc-w5jh) (data.ny.gov dataset yfdc-w5jh).
* Charges: MTA, [Taxis and For-Hire Vehicles](https://www.mta.info/fares-tolls/tolls/congestion-relief-zone/taxi-fhv-tolls).
  Vehicle reduction for comparison: MTA press release, 5 January 2026.

Raw files are downloaded by `make data` and are not stored in this repository.

## Assumptions and limits

* Trips are classified by pickup and dropoff zone. Trips that pass through the zone without stopping pay the
  charge but count as "elsewhere", which slightly dilutes the estimates.
* The design assumes that, without the toll, zone and non-zone trips would have changed from autumn to winter as
  they did a year earlier. Other changes between the two years that hit zone trips differently would bias the result.
* Speeds are trip averages (distance / time), not road-segment speeds.
* Driver pay is reported for Uber/Lyft only. Tips are excluded from rider totals.
"""
    (config.ROOT / "README.md").write_text(readme)
    memo = ("# Memo: what congestion pricing did to ride-hail trips in Manhattan\n\n**To:** Head of Pricing and "
            f"Driver Operations · **Data:** {n_trips / 1e6:,.0f} million TLC trips, Oct-Mar 2023-24 and 2024-25\n\n"
            "**What we found**\n\n" + "\n".join(f"- {t}" for t in findings) + "\n\n**What to do**\n\n"
            + "\n".join(f"{i}. {t}" for i, t in enumerate(recs, 1))
            + "\n\n**Caveats:** observational design using last year as the baseline; trips through the zone without "
              "stopping are not identified; effects of a few percent are within weekly noise.\n")
    (config.REPORTS / "memo.md").write_text(memo)
