-- 06_group_day.sql
-- Daily totals per season, service and trip group, with distance-weighted speed and per-trip money columns.
-- rel_day aligns the two seasons day by day (same weekday, 364 days apart).
SELECT season, service, trip_group, pickup_date, rel_day, rel_day >= 0 AS post,
       SUM(trips) AS trips, SUM(miles) / SUM(hours) AS mph, SUM(miles) / SUM(trips) AS miles_per_trip,
       SUM(base_fare) / SUM(trips) AS base_fare_per_trip, SUM(passenger_cost) / SUM(trips) AS passenger_cost_per_trip,
       SUM(cbd_fee) / SUM(trips) AS cbd_fee_per_trip, SUM(driver_pay) / SUM(trips) AS driver_pay_per_trip,
       SUM(driver_pay) / SUM(hours) AS driver_pay_per_hour, SUM(trips_with_cbd_fee) / SUM(trips) AS share_with_cbd_fee,
       SUM(miles) AS miles, SUM(hours) AS hours
FROM trip_days
GROUP BY ALL
ORDER BY season, service, trip_group, pickup_date;
