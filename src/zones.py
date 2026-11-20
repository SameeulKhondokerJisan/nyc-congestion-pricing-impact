"""Taxi-zone geometry: centroids in latitude/longitude (for Tableau) and a choropleth helper (for figures)."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src import config


def zone_shapes() -> gpd.GeoDataFrame:
    """TLC taxi zones (NY State Plane, feet) with LocationID; the zip is read in place."""
    shp = gpd.read_file(f"zip://{(config.RAW_DIR / 'reference' / 'taxi_zones.zip').as_posix()}!taxi_zones/taxi_zones.shp")
    return shp.rename(columns={"LocationID": "zone_id"})[["zone_id", "geometry"]].dissolve(by="zone_id").reset_index()


def centroids() -> pd.DataFrame:
    """One row per zone: centroid computed in the projected CRS, then converted to WGS84 lat/lon."""
    shp = zone_shapes()
    pts = gpd.GeoSeries(shp.geometry.centroid, crs=shp.crs).to_crs(4326)
    return pd.DataFrame({"zone_id": shp.zone_id.astype(int), "lat": pts.y.round(6), "lon": pts.x.round(6)})
