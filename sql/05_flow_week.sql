-- 05_flow_week.sql
-- Weekly panel of "flows" (pickup zone x trip group) per season and service, for difference-in-differences.
-- Weeks run Sunday to Saturday; rel_week = weeks since the season's start date (5 Jan 2025, or 7 Jan 2024
-- for the comparison season): -13 ... -1 before, 0 ... 11 after. Partial weeks at the ends are dropped.
SELECT season, service, pu_zone, trip_group,
       CAST(floor(rel_day / 7) AS INTEGER) AS rel_week,
       MIN(pickup_date) AS week_start,
       SUM(trips) AS trips, SUM(miles) AS miles, SUM(hours) AS hours, SUM(base_fare) AS base_fare,
       SUM(passenger_cost) AS passenger_cost, SUM(cbd_fee) AS cbd_fee, SUM(driver_pay) AS driver_pay,
       SUM(trips_with_cbd_fee) AS trips_with_cbd_fee
FROM trip_days
WHERE floor(rel_day / 7) BETWEEN {w_first} AND {w_last}
GROUP BY season, service, pu_zone, trip_group, CAST(floor(rel_day / 7) AS INTEGER);
