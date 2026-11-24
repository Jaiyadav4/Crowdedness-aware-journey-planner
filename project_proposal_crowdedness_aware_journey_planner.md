# Project Proposal — Crowdedness-Aware Bus Journey Planner (Delhi)

**Team:** TOROUS  
**Hackathon:** Transport Stack Hackathon 2026  
**Problem Statement:** Problem 2 / Phase 1 — Crowdedness-Aware Journey Planner  

## 1. Problem Chosen
Commuters traveling by bus in Delhi often have to choose between the fastest route and a less crowded ride without clear visibility into how busy different stretches of a route are at specific times of day. Existing journey planning typically focuses on schedule and travel time rather than stretch-by-stretch crowding or data reliability.

Our goal is to build a crowdedness-aware bus journey planner that estimates occupancy across route stretches, time bands, and day types (`weekday` vs. `weekend`), helping commuters compare route options while transparently flagging slices with sparse ticketing data.

## 2. Data Used
- **October 2026 Delhi Bus Ticketing Data:** ETM / e-ticketing trip records containing passenger counts, route identifiers, origin/destination stop names (`start_stop_name`, `end_stop_name`), and transaction timestamps (`created_at`).
- **Delhi Static GTFS Schedule Data:** `routes.txt`, `trips.txt`, `stops.txt`, and `stop_times.txt` used to establish canonical stop sequences along routes, scheduled departure hours, and stretch-level trip supply.

## 3. Approach & System Architecture
1. **GTFS Schedule & Supply Construction:** We parse static GTFS tables, build a canonical ordered stop list per route using its longest scheduled trip, and count unique scheduled trips traversing each consecutive stop-to-stop stretch (`idx` to `idx + 1`) by hour and time band.
2. **Stop Matching & Stretch Demand Estimation:** We normalize stop names and apply exact plus same-route fuzzy matching (`FUZZY_CUTOFF = 0.65`) to map ticket origin and destination stops onto canonical route indices. For valid forward trips (`s < e`), we use a cumulative difference array (`+passenger_count` at boarding, `-passenger_count` at alighting) to compute running onboard demand per stretch, hour, and day type (`weekday` vs. `weekend`), scaled to daily averages (`riders_per_day`).
3. **Crowding Index, Labels & Confidence Flagging:** We compute `crowd_index = riders_per_day / trips` for each route stretch, time band, and day type. Using empirical quantiles (`0.50` and `0.85`) over reliable observations (`tickets >= MIN_TICKETS`, with `MIN_TICKETS = 30`), we map scores to *Seats available*, *Standing room*, and *Crowded*, and flag low-ticket or unscheduled stretches (`Low data` / `No data`).
4. **Journey Planner Prototype:** Our Python prototype (`app.py` and `planner.py`) consumes the precomputed crowding lookup table (`crowding_by_band.csv`) and GTFS data so users can query routes and compare travel time alongside crowding levels.

## 4. Key Assumptions & Limitations
- **Assumptions:** Longest scheduled trip represents the canonical stop order; directional variants (`UP`/`DOWN`) are modeled as distinct route identifiers; tickets reflect planned origin-to-destination progression (`s < e`).
- **Limitations:** Estimates are less reliable on low-ticket slices (`< 30` tickets), early/late off-peak bands, unmatched stop names, trips involving pass holders or unrecorded riders, variations in bus fleet size (`12 m` vs. `9 m`), and seasonal/festival differences outside October 2026.