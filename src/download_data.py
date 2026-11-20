"""Download NYC TLC trip records and zone reference files into data/raw/.

Sources (all public, no sign-in):
  * TLC Trip Record Data, https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
    monthly Parquet files served from d37ci6vzurychx.cloudfront.net
  * TLC taxi zone lookup table and zone shapefile (same host, /misc/)
  * MTA Central Business District taxi zones, data.ny.gov dataset yfdc-w5jh

Window: Oct 2024 to Mar 2025, which brackets the start of congestion pricing on
5 Jan 2025 (13 weeks before and 12 weeks after), plus the same months a year earlier
(Oct 2023 to Mar 2024) as a seasonal comparison. The raw Parquet files are about
6.6 GB in total and are git-ignored.

Usage:
    python -m src.download_data            # everything
    python -m src.download_data --small    # reference files only (for tests)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src._fetch import fetch, sha256, write_manifest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TRIP_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/{kind}_tripdata_{month}.parquet"
MONTHS = ["2023-10", "2023-11", "2023-12", "2024-01", "2024-02", "2024-03",
          "2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]
KINDS = ["fhvhv", "yellow"]
REFERENCE = {
    "taxi_zone_lookup.csv": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv",
    "taxi_zones.zip": "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip",
    "mta_cbd_taxi_zones.csv": "https://data.ny.gov/api/views/yfdc-w5jh/rows.csv?accessType=DOWNLOAD",
}


def main(small: bool = False) -> None:
    entries = []
    for name, url in REFERENCE.items():
        path = fetch(url, RAW / "reference" / name)
        entries.append({"file": f"reference/{name}", "bytes": path.stat().st_size, "sha256": sha256(path), "url": url})
        print(f"ok  {name}")
    if not small:
        for kind in KINDS:
            for month in MONTHS:
                url = TRIP_URL.format(kind=kind, month=month)
                path = fetch(url, RAW / "trips" / f"{kind}_tripdata_{month}.parquet")
                entries.append({"file": f"trips/{path.name}", "bytes": path.stat().st_size, "url": url})
                print(f"ok  {path.name:35s} {path.stat().st_size / 1e6:8.1f} MB")
    write_manifest(RAW, entries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true", help="download reference files only")
    main(small=parser.parse_args().small)
