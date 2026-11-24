# Team TOROUS — Crowdedness-Aware Bus Journey Planner (Delhi Transport Hackathon 2026)

**Problem Statement:** Problem 2 / Phase 1 — Crowdedness-Aware Journey Planner

## Overview
A bus journey planner for Delhi that estimates stretch-by-stretch crowding across time bands and day types (weekday vs. weekend) using October 2026 ETM/e-ticketing records and static GTFS schedules. Commuters can compare route options on both travel time and crowding levels (*Seats available*, *Standing room*, *Crowded*), with transparency badges (*Low data*, *No data*) where ticket counts are sparse.

## Repository Contents
- TOROUS_crowding_model.ipynb — Data pipeline notebook that aligns October 2026 tickets with static GTFS schedules, computes running onboard demand per stretch and time band, and generates crowding_by_band.csv
- app.py — Web application entry point
- planner.py — Journey routing and crowding lookup module
- DATA — Static GTFS files (routes.txt, trips.txt, stops.txt, stop_times.txt) and precomputed crowding lookup table (crowding_by_band.csv)
- requirements.txt — Python package dependencies

## Setup & How to Run

### 1. Clone the Repository
bash
git clone https://github.com/Jaiyadav4/Crowdedness-aware-journey-planner.git
cd Crowdedness-aware-journey-planner
