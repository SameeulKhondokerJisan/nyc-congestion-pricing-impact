"""Generate the Tableau dashboard (dashboards/tableau/congestion_pricing_impact.twbx).

Writes small CSV extracts to dashboards/tableau/data/ and packages them as Hyper extracts in a .twbx:
a zone map (zone centroids with geographic roles), an hour x weekday heatmap, the event study, daily trips
against last year, and the price breakdown per trip.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from src.twb import Dashboard, DataSource, Field, Worksheet, Zone, save

S0, S1 = config.BASE, config.TOLL_SEASON
WEEKDAY = {1: "1 Mon", 2: "2 Tue", 3: "3 Wed", 4: "4 Thu", 5: "5 Fri", 6: "6 Sat", 0: "7 Sun"}


def _extracts(zchange, heat, es_all, group_day, unit, centroids) -> dict[str, pd.DataFrame]:
    d = config.TABLEAU_DATA
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    if centroids is not None:
        z = zchange.merge(centroids, on="zone_id", how="inner")
        z = z[z.trips_per_day_pre >= 50].copy()
        z["area"] = np.where(z.in_cbd, "Congestion Relief Zone", "Outside the zone")
        out["zone_map"] = z[["zone_id", "zone", "borough", "area", "lat", "lon", "trips_per_day_pre",
                             f"trips_per_day_post_{S1}", "change_net", "mph_change_net"]].rename(
            columns={f"trips_per_day_post_{S1}": "trips_per_day_post"})
    h = heat.copy()
    h["weekday"] = h.dow.map(WEEKDAY)
    out["speed_heatmap"] = h[["weekday", "pickup_hour", "relative_change_net"]].rename(
        columns={"pickup_hour": "hour", "relative_change_net": "speed_gain"})
    rows = []
    for r in es_all.itertuples():
        for series, col in (("Estimate", "coef"), ("95% CI low", "ci_low"), ("95% CI high", "ci_high")):
            rows.append({"service": r.service, "rel_week": int(r.rel_week), "series": series,
                         "change": float(np.exp(getattr(r, col)) - 1)})
    out["event_study"] = pd.DataFrame(rows)
    g = group_day[group_day.service == "Uber/Lyft"].copy()
    g["kind"] = np.where(g.trip_group.isin(config.TREATED_GROUPS), "Touches zone", "No end in zone")
    t = g.groupby(["season", "kind", "rel_day"]).trips.sum().unstack(["season", "kind"]).sort_index()
    idx = (t.rolling(7, center=True).mean() / t[t.index < 0].mean() * 100).stack(["season", "kind"], future_stack=True)
    daily = idx.rename("index").reset_index().dropna()
    daily["date"] = (pd.Timestamp(config.TOLL_START) + pd.to_timedelta(daily.rel_day, unit="D")).dt.strftime("%Y-%m-%d")
    daily["series"] = daily.kind + ", " + daily.season
    out["daily_trips"] = daily[["date", "series", "index"]]
    u = unit[(unit.season == S1) & unit.touches_zone & (unit.service == "Uber/Lyft")]
    comp = {"base_fare": "1 Base fare", "other_fees": "2 Taxes and other fees", "ny_surcharge": "3 NYS surcharge",
            "tolls": "4 Tolls", "cbd_fee": "5 Congestion zone charge", "driver_pay": "6 Driver pay"}
    rows = [{"period": "Oct-Dec 2024" if r.period == "Before" else "Jan-Mar 2025", "component": label,
             "usd": float(getattr(r, col))} for r in u.itertuples() for col, label in comp.items()]
    out["price_per_trip"] = pd.DataFrame(rows)
    for name, frame in out.items():
        frame.to_csv(d / f"{name}.csv", index=False)
    return out


def build(zchange, heat, es_all, group_day, unit, centroids) -> dict:
    ex = _extracts(zchange, heat, es_all, group_day, unit, centroids)
    d = config.TABLEAU_DATA
    sources, sheets, zones = [], [], []
    if "zone_map" in ex:
        zm = DataSource.from_csv(
            "zone_map", "Zone change", d / "zone_map.csv", dims=("zone_id",),
            captions={"change_net": "Change in pickups, net of last year", "trips_per_day_pre": "Pickups per day (before)",
                      "mph_change_net": "Speed change, net of last year", "lat": "Latitude", "lon": "Longitude"},
            formats={"change_net": "p0.0%", "mph_change_net": "p0.0%", "trips_per_day_pre": "n#,##0"},
            roles={"lat": "[Geographical].[Latitude]", "lon": "[Geographical].[Longitude]"})
        sources.append(zm)
        sheets.append(Worksheet("Zone map", zm, rows=[Field("lat", "avg")], cols=[Field("lon", "avg")], mark="Circle",
                                detail=[Field("zone_id"), Field("zone"), Field("borough")],
                                color=Field("change_net", "avg"), size=Field("trips_per_day_pre", "sum"),
                                tooltip=[Field("mph_change_net", "avg")],
                                title="Uber/Lyft pickups by zone: change after 5 Jan, net of last year"))
    hm = DataSource.from_csv("heatmap", "Speed by hour", d / "speed_heatmap.csv", dims=("hour",),
                             captions={"speed_gain": "Speed gain vs upper Manhattan, net of last year",
                                       "weekday": "Weekday", "hour": "Pickup hour"},
                             formats={"speed_gain": "p0.0%"})
    es = DataSource.from_csv("event", "Event study", d / "event_study.csv",
                             captions={"change": "Trips touching the zone vs other trips", "rel_week": "Weeks since toll",
                                       "series": "Line"}, formats={"change": "p0%"})
    es.column("rel_week").role, es.column("rel_week").type = "dimension", "quantitative"
    dt = DataSource.from_csv("daily", "Daily trips", d / "daily_trips.csv",
                             captions={"index": "Trips per day (pre-period = 100)", "series": "Trips, season",
                                       "date": "Date (last season aligned 52 weeks later)"},
                             formats={"index": "n#,##0"})
    pp = DataSource.from_csv("price", "Price per trip", d / "price_per_trip.csv",
                             captions={"usd": "Dollars per trip", "component": "Component", "period": "Period"},
                             formats={"usd": 'c"$"#,##0.00'})
    sources += [hm, es, dt, pp]
    sheets += [
        Worksheet("Speed by hour", hm, rows=[Field("weekday")], cols=[Field("hour")], mark="Square",
                  color=Field("speed_gain", "avg"), title="Speed gain inside the zone vs upper Manhattan, net of last year"),
        Worksheet("Event study", es, rows=[Field("service"), Field("change", "sum")],
                  cols=[Field("rel_week", kind="qk")], mark="Line", color=Field("series"),
                  title="Trips to, from and within the zone vs other trips, net of last year (95% CI)"),
        Worksheet("Daily trips", dt, rows=[Field("index", "sum")], cols=[Field("date", kind="qk")], mark="Line",
                  color=Field("series"), title="Uber/Lyft trips per day, this season and last (7-day average)"),
        Worksheet("Price per trip", pp, rows=[Field("component"), Field("period")], cols=[Field("usd", "sum")],
                  mark="Bar", color=Field("period"), text=Field("usd", "sum"), show_labels=True,
                  title="Uber/Lyft trips touching the zone: rider price and driver pay per trip"),
    ]
    zones += [Zone(16, 6, 1100, 34, text="Congestion pricing and New York taxi and ride-hail trips", font_size=18,
                   bold=True),
              Zone(16, 40, 1360, 22, text="TLC trip records, Oct-Mar 2024-25 against Oct-Mar 2023-24. Effects compare "
                                          "trips touching the Congestion Relief Zone with other trips, net of last year.",
                   font_size=10)]
    if "zone_map" in ex:
        zones += [Zone(16, 66, 600, 420, sheet="Zone map"),
                  Zone(16, 488, 600, 50, legend_sheet="Zone map", legend_field=f"[{sources[0].name}].[avg:change_net:qk]")]
    zones += [Zone(630, 66, 640, 210, sheet="Speed by hour"),
              Zone(1275, 66, 110, 190, legend_sheet="Speed by hour", legend_field=f"[{hm.name}].[avg:speed_gain:qk]"),
              Zone(630, 280, 640, 260, sheet="Event study"),
              Zone(1275, 280, 110, 90, legend_sheet="Event study", legend_field=f"[{es.name}].[none:series:nk]"),
              Zone(16, 546, 520, 346, sheet="Daily trips"),
              Zone(540, 560, 170, 110, legend_sheet="Daily trips", legend_field=f"[{dt.name}].[none:series:nk]"),
              Zone(716, 546, 668, 346, sheet="Price per trip")]
    dashboard = Dashboard("Congestion pricing impact", 1400, 900, zones)
    twbx = save(config.TABLEAU_DIR / "congestion_pricing_impact.twbx", sources, sheets, [dashboard])
    return {"twbx": str(twbx.relative_to(config.ROOT)), "sheets": len(sheets), "sources": len(sources)}
