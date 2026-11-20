-- 02_trips_view.sql
-- One harmonized view over the 12 monthly Parquet files (about 140 million trips), read in place.
-- passenger_cost = everything the rider pays except tips. The cbd_congestion_fee column exists only from
-- January 2025, so union_by_name fills it with NULL for 2024 files.
CREATE OR REPLACE VIEW trips_raw AS
SELECT 'Yellow taxi' AS service, tpep_pickup_datetime AS pickup_ts, tpep_dropoff_datetime AS dropoff_ts,
       PULocationID AS pu_zone, DOLocationID AS do_zone, trip_distance AS miles,
       fare_amount AS base_fare, total_amount - COALESCE(tip_amount, 0) AS passenger_cost,
       COALESCE(tip_amount, 0) AS tips, COALESCE(tolls_amount, 0) AS tolls,
       COALESCE(congestion_surcharge, 0) AS ny_surcharge, COALESCE(cbd_congestion_fee, 0) AS cbd_fee,
       CAST(NULL AS DOUBLE) AS driver_pay
FROM read_parquet('{raw}/trips/yellow_tripdata_*.parquet', union_by_name = true)
UNION ALL BY NAME
SELECT 'Uber/Lyft' AS service, pickup_datetime AS pickup_ts, dropoff_datetime AS dropoff_ts,
       PULocationID AS pu_zone, DOLocationID AS do_zone, trip_miles AS miles,
       base_passenger_fare AS base_fare,
       base_passenger_fare + COALESCE(tolls, 0) + COALESCE(bcf, 0) + COALESCE(sales_tax, 0)
           + COALESCE(congestion_surcharge, 0) + COALESCE(airport_fee, 0) + COALESCE(cbd_congestion_fee, 0)
           AS passenger_cost,
       COALESCE(tips, 0) AS tips, COALESCE(tolls, 0) AS tolls, COALESCE(congestion_surcharge, 0) AS ny_surcharge,
       COALESCE(cbd_congestion_fee, 0) AS cbd_fee, driver_pay
FROM read_parquet('{raw}/trips/fhvhv_tripdata_*.parquet', union_by_name = true);
