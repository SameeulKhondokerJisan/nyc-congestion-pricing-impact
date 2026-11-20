-- 08_zone_period.sql
-- Per season, pickup zone and service: trips per day and speed before and after the (aligned) start date.
WITH per AS (
    SELECT season, service, pu_zone, rel_day >= 0 AS post,
           SUM(trips) AS trips, SUM(miles) AS miles, SUM(hours) AS hours, COUNT(DISTINCT pickup_date) AS days
    FROM trip_days GROUP BY ALL
)
SELECT p.season, p.service, z.zone_id, z.zone, z.borough, z.in_cbd,
       SUM(CASE WHEN NOT post THEN trips END) / NULLIF(SUM(CASE WHEN NOT post THEN days END), 0) AS trips_per_day_pre,
       SUM(CASE WHEN post THEN trips END) / NULLIF(SUM(CASE WHEN post THEN days END), 0) AS trips_per_day_post,
       SUM(CASE WHEN NOT post THEN miles END) / NULLIF(SUM(CASE WHEN NOT post THEN hours END), 0) AS mph_pre,
       SUM(CASE WHEN post THEN miles END) / NULLIF(SUM(CASE WHEN post THEN hours END), 0) AS mph_post
FROM per p JOIN zones z ON z.zone_id = p.pu_zone
GROUP BY p.season, p.service, z.zone_id, z.zone, z.borough, z.in_cbd;
