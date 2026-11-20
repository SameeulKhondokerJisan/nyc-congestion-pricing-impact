# Data dictionary

## Warehouse (`data/processed/tlc.duckdb`)

| Object | Grain | Columns |
|---|---|---|
| zones (table) | taxi zone | zone_id, borough, zone, service_zone, in_cbd |
| trips_raw (view) | trip, over the Parquet files | service, pickup_ts, dropoff_ts, pu_zone, do_zone, miles, base_fare, passenger_cost (rider total excluding tips), tips, tolls, ny_surcharge, cbd_fee, driver_pay |
| trip_agg (table) | season x service x pickup date x hour x pickup zone x trip group | trips, miles, hours, base_fare, passenger_cost, tips, tolls, ny_surcharge, cbd_fee, trips_with_cbd_fee, driver_pay (sums) |
| trip_days (view) | trip_agg plus rel_day | rel_day = days since 5 Jan 2025 (2024-25) or 7 Jan 2024 (2023-24) |

## Definitions
* `service`: "Uber/Lyft" (TLC high-volume for-hire files) or "Yellow taxi".
* `season`: "2023-24" (Oct 2023-Mar 2024) or "2024-25" (Oct 2024-Mar 2025).
* `trip_group`: Within zone, Into zone, Out of zone, "Manhattan, outside zone", Elsewhere.
* `rel_week`: floor(rel_day / 7); -13 to -1 before and 0 to 11 after the (aligned) start date.
* `passenger_cost`: Uber/Lyft = base fare + tolls + Black Car Fund + sales tax + NYS surcharge + airport fee + zone
  charge; taxi = total_amount - tip_amount.
* `mph`: sum of miles / sum of hours.

## Result tables (`reports/tables/`)

| File | Content |
|---|---|
| quality_checks.csv | rule failures per service and pickup month |
| group_period_summary.csv | trips per day, speed and money per trip by service, trip group, season and period |
| event_study_trips.csv | weekly coefficients (log points) with 95% CI, per service |
| speed_gap_by_week.csv | weekly YoY change in the zone vs upper Manhattan speed gap |
| speed_by_hour_weekday.csv | speed change by weekday and hour, relative and net of last year |
| zone_change.csv | per pickup zone: pickups and speed before/after in both seasons, net change |
| unit_economics.csv | money per trip by season, service, touching flag and period |
| cbd_fee_share_after.csv | share of trips carrying the zone charge in Jan-Mar 2025, by group |
