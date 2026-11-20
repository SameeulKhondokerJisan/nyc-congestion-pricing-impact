# Memo: what congestion pricing did to ride-hail trips in Manhattan

**To:** Head of Pricing and Driver Operations · **Data:** 271 million TLC trips, Oct-Mar 2023-24 and 2024-25

**What we found**

- **Ride-hail demand for zone trips barely moved.** Uber/Lyft trips to, from and within the zone changed by -0.7% relative to trips with no end in the zone, net of last year's seasonal change (95% CI -1.5% to +0.2%). The interval includes zero. For scale, the MTA reports 11% fewer vehicles entering the zone in the toll's first year: ride-hail trips pay a $1.50 charge, not the $9 car toll, so their volume fell far less.
- **Trips inside the zone got faster.** Uber/Lyft trips with both ends in the zone sped up 4.2% relative to trips inside Manhattan north of 60th Street, net of last year (95% CI +2.6% to +5.8%); average speed went from 8.1 to 9.0 mph. Yellow taxis show the same gain (4.8%). The gain is 5.1 points in tolled peak hours against 1.1 overnight.
- **Riders paid $0.61 more per zone trip, not $1.50.** The zone charge added $1.45 per trip, but base fares fell $0.72 relative to other trips (net of last year), because faster trips take less time and both Uber/Lyft fares and TLC driver-pay rules include a per-minute component.
- **Drivers earned less per trip but more per hour.** Driver pay per zone trip fell $0.55 (-$0.65 to -$0.45), while pay per hour on trip rose $0.92 (+$0.72 to +$1.12) from a base of $60 per hour.
- **Yellow taxis: no clear change in zone trips.** The estimate is +2.0% (95% CI +0.3% to +3.6%), but a placebo start date in December gives +2.1%, so this is not evidence of riders switching to the cheaper $0.75 taxi charge.
- **A single-season before/after comparison would mislead.** Comparing Jan-Mar 2025 with Oct-Dec 2024 alone puts the speed gain at 8.8% (double the estimate net of last year) and fails a placebo test (-13.4% 'effect' at a fake start date), because Manhattan's holiday season moves zone trips differently. Using Oct-Mar 2023-24 as the seasonal baseline fixes this: the placebo gives +0.7% (p = 0.13).

**What to do**

1. Do not cut Uber/Lyft fares to offset the zone charge: zone trip volume held up, and riders' net price rose by less than half the charge because faster trips cost less.
2. Use the faster zone trips in driver supply messages: pay per hour on zone trips rose, so zone-specific driver bonuses are not needed to keep supply.
3. Review the time-based part of the fare and driver pay formulas: faster trips cut base fares by about $0.72 per zone trip.
4. Refresh the analysis as TLC publishes new months (about two months' delay) and watch the event study for a delayed demand response.

**Caveats:** observational design using last year as the baseline; trips through the zone without stopping are not identified; effects of a few percent are within weekly noise.
