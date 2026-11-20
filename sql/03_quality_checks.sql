-- 03_quality_checks.sql
-- Rows breaking each cleaning rule, per service and pickup month (a row can break several rules).
-- The same rules filter trips in 04_trip_agg.sql. Study windows: Oct-Mar of 2023-24 and of 2024-25.
WITH t AS (
    SELECT service, pickup_ts, dropoff_ts, pu_zone, do_zone, miles, base_fare, passenger_cost,
           date_diff('second', pickup_ts, dropoff_ts) AS secs,
           (pickup_ts >= TIMESTAMP '{s0_start}' AND pickup_ts < TIMESTAMP '{s0_end}')
               OR (pickup_ts >= TIMESTAMP '{s1_start}' AND pickup_ts < TIMESTAMP '{s1_end}') AS in_window
    FROM trips_raw
)
SELECT service, strftime(pickup_ts, '%Y-%m') AS pickup_month,
       COUNT(*) AS rows_read,
       COUNT(*) FILTER (WHERE NOT in_window) AS outside_window,
       COUNT(*) FILTER (WHERE secs < 60 OR secs > 10800) AS duration_out_of_range,
       COUNT(*) FILTER (WHERE miles <= 0 OR miles > 100 OR miles IS NULL) AS distance_out_of_range,
       COUNT(*) FILTER (WHERE secs >= 60 AND miles > 0 AND (miles / (secs / 3600.0) < 0.5 OR miles / (secs / 3600.0) > 65))
           AS speed_out_of_range,
       COUNT(*) FILTER (WHERE pu_zone NOT BETWEEN 1 AND 263 OR do_zone NOT BETWEEN 1 AND 263
                          OR pu_zone IS NULL OR do_zone IS NULL) AS unknown_zone,
       COUNT(*) FILTER (WHERE base_fare <= 0 OR passenger_cost <= 0) AS non_positive_fare,
       COUNT(*) FILTER (WHERE in_window AND secs BETWEEN 60 AND 10800 AND miles > 0 AND miles <= 100
                          AND miles / (secs / 3600.0) BETWEEN 0.5 AND 65
                          AND pu_zone BETWEEN 1 AND 263 AND do_zone BETWEEN 1 AND 263
                          AND base_fare > 0 AND passenger_cost > 0) AS rows_kept
FROM t
GROUP BY ALL
ORDER BY service, pickup_month;
