"""Effects of congestion pricing on trips, speeds and money: difference-in-differences against last year.

Treated trips touch the Congestion Relief Zone (within, into, out of); control trips have no end in the
zone. A single-season comparison (Jan-Mar vs. Oct-Dec 2024-25) is confounded by seasonality: Manhattan's
holiday season moves zone trips differently from trips elsewhere, and the placebo test fails. So every
main estimate first differences each flow against the same week one year earlier (weeks aligned 52 weeks
apart), then compares treated with control flows before and after 5 January:

    YoY_fw = log(trips_fw, 2024-25) - log(trips_fw, 2023-24)
    YoY_fw = flow effect + week effect + beta x (touches zone x after 5 Jan) + error

beta is a triple difference (zone vs. elsewhere, after vs. before, this year vs. last year). Flows are
pickup zone x trip group; weights are each flow's pre-period weekly trips; standard errors are clustered by
pickup zone. Speeds use the same logic on the daily log-speed gap between trips inside the zone and trips
inside upper Manhattan, with Newey-West standard errors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS
from scipy import stats

from src import config

S0, S1 = config.BASE, config.TOLL_SEASON
MEASURES = ["trips", "miles", "hours", "base_fare", "passenger_cost", "cbd_fee", "driver_pay"]


def yoy_panel(flow_week: pd.DataFrame, service: str, weeks: list[int] | None = None) -> pd.DataFrame:
    """Flow x week panel of year-over-year changes for one service (balanced, enough volume both years)."""
    df = flow_week[flow_week.service == service].copy()
    if weeks is not None:
        df = df[df.rel_week.isin(weeks)]
    df["flow"] = df.pu_zone.astype(str) + "|" + df.trip_group
    wide = df.pivot_table(index=["flow", "rel_week"], columns="season", values=MEASURES, aggfunc="sum")
    if df.driver_pay.isna().all():                            # taxis report no driver pay
        wide[[("driver_pay", S0), ("driver_pay", S1)]] = np.nan
    wide = wide.dropna(subset=[("trips", S0), ("trips", S1)])
    n_weeks = df.rel_week.nunique()
    complete = wide.groupby(level="flow").size() == n_weeks
    pre = wide[wide.index.get_level_values("rel_week") < 0]
    pre_mean = pre.groupby(level="flow")[[("trips", S0), ("trips", S1)]].mean()
    big = (pre_mean.min(axis=1) >= config.MIN_WEEKLY_TRIPS)
    keep = set(complete[complete].index) & set(big[big].index)
    wide = wide[wide.index.get_level_values("flow").isin(keep)]
    out = pd.DataFrame(index=wide.index)
    t0, t1 = wide[("trips", S0)], wide[("trips", S1)]
    out["d_log_trips"] = np.log(t1) - np.log(t0)
    out["d_log_mph"] = np.log(wide[("miles", S1)] / wide[("hours", S1)]) - np.log(wide[("miles", S0)] / wide[("hours", S0)])
    for m in ("base_fare", "passenger_cost", "cbd_fee", "driver_pay"):
        out[f"d_{m}_per_trip"] = wide[(m, S1)] / t1 - wide[(m, S0)] / t0
        out[f"{m}_per_trip_s1"] = wide[(m, S1)] / t1
    out["d_driver_pay_per_hour"] = wide[("driver_pay", S1)] / wide[("hours", S1)] - wide[("driver_pay", S0)] / wide[("hours", S0)]
    out["driver_pay_per_hour_s1"] = wide[("driver_pay", S1)] / wide[("hours", S1)]
    flows = out.index.get_level_values("flow").to_series(index=out.index)
    out["trip_group"] = flows.str.split("|").str[1]
    out["pu_zone"] = flows.str.split("|").str[0].astype(int)
    out["treated"] = out.trip_group.isin(config.TREATED_GROUPS)
    out["post"] = out.index.get_level_values("rel_week") >= 0
    out["weight"] = out.index.get_level_values("flow").map(pre_mean[("trips", S1)])
    return out.sort_index()


def _fit(df: pd.DataFrame, y: str, exog: list[str], weights: bool = True):
    mod = PanelOLS(df[y], df[exog], entity_effects=True, time_effects=True,
                   weights=df["weight"] if weights else None, drop_absorbed=True)
    return mod.fit(cov_type="clustered", clusters=df[["pu_zone"]])


def _row(res, name: str, log: bool) -> dict:
    b, se = float(res.params[name]), float(res.std_errors[name])
    lo, hi = b - 1.96 * se, b + 1.96 * se
    out = {"coef": b, "std_error": se, "ci_low": lo, "ci_high": hi, "p_value": float(res.pvalues[name]),
           "n_obs": int(res.nobs)}
    if log:
        out.update({"effect_pct": float(np.exp(b) - 1), "effect_pct_low": float(np.exp(lo) - 1),
                    "effect_pct_high": float(np.exp(hi) - 1)})
    return out


def trips_did(panel: pd.DataFrame, weights: bool = True, y: str = "d_log_trips") -> dict:
    """Pooled effect on log trips for flows touching the zone, plus one effect per trip group."""
    df = panel.copy()
    df["treated_post"] = (df.treated & df.post).astype(float)
    pooled = _row(_fit(df, y, ["treated_post"], weights), "treated_post", log=True)
    groups = [g for g in config.TREATED_GROUPS if (df.trip_group == g).any()]
    names = []
    for g in groups:
        col = "post_" + g.split()[0].lower()
        df[col] = ((df.trip_group == g) & df.post).astype(float)
        names.append(col)
    res = _fit(df, y, names, weights)
    by_group = {g: _row(res, n, log=True) for g, n in zip(groups, names)}
    return {"pooled": pooled, "by_group": by_group, "flows": int(df.index.get_level_values(0).nunique()),
            "treated_flows": int(df[df.treated].index.get_level_values(0).nunique())}


def money_did(panel: pd.DataFrame) -> dict:
    """Effect in dollars per trip (driver pay also per hour) for flows touching the zone, trip-weighted."""
    df = panel.copy()
    df["treated_post"] = (df.treated & df.post).astype(float)
    out = {}
    for m in ("passenger_cost", "base_fare", "cbd_fee", "driver_pay"):
        y = f"d_{m}_per_trip"
        if df[y].notna().all():
            out[f"{m}_per_trip"] = _row(_fit(df, y, ["treated_post"]), "treated_post", log=False)
            pre = df[df.treated & ~df.post]
            out[f"{m}_per_trip"]["treated_pre_mean_s1"] = float(np.average(pre[f"{m}_per_trip_s1"], weights=pre.weight))
    if df["d_driver_pay_per_hour"].notna().all():
        out["driver_pay_per_hour"] = _row(_fit(df, "d_driver_pay_per_hour", ["treated_post"]), "treated_post", log=False)
        pre = df[df.treated & ~df.post]
        out["driver_pay_per_hour"]["treated_pre_mean_s1"] = float(np.average(pre.driver_pay_per_hour_s1, weights=pre.weight))
    out["mph"] = _row(_fit(df, "d_log_mph", ["treated_post"]), "treated_post", log=True)
    return out


def event_study(panel: pd.DataFrame, y: str = "d_log_trips", ref_week: int = -1) -> tuple[pd.DataFrame, dict]:
    """Treated x week coefficients, re-centred on the average of the regular (non-holiday) pre-period weeks.

    The model omits week -1; each coefficient is then expressed relative to the mean of the regular pre weeks,
    with standard errors from the full covariance matrix. The pre-trend test asks whether the regular pre
    weeks differ from each other (joint Wald test of the re-centred coefficients).
    """
    df = panel.copy()
    weeks = sorted(df.index.get_level_values("rel_week").unique())
    names = []
    for k in weeks:
        if k == ref_week:
            continue
        col = f"w_{k}".replace("-", "m")
        df[col] = (df.treated & (df.index.get_level_values("rel_week") == k)).astype(float)
        names.append((k, col))
    res = _fit(df, y, [c for _, c in names])
    order = [k for k, _ in names]
    b = res.params[[c for _, c in names]].to_numpy()
    v = res.cov.loc[[c for _, c in names], [c for _, c in names]].to_numpy()
    # add the omitted week as a zero coefficient with zero variance
    order.append(ref_week)
    b = np.append(b, 0.0)
    v = np.pad(v, ((0, 1), (0, 1)))
    regular = [i for i, k in enumerate(order) if k < 0 and k not in config.HOLIDAY_WEEKS]
    contrast = np.eye(len(order))
    contrast[:, regular] -= 1.0 / len(regular)
    c = contrast @ b
    cv = contrast @ v @ contrast.T
    se = np.sqrt(np.clip(np.diag(cv), 0, None))
    es = pd.DataFrame({"rel_week": order, "coef": c, "ci_low": c - 1.96 * se, "ci_high": c + 1.96 * se,
                       "holiday": [k in config.HOLIDAY_WEEKS for k in order]}).sort_values("rel_week")
    sub = regular[:-1]                                        # one restriction fewer: they sum to zero
    wald = float(c[sub] @ np.linalg.solve(cv[np.ix_(sub, sub)], c[sub]))
    pre = es[(es.rel_week < 0) & ~es.holiday]
    post = es[es.rel_week >= 0]
    test = {"wald_stat": wald, "df": len(sub), "p_value": float(stats.chi2.sf(wald, len(sub))),
            "regular_pre_weeks": [order[i] for i in regular],
            "max_abs_regular_pre_pct": float(np.max(np.abs(np.exp(pre.coef) - 1))),
            "mean_post_pct": float(np.exp(post.coef.mean()) - 1)}
    return es.reset_index(drop=True), test


def placebo(flow_week: pd.DataFrame, service: str) -> dict:
    """Fake start on 1 Dec 2024 (week -5), using pre-period weeks only and leaving out the Thanksgiving weeks."""
    pre_weeks = [w for w in range(config.REL_WEEKS[0], 0) if w not in config.THANKSGIVING_WEEKS]
    panel = yoy_panel(flow_week, service, weeks=pre_weeks)
    panel["post"] = panel.index.get_level_values("rel_week") >= config.PLACEBO_REL_WEEK
    out = trips_did(panel)["pooled"]
    out["fake_rel_week"] = config.PLACEBO_REL_WEEK
    return out


def single_season(flow_week: pd.DataFrame, service: str) -> dict:
    """The naive design without last year: 2024-25 only, after vs. before. Kept to show why it fails."""
    df = flow_week[(flow_week.service == service) & (flow_week.season == S1)].copy()
    df["flow"] = df.pu_zone.astype(str) + "|" + df.trip_group
    pre_mean = df[df.rel_week < 0].groupby("flow").trips.mean()
    complete = df.groupby("flow").rel_week.nunique() == df.rel_week.nunique()
    keep = set(pre_mean[pre_mean >= config.MIN_WEEKLY_TRIPS].index) & set(complete[complete].index)
    df = df[df.flow.isin(keep)].copy()
    df["weight"] = df.flow.map(pre_mean)
    df["log_trips"] = np.log(df.trips)
    df["treated"] = df.trip_group.isin(config.TREATED_GROUPS)
    df = df.set_index(["flow", "rel_week"]).sort_index()
    df["post"] = df.index.get_level_values("rel_week") >= 0
    main = trips_did(df, y="log_trips")["pooled"]
    pre = df[(df.index.get_level_values("rel_week") < 0)
             & ~df.index.get_level_values("rel_week").isin(config.THANKSGIVING_WEEKS)].copy()
    pre["post"] = pre.index.get_level_values("rel_week") >= config.PLACEBO_REL_WEEK
    fake = trips_did(pre, y="log_trips")["pooled"]
    return {"estimate": main, "placebo": fake}


def _daily_gap(group_day: pd.DataFrame, service: str, treated: str, control: str) -> pd.DataFrame:
    g = group_day[group_day.service == service].pivot_table(index=["season", "rel_day"], columns="trip_group",
                                                           values=["miles", "hours"], aggfunc="sum")
    mph = g["miles"] / g["hours"]
    gap = (np.log(mph[treated]) - np.log(mph[control])).unstack("season")
    gap = gap.dropna()
    return pd.DataFrame({"gap_s0": gap[S0], "gap_s1": gap[S1], "d_gap": gap[S1] - gap[S0],
                         "mph_t_s1": mph[treated].xs(S1).reindex(gap.index),
                         "mph_c_s1": mph[control].xs(S1).reindex(gap.index),
                         "mph_t_s0": mph[treated].xs(S0).reindex(gap.index),
                         "mph_c_s0": mph[control].xs(S0).reindex(gap.index)})


def speed_did(group_day: pd.DataFrame, service: str, treated: str = "Within zone",
              control: str = "Manhattan, outside zone") -> dict:
    """Change in the daily log-speed gap (zone vs. upper Manhattan) after 5 Jan, net of last year's change."""
    d = _daily_gap(group_day, service, treated, control)
    post = (d.index >= 0).astype(float)
    res = sm.OLS(d.d_gap.to_numpy(), sm.add_constant(post)).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    single = sm.OLS(d.gap_s1.to_numpy(), sm.add_constant(post)).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    b, se = float(res.params[1]), float(res.bse[1])
    pre, aft = d.index < 0, d.index >= 0
    return {"treated": treated, "control": control, "coef": b, "std_error": se, "p_value": float(res.pvalues[1]),
            "effect_pct": float(np.exp(b) - 1), "effect_pct_low": float(np.exp(b - 1.96 * se) - 1),
            "effect_pct_high": float(np.exp(b + 1.96 * se) - 1),
            "single_season_effect_pct": float(np.exp(single.params[1]) - 1),
            "mph_treated_before": float(d.mph_t_s1[pre].mean()), "mph_treated_after": float(d.mph_t_s1[aft].mean()),
            "mph_control_before": float(d.mph_c_s1[pre].mean()), "mph_control_after": float(d.mph_c_s1[aft].mean()),
            "mph_treated_before_last_year": float(d.mph_t_s0[pre].mean()),
            "mph_treated_after_last_year": float(d.mph_t_s0[aft].mean()), "days": int(len(d))}


def speed_by_week(group_day: pd.DataFrame, service: str, treated: str = "Within zone",
                  control: str = "Manhattan, outside zone") -> pd.DataFrame:
    """Weekly year-over-year change in the speed gap, centred on its pre-period mean."""
    d = _daily_gap(group_day, service, treated, control).reset_index()
    d["rel_week"] = np.floor(d.rel_day / 7).astype(int)
    d = d[d.rel_week.between(*config.REL_WEEKS)]
    w = d.groupby("rel_week").d_gap.mean().rename("d_gap").reset_index()
    w["d_gap_vs_pre"] = w.d_gap - w.loc[w.rel_week < 0, "d_gap"].mean()
    w["pct_vs_pre"] = np.exp(w.d_gap_vs_pre) - 1
    return w


def group_period_summary(group_day: pd.DataFrame) -> pd.DataFrame:
    """Before/after averages per season, service and trip group."""
    rows = []
    for (season, service, group, post), x in group_day.groupby(["season", "service", "trip_group", "post"]):
        rows.append({"season": season, "service": service, "trip_group": group, "period": "after" if post else "before",
                     "trips_per_day": x.trips.mean(), "mph": x.miles.sum() / x.hours.sum(),
                     "passenger_cost_per_trip": np.average(x.passenger_cost_per_trip, weights=x.trips),
                     "base_fare_per_trip": np.average(x.base_fare_per_trip, weights=x.trips),
                     "cbd_fee_per_trip": np.average(x.cbd_fee_per_trip, weights=x.trips),
                     "driver_pay_per_trip": (np.average(x.driver_pay_per_trip, weights=x.trips)
                                             if x.driver_pay_per_trip.notna().all() else np.nan),
                     "share_with_cbd_fee": np.average(x.share_with_cbd_fee, weights=x.trips)})
    df = pd.DataFrame(rows)
    wide = df.pivot_table(index=["service", "trip_group"], columns=["season", "period"], dropna=False)
    wide.columns = [f"{m}_{s}_{p}" for m, s, p in wide.columns]
    wide = wide.reset_index()
    for s in (S0, S1):
        wide[f"trips_change_{s}"] = wide[f"trips_per_day_{s}_after"] / wide[f"trips_per_day_{s}_before"] - 1
        wide[f"mph_change_{s}"] = wide[f"mph_{s}_after"] / wide[f"mph_{s}_before"] - 1
    wide["trips_change_net"] = (1 + wide[f"trips_change_{S1}"]) / (1 + wide[f"trips_change_{S0}"]) - 1
    wide["mph_change_net"] = (1 + wide[f"mph_change_{S1}"]) / (1 + wide[f"mph_change_{S0}"]) - 1
    return wide
