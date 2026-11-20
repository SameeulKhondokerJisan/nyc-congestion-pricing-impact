"""Static charts (matplotlib, GeoPandas) for the README, memo and notebook."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

from src import config  # noqa: E402

BLUE, ORANGE, GREEN, GREY, RED, PURPLE = "#2b6cb0", "#c05621", "#2f855a", "#a0aec0", "#c53030", "#6b46c1"
S0, S1 = config.BASE, config.TOLL_SEASON
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10})


def _save(fig, name: str) -> str:
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(config.FIGURES / name, bbox_inches="tight")
    plt.close(fig)
    return f"reports/figures/{name}"


def daily_trips(group_day: pd.DataFrame, service: str = "Uber/Lyft") -> str:
    """Trips touching the zone and other trips, this season and last, indexed to each season's pre-period."""
    d = group_day[group_day.service == service].copy()
    d["kind"] = np.where(d.trip_group.isin(config.TREATED_GROUPS), "Touches zone", "No end in zone")
    t = d.groupby(["season", "kind", "rel_day"]).trips.sum().unstack(["season", "kind"]).sort_index()
    idx = t.rolling(7, center=True).mean() / t[t.index < 0].mean() * 100
    fig, ax = plt.subplots(figsize=(10, 3.8))
    styles = {("Touches zone", S1): (RED, "-", 1.8), ("No end in zone", S1): (BLUE, "-", 1.8),
              ("Touches zone", S0): (RED, ":", 1.2), ("No end in zone", S0): (BLUE, ":", 1.2)}
    for (kind, season), (color, ls, lw) in styles.items():
        ax.plot(idx.index, idx[(season, kind)], color=color, ls=ls, lw=lw, label=f"{kind}, {season}")
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.text(0, ax.get_ylim()[1], " toll starts (2024-25)", va="top", fontsize=8)
    ax.axhline(100, color=GREY, lw=0.6)
    ax.set_xlabel("Days since 5 Jan 2025 (2024-25) or 7 Jan 2024 (2023-24)")
    ax.set_ylabel("Trips per day, 7-day average\n(each season's pre-period = 100)")
    ax.set_title(f"{service} trips by relation to the Congestion Relief Zone, this season and last",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="lower left")
    return _save(fig, "01_daily_trips_vs_last_year.png")


def event_study(es: dict[str, pd.DataFrame]) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.9))
    for (service, df), color, shift in zip(es.items(), (BLUE, ORANGE), (-0.12, 0.12)):
        for holiday, face in ((False, color), (True, "white")):
            d = df[df.holiday == holiday]
            y, lo, hi = (np.exp(d[c]) - 1 for c in ("coef", "ci_low", "ci_high"))
            ax.errorbar(d.rel_week + shift, y * 100, yerr=[(y - lo) * 100, (hi - y) * 100], fmt="o", ms=4,
                        color=color, mfc=face, capsize=2, lw=1,
                        label=service if not holiday else None)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(-0.5, color="black", lw=0.8, ls="--")
    ax.set_xlabel("Weeks since the toll started (hollow = Thanksgiving, Christmas and New Year weeks)")
    ax.set_ylabel("Trips touching the zone vs. other\ntrips, net of last year (%)")
    ax.set_title("Event study: trips to, from and within the zone, relative to regular pre-period weeks (95% CI)",
                 fontweight="bold", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, "02_event_study_trips.png")


def zone_change_table(zone_period: pd.DataFrame, service: str = "Uber/Lyft") -> pd.DataFrame:
    """Per zone: after/before change in pickups this season, last season and net of last season."""
    z = zone_period[zone_period.service == service].pivot_table(
        index=["zone_id", "zone", "borough", "in_cbd"], columns="season",
        values=["trips_per_day_pre", "trips_per_day_post", "mph_pre", "mph_post"]).reset_index()
    z.columns = ["_".join(c for c in col if c) for col in z.columns]
    for s in (S0, S1):
        z[f"change_{s}"] = z[f"trips_per_day_post_{s}"] / z[f"trips_per_day_pre_{s}"] - 1
        z[f"mph_change_{s}"] = z[f"mph_post_{s}"] / z[f"mph_pre_{s}"] - 1
    z["change_net"] = (1 + z[f"change_{S1}"]) / (1 + z[f"change_{S0}"]) - 1
    z["mph_change_net"] = (1 + z[f"mph_change_{S1}"]) / (1 + z[f"mph_change_{S0}"]) - 1
    z["trips_per_day_pre"] = z[f"trips_per_day_pre_{S1}"]
    return z


def zone_map(zchange: pd.DataFrame, shapes, service: str = "Uber/Lyft") -> str:
    g = shapes.merge(zchange[["zone_id", "change_net", "in_cbd", "trips_per_day_pre"]], on="zone_id", how="left")
    g["pct"] = g.change_net * 100
    g.loc[g.trips_per_day_pre < 50, "pct"] = np.nan             # too few trips to read a change
    fig, ax = plt.subplots(figsize=(7.5, 8))
    lim = np.nanpercentile(np.abs(g.pct), 95)
    g.plot(column="pct", ax=ax, cmap="RdBu", norm=TwoSlopeNorm(0, -lim, lim), edgecolor="white", lw=0.2,
           legend=True, legend_kwds={"label": "Change in pickups per day after 5 Jan, net of last year (%)",
                                     "shrink": 0.6}, missing_kwds={"color": "#edf2f7"})
    g[g.in_cbd == True].dissolve().boundary.plot(ax=ax, color="black", lw=1.2)  # noqa: E712
    ax.set_axis_off()
    ax.set_title(f"{service} pickups by taxi zone: Jan-Mar vs. Oct-Dec, 2024-25 relative to 2023-24\n"
                 "(black outline = Congestion Relief Zone; grey = under 50 pickups a day)", fontsize=10,
                 fontweight="bold")
    return _save(fig, "03_zone_map_change.png")


def speed_heatmap_table(hour_weekday: pd.DataFrame, service: str = "Uber/Lyft") -> pd.DataFrame:
    """Per weekday x hour: speed change inside the zone minus upper Manhattan, net of last year (pts)."""
    h = hour_weekday[hour_weekday.service == service]
    p = h.pivot_table(index=["dow", "weekday", "pickup_hour"], columns=["season", "trip_group", "post"],
                      values="mph")
    out = p.index.to_frame(index=False)
    def chg(season, group):
        return (p[(season, group, True)] / p[(season, group, False)] - 1).to_numpy()
    rel_s1 = chg(S1, "Within zone") - chg(S1, "Manhattan, outside zone")
    rel_s0 = chg(S0, "Within zone") - chg(S0, "Manhattan, outside zone")
    out["within_change_s1"] = chg(S1, "Within zone")
    out["relative_change_s1"] = rel_s1
    out["relative_change_net"] = rel_s1 - rel_s0
    return out


def speed_heatmap(table: pd.DataFrame) -> str:
    rel = table.pivot(index="dow", columns="pickup_hour", values="relative_change_net") * 100
    order = [1, 2, 3, 4, 5, 6, 0]                                 # Monday first (dayofweek: Sunday = 0)
    rel = rel.reindex(order)
    names = table.drop_duplicates("dow").set_index("dow").weekday.reindex(order)
    fig, ax = plt.subplots(figsize=(10, 3.6))
    lim = np.nanmax(np.abs(rel.to_numpy()))
    im = ax.imshow(rel.to_numpy(), cmap="RdBu", norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.set_yticks(range(len(names)), [n[:3] for n in names])
    ax.set_xticks(range(0, 24, 2), [f"{x:02d}" for x in range(0, 24, 2)])
    ax.set_xlabel("Pickup hour")
    fig.colorbar(im, ax=ax, label="Percentage points")
    ax.set_title("Speed gain inside the zone relative to upper Manhattan, net of last year, by weekday and hour",
                 fontweight="bold", fontsize=10)
    return _save(fig, "04_speed_change_heatmap.png")


def speed_by_week(weekly: dict[str, pd.DataFrame]) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.4))
    for (service, df), color in zip(weekly.items(), (BLUE, ORANGE)):
        ax.plot(df.rel_week, df.pct_vs_pre * 100, marker="o", ms=4, color=color, label=service)
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(-0.5, color="black", lw=0.8, ls="--")
    ax.set_xlabel("Weeks since the toll started")
    ax.set_ylabel("Speed gap vs. pre-period,\nnet of last year (%)")
    ax.set_title("Trip speed inside the zone relative to upper Manhattan, by week", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, "05_speed_gap_by_week.png")


def price_breakdown(unit: pd.DataFrame, service: str = "Uber/Lyft") -> str:
    u = unit[(unit.service == service) & unit.touches_zone & (unit.season == S1)].set_index("period").reindex(
        ["Before", "After"])
    comps = [("base_fare", "Base fare", BLUE), ("other_fees", "Taxes and other fees", GREY),
             ("ny_surcharge", "NYS congestion surcharge", PURPLE), ("tolls", "Bridge and tunnel tolls", GREEN),
             ("cbd_fee", "Congestion Relief Zone charge", RED)]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    left = np.zeros(2)
    labels = ["Oct-Dec 2024", "Jan-Mar 2025"]
    for col, label, color in comps:
        ax.barh(labels, u[col], left=left, color=color, label=label)
        left += u[col].to_numpy()
    for i, (tot, pay) in enumerate(zip(u.passenger_cost, u.driver_pay)):
        ax.text(tot + 0.3, i, f"\\${tot:.2f} paid by rider; driver earns \\${pay:.2f}", va="center", fontsize=8)
    ax.set_xlim(0, left.max() * 1.6)
    ax.set_xlabel("Dollars per trip (excluding tips)")
    ax.set_title(f"What a rider pays per {service} trip touching the zone", fontweight="bold")
    ax.legend(frameon=False, fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    return _save(fig, "06_price_breakdown.png")
