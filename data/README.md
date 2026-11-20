# Data

`make data` downloads everything into `raw/` and writes `raw/MANIFEST.json` (file sizes and source URLs;
SHA-256 for the reference files). `make pipeline` builds `processed/tlc.duckdb`. Both folders are git-ignored.

| File | Source | Content |
|---|---|---|
| trips/fhvhv_tripdata_YYYY-MM.parquet | NYC TLC Trip Record Data | High-volume for-hire trips (Uber HV0003, Lyft HV0005), about 20 million a month |
| trips/yellow_tripdata_YYYY-MM.parquet | NYC TLC Trip Record Data | Yellow taxi trips, about 3 to 4 million a month |
| reference/taxi_zone_lookup.csv | NYC TLC | 265 taxi zones with borough (264 and 265 are unknown/outside NYC) |
| reference/taxi_zones.zip | NYC TLC | Taxi zone shapefile (NY State Plane, feet) |
| reference/mta_cbd_taxi_zones.csv | MTA, data.ny.gov dataset yfdc-w5jh | The 38 taxi zones inside the Congestion Relief Zone, with polygons |

Months: October 2023 to March 2024 (comparison season) and October 2024 to March 2025 (the toll started on
5 January 2025). Trip files: https://d37ci6vzurychx.cloudfront.net/trip-data/ (linked from
https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). The `cbd_congestion_fee` column exists from
January 2025. TLC data are published by the City of New York as open data.
