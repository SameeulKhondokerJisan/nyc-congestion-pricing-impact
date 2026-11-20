"""Create notebooks/congestion_pricing_analysis.ipynb (executed by `make notebook`)."""
import nbformat as nbf

from src import config

CELLS = [
    ("md", "# Congestion pricing and New York taxi and ride-hail trips\nWalk-through of the analysis behind the README. "
           "SQL runs live against the DuckDB warehouse built by `src/run_pipeline.py`; estimates are read from "
           "`reports/results.json`."),
    ("code", "import os, sys, json, pathlib\nROOT = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == 'notebooks' "
             "else pathlib.Path.cwd()\nos.chdir(ROOT); sys.path.insert(0, str(ROOT))\nimport pandas as pd\n"
             "from IPython.display import Image, Markdown, display\nfrom src import config, data\n"
             "pd.set_option('display.float_format', lambda x: f'{x:,.4f}')\npd.set_option('display.width', 160)\n"
             "results = json.loads(config.RESULTS_JSON.read_text())\nT = lambda name: pd.read_csv(f'reports/tables/{name}.csv')"),
    ("md", "## 1. Data and cleaning\nRows read and kept per service and month (`sql/03_quality_checks.sql`)."),
    ("code", "q = T('quality_checks')\nq.groupby('service')[['rows_read', 'rows_kept']].sum().assign(kept_share=lambda d: d.rows_kept / d.rows_read)"),
    ("code", "data.row_counts()"),
    ("md", "The 38 taxi zones in the Congestion Relief Zone, and how often each trip group carries the charge in Jan-Mar 2025."),
    ("code", "display(data.query('SELECT zone_id, zone FROM zones WHERE in_cbd ORDER BY zone_id').head(10))\nT('cbd_fee_share_after')"),
    ("md", "## 2. Trips this season and last"),
    ("code", "display(Image(filename='reports/figures/01_daily_trips_vs_last_year.png'))"),
    ("code", "cols = ['service', 'trip_group'] + [c for c in T('group_period_summary').columns if c.startswith('trips_')]\n"
             "T('group_period_summary')[cols]"),
    ("md", "## 3. Difference-in-differences on trips\nYear-over-year change per flow, flow and week fixed effects, "
           "weights by pre-period volume, standard errors clustered by pickup zone."),
    ("code", "rows = []\nfor s, e in results['estimates'].items():\n"
             "    for label, r in [('main (no Thanksgiving weeks)', e['trips']['pooled']), ('all weeks', e['trips_all_weeks']),\n"
             "                     ('unweighted', e['trips_unweighted']), ('placebo, fake start 1 Dec', e['placebo']),\n"
             "                     ('single season (naive)', e['single_season']['estimate']),\n"
             "                     ('single season placebo', e['single_season']['placebo'])]:\n"
             "        rows.append({'service': s, 'estimate': label, 'effect_pct': r['effect_pct'], 'ci_low': r['effect_pct_low'],\n"
             "                     'ci_high': r['effect_pct_high'], 'p_value': r['p_value']})\npd.DataFrame(rows)"),
    ("code", "display(Image(filename='reports/figures/02_event_study_trips.png'))\n"
             "{s: e['pre_trend_test'] for s, e in results['estimates'].items()}"),
    ("code", "display(Image(filename='reports/figures/03_zone_map_change.png'))\n"
             "T('zone_change').sort_values('trips_per_day_pre', ascending=False)[['zone', 'borough', 'in_cbd', 'trips_per_day_pre', 'change_net']].head(10)"),
    ("md", "## 4. Speeds"),
    ("code", "{s: {k: v for k, v in e['speed'].items() if k not in ('treated', 'control')} for s, e in results['estimates'].items()}"),
    ("code", "display(Image(filename='reports/figures/04_speed_change_heatmap.png'))\n"
             "display(Image(filename='reports/figures/05_speed_gap_by_week.png'))\nresults['speed_by_toll_period']"),
    ("md", "## 5. Money per trip"),
    ("code", "pd.DataFrame(results['estimates']['Uber/Lyft']['money']).T"),
    ("code", "display(Image(filename='reports/figures/06_price_breakdown.png'))\nT('unit_economics')"),
    ("md", "## 6. Memo"),
    ("code", "display(Markdown(open('reports/memo.md').read()))"),
]


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in CELLS]
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nbf.write(nb, config.ROOT / "notebooks" / "congestion_pricing_analysis.ipynb")


if __name__ == "__main__":
    main()
