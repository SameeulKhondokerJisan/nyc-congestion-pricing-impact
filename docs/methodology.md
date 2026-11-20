# Methodology

## Question and setting
On 5 January 2025 New York began tolling vehicles that enter Manhattan south of and including 60th Street (the
Congestion Relief Zone, CRZ). Taxi and for-hire riders pay a per-trip charge instead of the vehicle toll: $1.50 for
high-volume for-hire services (Uber, Lyft) and $0.75 for taxis, on trips to, from, within or through the zone.
A New York State congestion surcharge for trips south of 96th Street ($2.75 for ride-hail, $2.50 for taxis)
existed before and continues.

## Data and cleaning
TLC trip records for October to March of 2023-24 and 2024-25 (24 Parquet files), read in place by DuckDB through one
view that harmonizes the yellow taxi and high-volume for-hire schemas. Rider total excludes tips. A trip is kept if
it starts inside a study window, lasts 1 minute to 3 hours, covers more than 0 and at most 100 miles, averages
0.5 to 65 mph, has known pickup and dropoff zones (1-263), and has a positive fare and rider total. Rule counts by
month are in `data_quality_log.md`. Kept trips are aggregated in one pass to season x service x date x hour x
pickup zone x trip group (`sql/04_trip_agg.sql`); all analysis uses roll-ups of that table.

## Trip groups
The MTA's list of taxi zones inside the CRZ (data.ny.gov yfdc-w5jh, 38 zones) defines five groups from the pickup
and dropoff zones: within zone, into zone, out of zone (the three "touching" groups that pay the charge), upper
Manhattan (both ends in Manhattan outside the zone) and elsewhere. Trips that cross the zone without stopping pay
the charge but fall in "elsewhere": in Jan-Mar 2025 about 2% of Uber/Lyft trips in that group carry the charge,
against 98-99.5% of trips in the touching groups. No trip carries the charge before 4 January 2025; on 4 January,
about 1,400 trips that started after 21:00 and ran past midnight do (the toll began at 00:00 on 5 January).

## Why last year is the baseline
A single-season comparison (Jan-Mar 2025 against Oct-Dec 2024) mixes the toll with the seasonal swing from the
holiday season to winter, which hits Manhattan trips differently from trips elsewhere. That design fails a placebo
test: a fake start date in the pre-period produces a large "effect" (`single_season` in `results.json`). The main
design therefore uses October-March 2023-24 as the seasonal baseline, with weeks aligned 52 weeks apart (Sunday
7 January 2024 matches Sunday 5 January 2025, so weekdays, Christmas and New Year line up).

## Trips: difference-in-differences on year-over-year changes
Unit: a flow = pickup zone x trip group, per service. For each flow and aligned week, YoY = log(trips 2024-25) -
log(trips 2023-24). Model: YoY = flow effect + week effect + beta x (touching group x after 5 January), estimated
with `linearmodels.PanelOLS`, weights equal to the flow's pre-period weekly trips (so beta is volume-weighted),
standard errors clustered by pickup zone. Flows need at least 50 trips a week before the start in both seasons and
data in every week. Thanksgiving falls in week -7 of 2023-24 but week -6 of 2024-25, so those two misaligned weeks
are left out of the main estimate (the all-weeks version is reported too). Effects by trip group use one dummy per
touching group.

## Checks
* Event study: one coefficient per week, re-centered on the average of the regular pre-period weeks (excluding the
  Thanksgiving, pre-Christmas, Christmas and New Year weeks), with standard errors from the full covariance matrix.
* Pre-trend test: joint Wald test that the regular pre-period weeks are equal. With hundreds of flows the standard
  errors are small, so even differences of a few percent between weeks reject; the README reports the size of the
  pre-period variation next to the estimate so readers can judge it.
* Placebo: a fake start on 1 December 2024 (week -5), using pre-period weeks only and leaving out Thanksgiving.
* Robustness: all weeks, unweighted, and the naive single-season design.

## Money per trip
Same design with dollar outcomes per trip (rider total, base fare, zone charge, driver pay) and driver pay per hour
on trip, as year-over-year differences in levels. Taxis do not report driver pay.

## Speeds
Distance-weighted average speed (miles / hours) per day for trips within the zone and for trips within upper
Manhattan. The outcome is the year-over-year change in the daily log-speed gap between the two; it is regressed on
an after-5-January dummy with Newey-West standard errors (7 lags). The hour x weekday heatmap repeats the
comparison cell by cell. Speeds are trip averages, not road-segment speeds.

## Implied price response
Trips effect (log points) divided by the rider price effect as a share of the pre-period rider price, for
Uber/Lyft trips touching the zone. It also absorbs faster trips and anything else that changed for zone trips,
so the Excel scenarios treat it as a rough guide near the current charge.
