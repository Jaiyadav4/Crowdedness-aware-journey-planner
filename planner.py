"""
TRADON journey planner (Transport Stack Hackathon 2026, Problem 2)

Finds bus journeys between two stops (direct, or with one change) from the
static GTFS schedule, and puts a crowding level next to every option using
crowding_by_band.csv (made by the notebook).

Not included on purpose: walking to/from stops, other modes than bus.
"""
import re
import difflib
from collections import defaultdict

import numpy as np
import pandas as pd

norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())

# Must be the same bands as in the notebook
BANDS = {
    "night (0-5)": range(0, 5),
    "early (5-8)": range(5, 8),
    "morning peak (8-11)": range(8, 11),
    "midday (11-16)": range(11, 16),
    "evening peak (16-21)": range(16, 21),
    "late (21-24)": range(21, 24),
}
HOUR_TO_BAND = {h: b for b, hrs in BANDS.items() for h in hrs}
LEVEL_RANK = {"Seats available": 0, "Standing room": 1, "No data": 1.5, "Crowded": 2}
TRANSFER_BUFFER = 3 * 60      # seconds we assume it takes to change buses


def to_sec(col):
    p = col.str.strip().str.split(":", expand=True).astype(int)
    return (p[0] * 3600 + p[1] * 60 + p[2]).to_numpy()


def hhmm(sec):
    """Seconds since midnight -> 12-hour clock text, e.g. 8:30 AM (times past midnight get '(next day)')."""
    sec = int(sec)
    h, m = (sec % 86400) // 3600, (sec % 3600) // 60
    text = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    return text + (" (next day)" if sec >= 86400 else "")


class Planner:
    def __init__(self, data_dir, crowding_file):
        d = data_dir
        routes = pd.read_csv(f"{d}/routes.txt", usecols=["route_id", "route_short_name", "route_desc"])
        trips = pd.read_csv(f"{d}/trips.txt", usecols=["route_id", "trip_id"])
        stops = pd.read_csv(f"{d}/stops.txt", usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"])
        st = pd.read_csv(f"{d}/stop_times.txt", usecols=[
            "trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"])
        st["arr"] = to_sec(st.arrival_time)
        st["dep"] = to_sec(st.departure_time)
        st = st.sort_values(["trip_id", "stop_sequence"])

        # ---- stop names (many stop_ids share one name, e.g. both sides of a road)
        self.stop_name = dict(zip(stops.stop_id, stops.stop_name))
        self.coords = dict(zip(stops.stop_id, zip(stops.stop_lat, stops.stop_lon)))
        self.route_desc = dict(zip(routes.route_short_name, routes.route_desc.fillna("")))
        ids, self.display = defaultdict(set), {}
        for sid, nm in zip(stops.stop_id, stops.stop_name):
            k = norm(nm)
            ids[k].add(sid)
            self.display.setdefault(k, str(nm).strip())
        self.ids_arr = {k: np.array(sorted(v)) for k, v in ids.items()}

        # ---- every trip as arrays (stop ids, arrival secs, departure secs)
        route_of = dict(zip(trips.trip_id, trips.route_id))
        short = dict(zip(routes.route_id, routes.route_short_name))
        tid = st.trip_id.to_numpy()
        sid, arr, dep = st.stop_id.to_numpy(), st.arr.to_numpy(), st.dep.to_numpy()
        cut = np.flatnonzero(tid[1:] != tid[:-1]) + 1
        starts, ends = np.r_[0, cut], np.r_[cut, len(tid)]

        self.trip = {}
        self.trips_of_route = defaultdict(list)
        longest = {}
        for s, e in zip(starts, ends):
            t = tid[s]
            r = short.get(route_of.get(t))
            if r is None:
                continue
            self.trip[t] = (sid[s:e], arr[s:e], dep[s:e])
            self.trips_of_route[r].append(t)
            n = e - s
            # keep the trip with the most stops (smallest trip id wins a tie)
            if r not in longest or n > longest[r][0] or (n == longest[r][0] and t < longest[r][1]):
                longest[r] = (n, t)

        # ---- one standard stop list per route (its longest trip), same idea as the notebook
        self.pattern, self.pattern_ids, self.routes_at = {}, {}, defaultdict(list)
        for r, (_, t) in longest.items():
            names = [norm(self.stop_name[x]) for x in self.trip[t][0]]
            pos = {}
            for i, nm in enumerate(names):
                pos.setdefault(nm, i)
            self.pattern[r] = (names, pos)
            self.pattern_ids[r] = list(self.trip[t][0])
            for nm in pos:
                self.routes_at[nm].append(r)

        # ---- for browsing: searchable text per route, and one point per bus stop name
        self.route_text = {r: "|".join(names) for r, (names, _) in self.pattern.items()}
        self.stop_points = []
        for nm, rs in self.routes_at.items():
            pts = [self.coords[x] for x in self.ids_arr[nm]]
            la, lo = float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))
            if 28.0 < la < 29.5 and 76.0 < lo < 78.0:          # keep only points inside Delhi NCR
                self.stop_points.append({"name": self.display[nm], "lat": la, "lon": lo, "n": len(rs)})

        # ---- crowding table, looked up by (route, from stop, to stop, band, daytype)
        c = pd.read_csv(crowding_file, usecols=[
            "route", "band", "daytype", "crowd_index", "low_confidence", "from_stop", "to_stop"])
        good = c[c.crowd_index.notna() & ~c.low_confidence].crowd_index
        self.seats_max, self.standing_max = good.quantile([0.50, 0.85])
        c = c.dropna(subset=["crowd_index", "from_stop", "to_stop"]).copy()
        c["f"], c["t"] = c.from_stop.map(norm), c.to_stop.map(norm)
        g = c.groupby(["route", "f", "t", "band", "daytype"]).agg(
            ci=("crowd_index", "mean"), low=("low_confidence", "min"))
        self.crowd = dict(zip(g.index, zip(g.ci, g.low)))

    # ------------------------------------------------------------ helpers
    def level(self, idx):
        if idx is None:
            return "No data"
        if idx <= self.seats_max:
            return "Seats available"
        return "Standing room" if idx <= self.standing_max else "Crowded"

    def find_stop(self, text):
        """Exact (ignoring spaces/symbols) or closest stop name."""
        k = norm(text)
        if k in self.ids_arr:
            return k
        m = difflib.get_close_matches(k, self.ids_arr.keys(), n=1, cutoff=0.8)
        return m[0] if m else None

    def search_stops(self, q, limit=15):
        k = norm(q)
        if len(k) < 2:
            return []
        starts = [v for n, v in self.display.items() if n.startswith(k)]
        inside = [v for n, v in self.display.items() if k in n and not n.startswith(k)]
        return sorted(starts)[:limit] + sorted(inside)[: max(0, limit - len(starts))]

    def leg_crowding(self, route, i, j, band, daytype):
        """Crowding on the stretches from position i to position j of the route."""
        names, _ = self.pattern[route]
        vals, low, peak = [], 0, None
        for k in range(i, j):
            v = self.crowd.get((route, names[k], names[k + 1], band, daytype))
            if v:
                vals.append(v[0])
                low += bool(v[1])
                if peak is None or v[0] > peak[0]:
                    peak = (v[0], k)
        if not vals:
            return {"level": "No data", "index": None, "coverage": 0.0, "low_confidence": True,
                    "peak_level": "No data", "peak_from": None, "peak_to": None}
        mean = float(np.mean(vals))
        return {"level": self.level(mean), "index": round(mean, 2),
                "coverage": round(len(vals) / (j - i), 2),
                "low_confidence": bool(low / len(vals) > 0.5 or len(vals) / (j - i) < 0.5),
                "peak_level": self.level(peak[0]),
                "peak_from": self.display[names[peak[1]]], "peak_to": self.display[names[peak[1] + 1]]}

    def next_trip(self, route, a, b, after):
        """Earliest trip of `route` leaving stop-name a at/after `after` that later reaches stop-name b."""
        fa, ta = self.ids_arr[a], self.ids_arr[b]
        best = None
        for t in self.trips_of_route[route]:
            s, arr, dep = self.trip[t]
            fi = np.flatnonzero(np.isin(s, fa))
            if not len(fi):
                continue
            i = fi[0]
            ti = np.flatnonzero(np.isin(s[i + 1:], ta))
            if not len(ti):
                continue
            j = i + 1 + ti[0]
            if dep[i] >= after and (best is None or dep[i] < best[0]):
                best = (int(dep[i]), int(arr[j]))
        return best

    def trips_between(self, route, a, b, lo, hi):
        """Every trip of `route` that leaves stop-name a between lo and hi (seconds) and later reaches b."""
        fa, ta = self.ids_arr[a], self.ids_arr[b]
        found = {}
        for t in self.trips_of_route[route]:
            s, arr, dep = self.trip[t]
            fi = np.flatnonzero(np.isin(s, fa))
            if not len(fi):
                continue
            i = fi[0]
            ti = np.flatnonzero(np.isin(s[i + 1:], ta))
            if not len(ti):
                continue
            d0 = int(dep[i])
            if lo <= d0 <= hi:
                found[d0] = int(arr[i + 1 + ti[0]])
        return sorted(found.items())

    def make_leg(self, route, a, b, dep, arr, daytype, now=None):
        names, pos = self.pattern[route]
        band = HOUR_TO_BAND[(dep // 3600) % 24]
        return {"route": route, "board": self.display[a], "alight": self.display[b],
                "depart": hhmm(dep), "arrive": hhmm(arr), "ride_min": round((arr - dep) / 60),
                "stops": pos[b] - pos[a], "band": band,
                "crowding": self.leg_crowding(route, pos[a], pos[b], band, daytype),
                "now": self._now_crowding(route, pos[a], pos[b], now),
                "_dep": dep, "_arr": arr}

    def _now_crowding(self, route, i, j, now):
        """Usual crowding on this stretch at the current time of day (now = (band, daytype))."""
        if not now:
            return None
        c = self.leg_crowding(route, i, j, now[0], now[1])
        return {"level": c["level"], "index": c["index"], "band": now[0]}

    # ------------------------------------------------------------ main search
    def journeys(self, frm, to, depart, daytype="weekday", sort="fastest", limit=8, now=None, now_day=None):
        a, b = self.find_stop(frm), self.find_stop(to)
        if a is None or b is None:
            return {"error": "Stop not found: " + (frm if a is None else to)}
        if a == b:
            return {"error": "From and to are the same stop"}
        h, m = (int(x) for x in depart.split(":"))
        t0 = h * 3600 + m * 60
        now_ctx = None
        if now:
            now_ctx = (HOUR_TO_BAND[int(now.split(":")[0]) % 24], now_day or daytype)
        lo, hi = t0 - 30 * 60, t0 + 90 * 60          # we look 30 min before and 90 min after the asked time
        options = []                                  # (kind, legs, nearby times)

        # ---- direct buses: every departure in the window, grouped per route
        for r in self.routes_at[a]:
            _, pos = self.pattern[r]
            if b not in pos or pos[a] >= pos[b]:
                continue
            ts = self.trips_between(r, a, b, lo, hi)
            legs = [self.make_leg(r, a, b, d, ar, daytype, now_ctx) for d, ar in ts]
            upcoming = [l for l in legs if l["_dep"] >= t0]
            if not upcoming:
                continue
            if sort == "comfortable":     # the least crowded departure of this bus in the window
                head = min(upcoming, key=lambda l: (
                    LEVEL_RANK[l["crowding"]["level"]],
                    l["crowding"]["index"] if l["crowding"]["index"] is not None else 99, l["_dep"]))
            else:                         # the next departure
                head = upcoming[0]
            nearby = [{"depart": l["depart"], "arrive": l["arrive"], "level": l["crowding"]["level"],
                       "index": l["crowding"]["index"], "mins": round((l["_dep"] - t0) / 60),
                       "chosen": l is head} for l in legs]
            options.append(("direct", [head], nearby))
        direct_found = len(options) > 0

        # ---- one change: pick the transfer stop with the fewest stops overall
        pairs = []
        for r1 in self.routes_at[a]:
            n1, p1 = self.pattern[r1]
            for r2 in self.routes_at[b]:
                if r1 == r2:
                    continue
                n2, p2 = self.pattern[r2]
                if p2[b] == 0:
                    continue
                best = None
                for i in range(p1[a] + 1, len(n1)):
                    nm = n1[i]
                    if nm in p2 and p2[nm] < p2[b] and nm not in (a, b):
                        cost = (i - p1[a]) + (p2[b] - p2[nm])
                        if best is None or cost < best[0]:
                            best = (cost, nm)
                if best:
                    pairs.append((best[0], r1, r2, best[1]))
        pairs.sort()
        want = 2 if direct_found else 6
        taken = 0
        for _, r1, r2, x in pairs[:80]:
            l1 = self.next_trip(r1, a, x, t0)
            if not l1:
                continue
            l2 = self.next_trip(r2, x, b, l1[1] + TRANSFER_BUFFER)
            if not l2:
                continue
            options.append(("transfer", [self.make_leg(r1, a, x, l1[0], l1[1], daytype, now_ctx),
                                         self.make_leg(r2, x, b, l2[0], l2[1], daytype, now_ctx)], None))
            taken += 1
            if taken == want:
                break

        # drop buses that leave more than 90 minutes after the asked time
        options = [o for o in options if o[1][0]["_dep"] - t0 <= 90 * 60]

        # ---- summarise each option
        result, seen = [], set()
        for kind, legs, nearby in options:
            key = tuple((l["route"], l["depart"]) for l in legs)
            if key in seen:
                continue
            seen.add(key)
            idxs = [l["crowding"]["index"] for l in legs if l["crowding"]["index"] is not None]
            worst = max(idxs) if idxs else None
            end, start = legs[-1]["_arr"], legs[0]["_dep"]
            result.append({
                "kind": kind, "legs": [{k: v for k, v in l.items() if not k.startswith("_")} for l in legs],
                "nearby": nearby, "depart": hhmm(start), "arrive": hhmm(end),
                "total_min": round((end - t0) / 60), "wait_min": round((start - t0) / 60),
                "changes": len(legs) - 1,
                "change_at": legs[0]["alight"] if len(legs) > 1 else None,
                "change_wait_min": round((legs[1]["_dep"] - legs[0]["_arr"]) / 60) if len(legs) > 1 else None,
                "crowd_index": worst, "level": self.level(worst),
                "low_confidence": any(l["crowding"]["low_confidence"] for l in legs)})

        if sort == "comfortable":
            result.sort(key=lambda o: (LEVEL_RANK[o["level"]], o["crowd_index"] or 0, o["total_min"]))
        else:
            result.sort(key=lambda o: o["total_min"])
        result = result[:limit]
        fastest = min((o["total_min"] for o in result), default=0)
        for o in result:
            o["minutes_slower_than_fastest"] = o["total_min"] - fastest
        return {"from": self.display[a], "to": self.display[b], "depart": depart,
                "daytype": daytype, "sort": sort, "direct_found": direct_found,
                "window": [hhmm(lo), hhmm(hi)], "options": result}

    # ------------------------------------------------------------ route map
    def search_routes(self, q, limit=15):
        k = norm(q)
        if not k:
            return []
        hits = [r for r in self.pattern if norm(r).startswith(k)]
        hits += [r for r in self.pattern if k in norm(r) and not norm(r).startswith(k)]
        return [{"route": r, "desc": self.route_desc.get(r, "")} for r in sorted(hits)[:limit]]

    def route_map(self, route, depart, daytype="weekday", board=None, alight=None):
        """All stops of a route with coordinates, and the crowding of every stretch at this time."""
        if route not in self.pattern:
            return {"error": "Route not found: " + route}
        names, pos = self.pattern[route]
        h = int(depart.split(":")[0])
        band = HOUR_TO_BAND[h % 24]
        i0 = pos.get(norm(board)) if board else None
        j0 = pos.get(norm(alight)) if alight else None
        stops = []
        for sid, nm in zip(self.pattern_ids[route], names):
            lat, lon = self.coords[sid]
            stops.append({"name": self.display[nm], "lat": float(lat), "lon": float(lon)})
        stretches = []
        for k in range(len(names) - 1):
            c = self.leg_crowding(route, k, k + 1, band, daytype)
            in_trip = True if i0 is None or j0 is None else (i0 <= k < j0)
            stretches.append({"level": c["level"], "index": c["index"],
                              "low_confidence": c["low_confidence"], "in_trip": in_trip})
        return {"route": route, "desc": self.route_desc.get(route, ""), "band": band,
                "daytype": daytype, "stops": stops, "stretches": stretches}

    # ------------------------------------------------------------ browse without knowing the route number
    def browse_routes(self, q, limit=80):
        """Routes matching a bus number, a place in the route name, or ANY stop on the route."""
        k = norm(q)
        if len(k) < 2:
            return {"total": 0, "routes": []}
        found = []
        for r, text in self.route_text.items():
            rn, desc = norm(r), self.route_desc.get(r, "")
            via = None
            if rn == k:
                score = 0
            elif rn.startswith(k):
                score = 1
            elif k in norm(desc):
                score = 2
            elif k in text:
                score = 3
                names, _ = self.pattern[r]
                via = next(self.display[n] for n in names if k in n)
            else:
                continue
            found.append((score, r, via))
        found.sort(key=lambda x: (x[0], x[1]))
        routes = [{"route": r, "desc": self.route_desc.get(r, ""), "stops": len(self.pattern[r][0]), "via": via}
                  for _, r, via in found[:limit]]
        return {"total": len(found), "routes": routes}

    def stop_info(self, name, depart=None, limit=60, per_route=3):
        """All buses that stop at a bus stop, with their next scheduled times after `depart` (HH:MM)."""
        k = self.find_stop(name)
        if k is None or k not in self.routes_at:
            return {"error": "Stop not found: " + name}
        after = None
        if depart:
            h, m = (int(x) for x in depart.split(":"))
            after = h * 3600 + m * 60
        ids = self.ids_arr[k]
        rows = []
        for r in self.routes_at[k]:
            times = []
            for t in self.trips_of_route[r]:
                s, _, dep = self.trip[t]
                hit = np.flatnonzero(np.isin(s, ids))
                if len(hit):
                    times.append(int(dep[hit[0]]))
            if not times:
                continue
            times.sort()
            nxt = [x for x in times if after is None or x >= after][:per_route]
            rows.append({"route": r, "desc": self.route_desc.get(r, ""),
                         "next": [hhmm(x) for x in nxt], "first": hhmm(times[0]), "last": hhmm(times[-1]),
                         "all": [hhmm(x).replace(" (next day)", "*") for x in times],     # whole day, * = after midnight
                         "upcoming_from": sum(1 for x in times if after is not None and x < after),
                         "_sort": nxt[0] if nxt else 10 ** 9})
        rows.sort(key=lambda x: (x["_sort"], x["route"]))      # buses coming soonest first
        for x in rows:
            del x["_sort"]
        return {"name": self.display[k], "total": len(rows), "after": depart, "routes": rows[:limit]}
