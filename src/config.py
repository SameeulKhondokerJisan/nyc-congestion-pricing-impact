"""Paths, study window and assumptions."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("TLC_RAW_DIR", ROOT / "data" / "raw"))
DB_PATH = Path(os.environ.get("TLC_DB_PATH", ROOT / "data" / "processed" / "tlc.duckdb"))
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"
RESULTS_JSON = REPORTS / "results.json"
TABLEAU_DIR = ROOT / "dashboards" / "tableau"
TABLEAU_DATA = TABLEAU_DIR / "data"
EXCEL_PATH = ROOT / "excel" / "trip_unit_economics.xlsx"

# Two seasons of six months. The toll began at 00:00 on Sunday 5 January 2025; the comparison season is
# aligned 52 weeks earlier (Sunday 7 January 2024), so weekdays and the Christmas and New Year weeks line up.
SEASONS = {"2023-24": {"start": "2023-10-01", "end": "2024-04-01", "toll": "2024-01-07"},
           "2024-25": {"start": "2024-10-01", "end": "2025-04-01", "toll": "2025-01-05"}}
BASE, TOLL_SEASON = "2023-24", "2024-25"
TOLL_START = SEASONS[TOLL_SEASON]["toll"]
REL_WEEKS = (-13, 11)               # full Sunday-Saturday weeks: 13 before and 12 after the (aligned) start
THANKSGIVING_WEEKS = [-7, -6]       # Thanksgiving is in week -7 of 2023-24 but week -6 of 2024-25: misaligned
HOLIDAY_WEEKS = [-7, -6, -3, -2, -1]  # Thanksgiving, pre-Christmas, Christmas and New Year weeks
PLACEBO_REL_WEEK = -5               # fake start (1 Dec 2024), using pre-period weeks without Thanksgiving
MIN_WEEKLY_TRIPS = 50               # flows below this pre-period weekly average are left out of the panel

SERVICES = {"Uber/Lyft": 1.50, "Yellow taxi": 0.75}       # per-trip congestion charge paid by the passenger
TREATED_GROUPS = ["Within zone", "Into zone", "Out of zone"]
CONTROL_GROUPS = ["Manhattan, outside zone", "Elsewhere"]

# Published reference (MTA press release, 5 January 2026): 11% fewer vehicles entered the zone in year one.
MTA_VEHICLE_REDUCTION = 0.11
