-- 07_hour_weekday.sql
-- Speed and trips per day by weekday and pickup hour, before and after the (aligned) start date, per season,
-- service and trip group.
WITH days AS (
    SELECT season, dayofweek(pickup_date) AS dow, rel_day >= 0 AS post, COUNT(DISTINCT pickup_date) AS n_days
    FROM trip_days GROUP BY ALL
)
SELECT a.season, a.service, a.trip_group, dayofweek(a.pickup_date) AS dow, dayname(a.pickup_date) AS weekday,
       a.pickup_hour, a.rel_day >= 0 AS post,
       SUM(a.trips) / ANY_VALUE(d.n_days) AS trips_per_day, SUM(a.miles) / SUM(a.hours) AS mph
FROM trip_days a
JOIN days d ON d.season = a.season AND d.dow = dayofweek(a.pickup_date) AND d.post = (a.rel_day >= 0)
GROUP BY a.season, a.service, a.trip_group, dayofweek(a.pickup_date), dayname(a.pickup_date), a.pickup_hour,
         a.rel_day >= 0;
