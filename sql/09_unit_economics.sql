-- 09_unit_economics.sql
-- Average money per trip by season, service, whether the trip touches the zone, and period (before/after
-- the season's start date). other_fees = everything the rider pays besides base fare, tolls, the NYS
-- surcharge and the CBD charge (sales tax, Black Car Fund and airport fee for Uber/Lyft; MTA tax,
-- improvement surcharge and extras for taxis).
SELECT season, service,
       trip_group IN ('Within zone', 'Into zone', 'Out of zone') AS touches_zone,
       CASE WHEN rel_day >= 0 THEN 'After' ELSE 'Before' END AS period,
       SUM(trips) AS trips, COUNT(DISTINCT pickup_date) AS days,
       SUM(trips) / COUNT(DISTINCT pickup_date) AS trips_per_day,
       SUM(base_fare) / SUM(trips) AS base_fare, SUM(tolls) / SUM(trips) AS tolls,
       SUM(ny_surcharge) / SUM(trips) AS ny_surcharge, SUM(cbd_fee) / SUM(trips) AS cbd_fee,
       (SUM(passenger_cost) - SUM(base_fare) - SUM(tolls) - SUM(ny_surcharge) - SUM(cbd_fee)) / SUM(trips) AS other_fees,
       SUM(passenger_cost) / SUM(trips) AS passenger_cost, SUM(tips) / SUM(trips) AS tips,
       SUM(driver_pay) / SUM(trips) AS driver_pay, SUM(miles) / SUM(trips) AS miles,
       SUM(hours) * 60 / SUM(trips) AS minutes
FROM trip_days
GROUP BY ALL
ORDER BY season, service, touches_zone, period DESC;
