-- 01_zones.sql
-- Taxi zones with borough and a flag for the 38 zones the MTA lists inside the Congestion Relief Zone
-- (Manhattan south of and including 60th Street). {raw} is replaced with the absolute path of data/raw.
CREATE OR REPLACE TABLE zones AS
SELECT z.LocationID AS zone_id, z.Borough AS borough, z.Zone AS zone, z.service_zone,
       c.zone_id IS NOT NULL AS in_cbd
FROM read_csv('{raw}/reference/taxi_zone_lookup.csv', header = true) z
LEFT JOIN (SELECT DISTINCT CAST("Taxi Zone" AS INTEGER) AS zone_id
           FROM read_csv('{raw}/reference/mta_cbd_taxi_zones.csv', header = true)) c
       ON c.zone_id = z.LocationID;
