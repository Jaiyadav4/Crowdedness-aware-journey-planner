# Technical Note — Crowdedness-Aware Journey Planner (TOROUS)

## Method
* **Supply (GTFS):** Extracted canonical stop sequences per route (from longest scheduled trip) and scheduled trip counts per stop-to-stop stretch across hours and day types (`weekday` vs. `weekend`).
* **Demand (Ticketing Data):** Normalized ticket origin/destination stop names and mapped them to route stops via exact and same-route fuzzy matching (`FUZZY_CUTOFF = 0.65`). Computed stretch-level daily ridership (`riders_per_day`) for forward trips (`s < e`) using difference-array prefix sums.
* **Crowding & Confidence:** Calculated `crowd_index = riders_per_day / trips`, mapped scores to *Seats available*, *Standing room*, and *Crowded* using `0.50` and `0.85` quantiles on slices with `tickets >= 30` (`MIN_TICKETS = 30`), and flagged sparse/unscheduled slices (`Low data` / `No data`).
* **Planner:** `planner.py` and `app.py` serve route comparisons with travel time and crowding estimates from `crowding_by_band.csv` and GTFS schedules.

## Assumptions
* Longest trip represents the canonical stop order; directional variants/route IDs stay separate.
* Tickets represent forward stop progression (`s < e`) with quantile thresholds calibrated on `tickets >= 30`.

## Limitations
* Higher uncertainty on low-ticket (`< 30`), off-peak, or unmatched-stop slices.
* Pass holders/unrecorded riders, bus size differences (`12 m` vs. `9 m`), and seasonal shifts outside October 2026 are not explicitly modeled.