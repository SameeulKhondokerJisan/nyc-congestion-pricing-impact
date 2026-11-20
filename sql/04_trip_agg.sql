-- 04_trip_agg.sql
-- Cleaned trips aggregated to season x service x pickup date x hour x pickup zone x trip group, in one pass
-- over the Parquet files. Every later table is a roll-up of this one.
-- Trip groups: Within zone (both ends in the Congestion Relief Zone), Into zone, Out of zone,
-- Manhattan outside zone (both ends in Manhattan north of 60th St), Elsewhere (all other trips).
CREATE OR REPLACE TABLE trip_agg AS
WITH t AS (
    SELECT *, date_diff('second', pickup_ts, dropoff_ts) AS secs FROM trips_raw
), clean AS (
    SELECT t.*, zp.in_cbd AS pu_cbd, zd.in_cbd AS do_cbd, zp.borough AS pu_borough, zd.borough AS do_borough
    FROM t
    JOIN zones zp ON zp.zone_id = t.pu_zone
    JOIN zones zd ON zd.zone_id = t.do_zone
    WHERE ((t.pickup_ts >= TIMESTAMP '{s0_start}' AND t.pickup_ts < TIMESTAMP '{s0_end}')
           OR (t.pickup_ts >= TIMESTAMP '{s1_start}' AND t.pickup_ts < TIMESTAMP '{s1_end}'))
      AND t.secs BETWEEN 60 AND 10800 AND t.miles > 0 AND t.miles <= 100
      AND t.miles / (t.secs / 3600.0) BETWEEN 0.5 AND 65
      AND t.pu_zone BETWEEN 1 AND 263 AND t.do_zone BETWEEN 1 AND 263
      AND t.base_fare > 0 AND t.passenger_cost > 0
)
SELECT CASE WHEN pickup_ts < TIMESTAMP '{s1_start}' THEN '{s0}' ELSE '{s1}' END AS season,
       service, CAST(pickup_ts AS DATE) AS pickup_date, CAST(hour(pickup_ts) AS INTEGER) AS pickup_hour, pu_zone,
       CASE WHEN pu_cbd AND do_cbd THEN 'Within zone'
            WHEN do_cbd THEN 'Into zone'
            WHEN pu_cbd THEN 'Out of zone'
            WHEN pu_borough = 'Manhattan' AND do_borough = 'Manhattan' THEN 'Manhattan, outside zone'
            ELSE 'Elsewhere' END AS trip_group,
       COUNT(*) AS trips, SUM(miles) AS miles, SUM(secs) / 3600.0 AS hours,
       SUM(base_fare) AS base_fare, SUM(passenger_cost) AS passenger_cost, SUM(tips) AS tips,
       SUM(tolls) AS tolls, SUM(ny_surcharge) AS ny_surcharge, SUM(cbd_fee) AS cbd_fee,
       COUNT(*) FILTER (WHERE cbd_fee > 0) AS trips_with_cbd_fee, SUM(driver_pay) AS driver_pay
FROM clean
GROUP BY ALL;

-- Calendar position of each pickup date: days since the season's (aligned) toll start.
CREATE OR REPLACE VIEW trip_days AS
SELECT *, date_diff('day', CASE season WHEN '{s0}' THEN DATE '{s0_toll}' ELSE DATE '{s1_toll}' END, pickup_date)
          AS rel_day
FROM trip_agg;
