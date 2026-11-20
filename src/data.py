"""Build the DuckDB warehouse from the TLC Parquet files and expose query helpers."""
from __future__ import annotations

import re

import duckdb
import pandas as pd

from src import config

_S0, _S1 = config.SEASONS[config.BASE], config.SEASONS[config.TOLL_SEASON]
PARAMS = {"s0_start": _S0["start"], "s0_end": _S0["end"], "s0_toll": _S0["toll"], "s0": config.BASE,
          "s1_start": _S1["start"], "s1_end": _S1["end"], "s1_toll": _S1["toll"], "s1": config.TOLL_SEASON,
          "w_first": config.REL_WEEKS[0], "w_last": config.REL_WEEKS[1]}


def split_statements(sql: str) -> list[str]:
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(config.DB_PATH), read_only=read_only)


def render(filename: str, **params) -> str:
    sql = (config.SQL_DIR / filename).read_text().replace("{raw}", config.RAW_DIR.as_posix())
    for key, value in {**PARAMS, **params}.items():
        sql = sql.replace("{" + key + "}", str(value))
    return sql


def run_sql(con, filename: str, **params) -> pd.DataFrame | None:
    result = None
    for statement in split_statements(render(filename, **params)):
        result = con.execute(statement)
    try:
        return result.df() if result is not None else None
    except duckdb.Error:
        return None


def build_warehouse() -> pd.DataFrame:
    """Create zones, the trips view and the cleaned aggregate. Returns the quality-check table."""
    trips = config.RAW_DIR / "trips"
    if not trips.exists() or not any(trips.glob("*.parquet")):
        raise FileNotFoundError(f"No Parquet files in {trips}. Run `python -m src.download_data` first.")
    with connect() as con:
        con.execute("SET preserve_insertion_order = false")
        run_sql(con, "01_zones.sql")
        run_sql(con, "02_trips_view.sql")
        checks = run_sql(con, "03_quality_checks.sql")
        run_sql(con, "04_trip_agg.sql")
    return checks


def query(filename_or_sql: str, **params) -> pd.DataFrame:
    with connect(read_only=True) as con:
        if filename_or_sql.endswith(".sql"):
            return run_sql(con, filename_or_sql, **params)
        return con.execute(filename_or_sql).df()


def table(name: str) -> pd.DataFrame:
    return query(f"SELECT * FROM {name}")


def row_counts() -> dict[str, int]:
    with connect(read_only=True) as con:
        return {"zones": int(con.execute("SELECT COUNT(*) FROM zones").fetchone()[0]),
                "cbd_zones": int(con.execute("SELECT COUNT(*) FROM zones WHERE in_cbd").fetchone()[0]),
                "trip_agg_rows": int(con.execute("SELECT COUNT(*) FROM trip_agg").fetchone()[0]),
                "clean_trips": int(con.execute("SELECT SUM(trips) FROM trip_agg").fetchone()[0])}
