"""
TRADON web screen + API.

Run:   py app.py data
Open:  http://127.0.0.1:5000        (the route map needs internet for the map tiles)

The data folder must contain: routes.txt, trips.txt, stops.txt, stop_times.txt, crowding_by_band.csv
API examples:
  GET /journeys?from=ISBT Kashmere Gate&to=Nehru Place&depart=08:30&day=weekday&sort=comfortable
  GET /routes?q=717
  GET /routemap?route=717AUP&depart=09:00&day=weekday
  GET /browse?q=nehru place          (routes by number, place name or any stop on the route)
  GET /stopinfo?name=Nehru Place&depart=08:30   (buses at a stop with next scheduled times)
  GET /allstops                      (every bus stop with coordinates)
"""
import sys
from flask import Flask, jsonify, request, render_template_string
from planner import Planner

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"
app = Flask(__name__)
planner = Planner(DATA_DIR, f"{DATA_DIR}/crowding_by_band.csv")


@app.get("/stops")
def stops():
    return jsonify(planner.search_stops(request.args.get("q", "")))


@app.get("/routes")
def routes():
    return jsonify(planner.search_routes(request.args.get("q", "")))


@app.get("/journeys")
def journeys():
    res = planner.journeys(request.args.get("from", ""), request.args.get("to", ""),
                           request.args.get("depart", "08:30"),
                           request.args.get("day", "weekday"),
                           request.args.get("sort", "fastest"))
    return jsonify(res), (400 if "error" in res else 200)


@app.get("/routemap")
def routemap():
    res = planner.route_map(request.args.get("route", ""), request.args.get("depart", "08:30"),
                            request.args.get("day", "weekday"),
                            request.args.get("board") or None, request.args.get("alight") or None)
    return jsonify(res), (400 if "error" in res else 200)


@app.get("/browse")
def browse():
    return jsonify(planner.browse_routes(request.args.get("q", "")))


@app.get("/stopinfo")
def stopinfo():
    res = planner.stop_info(request.args.get("name", ""), request.args.get("depart") or None)
    return jsonify(res), (400 if "error" in res else 200)


@app.get("/allstops")
def allstops():
    return jsonify(planner.stop_points)


@app.get("/")
def home():
    return render_template_string(PAGE)


PAGE = """
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TRADON - Delhi bus planner with crowding</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  body{font-family:system-ui,Arial,sans-serif;max-width:1090px;margin:24px auto;padding:0 14px;color:#51a529;background:#f6f7fb}
  h1{font-size:35px;margin-bottom:4px}
   h2{font-size:22px;margin:0 0 8px}
     .sub{color:#5b6475;margin-bottom:18px}
  .box{background:#fff;border-radius:10px;padding:26px;box-shadow:0 1px 4px #0001;margin-bottom:12px}
  label{display:block;font-size:13px;color:#5b6475;margin:10px 0 4px}
  input,select{width:100%;padding:9px;border:1px solid #ccd2de;border-radius:6px;font-size:15px;box-sizing:border-box}
  .row{display:flex;gap:10px} .row>div{flex:1}
  button{margin-top:14px;padding:10px 18px;border:0;border-radius:6px;background:#2457d6;color:#fff;font-size:15px;cursor:pointer}
  .opt{background:#fff;border-radius:10px;padding:14px;margin-top:12px;box-shadow:0 1px 4px #0001}
  .top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
  .time{font-size:18px;font-weight:600} .meta{color:#5b6475;font-size:13px}
  .badge{padding:3px 10px;border-radius:12px;font-size:13px;font-weight:600;color:#fff;white-space:nowrap}
  .Seats{background:#2e9e5b} .Standing{background:#e0a100} .Crowded{background:#d6402b} .Nodata{background:#8a93a5}
  .leg{border-top:1px solid #eef0f5;margin-top:10px;padding-top:8px;font-size:14px}
  .rt{cursor:pointer;color:#2457d6;text-decoration:underline}
  .tag{font-size:12px;color:#2457d6;margin-left:6px} .err{color:#d6402b;margin-top:12px}
  .note{font-size:12px;color:#5b6475;margin-top:16px}
  #mapbox{display:none}
  .mapwrap{display:flex;gap:12px;flex-wrap:wrap}
  #map{flex:2;min-width:300px;height:440px;border-radius:8px}
  #line{flex:1;min-width:220px;max-height:440px;overflow-y:auto;padding-right:6px}
  .stp{display:flex;gap:10px;min-height:34px}
  .rail{width:16px;display:flex;flex-direction:column;align-items:center}
  .dot{width:11px;height:11px;border-radius:50%;background:#fff;border:2px solid #333;flex:none}
  .bar{flex:1;width:6px;min-height:18px}
  .nm{font-size:13px;padding-bottom:8px}
  .ritem{padding:8px 6px;border-top:1px solid #eef0f5;cursor:pointer;font-size:14px}
  .ritem:hover{background:#f0f4ff} .ritem b{color:#2457d6;margin-right:6px}
  #blist{max-height:300px;overflow-y:auto;margin-top:8px}
  .btn2{background:#fff;color:#2457d6;border:1px solid #2457d6;margin-top:10px}
  .nm.click{cursor:pointer} .nm.click:hover{color:#2457d6;text-decoration:underline}
  .lg{display:flex;align-items:center;gap:8px;margin:7px 0;font-size:13px;cursor:pointer}
  .lg i{width:28px;height:6px;border-radius:3px;flex:none}
  .legend span{display:inline-block;margin-right:12px;font-size:12px}
  .legend i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:4px}
</style></head><body>
<div class="hero-banner">
  <center><h1 data-i18n="hero_title">Crowdedness-Aware Journey Planner</h1>
  <div class="sub" data-i18n="hero_sub">Team TOROUS &bull; Transport Stack Hackathon 2026</div>
</div></center>

<div class="box">
  <label>From (start typing a stop name)</label>
  <input id="from" list="stoplist" autocomplete="off" placeholder="e.g. ISBT Kashmere Gate">
  <label>To</label>
  <input id="to" list="stoplist" autocomplete="off" placeholder="e.g. Nehru Place">
  <datalist id="stoplist"></datalist>
  <div class="row">
    <div><label>Leaving at</label><input id="depart" type="time" value="08:30"></div>
    <div><label>Day</label><select id="day"><option value="weekday">Weekday</option><option value="weekend">Weekend</option></select></div>
    <div><label>Show me</label><select id="sort"><option value="fastest">Fastest first</option><option value="comfortable">Most comfortable first</option></select></div>
  </div>
  <button onclick="go()">Find buses</button>
</div>

<div class="box">
  <h2>Find a bus without knowing its number</h2>
  <input id="bq" autocomplete="off" placeholder="Type a place, bus stand or stop name (e.g. Nehru Place, ISBT) or a bus number">
  <div class="meta" style="margin-top:6px">Shows every bus that goes there. Click a bus to see where it goes, stop by stop, on the map.</div>
  <div id="blist"></div>
  <button class="btn2" onclick="showAllStops()">Show all bus stops on the map</button>
</div>

<div class="box" id="mapbox">
  <h2 id="maptitle"></h2>
  <div class="meta" id="mapsub" style="margin-bottom:8px"></div>
  <div class="legend" id="legend"><span><i style="background:#2e9e5b"></i>Seats available</span><span><i style="background:#e0a100"></i>Standing room</span><span><i style="background:#d6402b"></i>Crowded</span><span><i style="background:#8a93a5"></i>No data</span></div>
  <div class="mapwrap" style="margin-top:10px"><div id="map"></div><div id="line"></div></div>
</div>

<div id="out"></div>
<div class="note">Crowding is estimated from ticket data (Oct 2026) per route, stretch and time of day. Walking to the stop is not included.
"Low data" means few tickets back that estimate. Map lines join the stops in order (not the exact road shape).</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const COL = {'Seats available':'#2e9e5b','Standing room':'#e0a100','Crowded':'#d6402b','No data':'#8a93a5'};
let OPTS = [], map = null, layer = null, CUR = null;

async function suggest(e){
  const q = e.target.value; if(q.length < 2) return;
  const r = await fetch('/stops?q=' + encodeURIComponent(q)); const names = await r.json();
  $('stoplist').innerHTML = names.map(n => `<option value="${esc(n)}">`).join('');
}
$('from').addEventListener('input', suggest); $('to').addEventListener('input', suggest);
const cls = l => l.startsWith('Seats') ? 'Seats' : l.startsWith('Standing') ? 'Standing' : l === 'Crowded' ? 'Crowded' : 'Nodata';
const badge = l => `<span class="badge ${cls(l)}">${l}</span>`;

async function go(){
  const p = new URLSearchParams({from:$('from').value, to:$('to').value, depart:$('depart').value,
                                 day:$('day').value, sort:$('sort').value});
  const r = await fetch('/journeys?' + p); const d = await r.json();
  if(d.error){ $('out').innerHTML = `<div class="err">${esc(d.error)}</div>`; return; }
  if(!d.options.length){ $('out').innerHTML = '<div class="err">No bus found for this time. Try another time or stop.</div>'; return; }
  OPTS = d.options;
  $('out').innerHTML = d.options.map((o, oi) => {
    const kind = o.kind === 'direct_later' ? 'Later bus' : o.changes ? `${o.changes} change` : 'Direct';
    const slower = o.minutes_slower_than_fastest ? ` (+${o.minutes_slower_than_fastest} min vs fastest)` : '';
    const legs = o.legs.map((l, li) => {
      const c = l.crowding;
      const peak = c.peak_from && c.peak_level !== c.level ? `<br><span class="meta">Busiest part: ${esc(c.peak_from)} to ${esc(c.peak_to)} (${c.peak_level})</span>` : '';
      return `<div class="leg"><b class="rt" title="Show this bus on the map" onclick="showLeg(${oi},${li})">${esc(l.route)}</b> ${l.depart} ${esc(l.board)} &rarr; ${l.arrive} ${esc(l.alight)}
        <span class="meta">(${l.ride_min} min, ${l.stops} stops)</span> ${badge(c.level)}${c.low_confidence && c.level!=='No data' ? '<span class="tag">low data</span>' : ''}${peak}</div>`;
    }).join('');
    return `<div class="opt"><div class="top"><div><span class="time">${o.depart} &rarr; ${o.arrive}</span>
      <span class="meta"> ${o.total_min} min in total${slower}</span><span class="tag">${kind}</span><span class="tag rt" onclick="showOption(${oi})">Show on map</span></div>${badge(o.level)}</div>${legs}</div>`;
  }).join('');
}

function showLeg(oi, li){ const l = OPTS[oi].legs[li]; showMap(l.route, l.board, l.alight, l.depart); }

function ensureMap(){
  $('mapbox').style.display = 'block';          // must be visible before Leaflet draws the map
  if(!map){
    map = L.map('map', {preferCanvas: true});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}).addTo(map);
    layer = L.layerGroup().addTo(map);
  }
  layer.clearLayers();
  map.closePopup();
}

// ---- find buses by place / stop / number
let bTimer = null;
$('bq').addEventListener('input', () => { clearTimeout(bTimer); bTimer = setTimeout(browse, 300); });

async function browse(){
  const q = $('bq').value.trim();
  if(q.length < 2){ $('blist').innerHTML = ''; return; }
  const r = await fetch('/browse?q=' + encodeURIComponent(q)); const d = await r.json();
  if(!d.routes.length){ $('blist').innerHTML = '<div class="meta" style="padding:8px">No bus found. Try another spelling or a nearby place.</div>'; return; }
  const more = d.total > d.routes.length ? `<div class="meta" style="padding:8px">Showing ${d.routes.length} of ${d.total} buses. Type more letters to narrow down.</div>` : `<div class="meta" style="padding:8px 6px 0">${d.total} bus(es) found</div>`;
  const btn = '<button class="btn2" style="margin:6px" onclick="showTop()">Show these on the map (a colour for each bus)</button>';
  $('blist').innerHTML = more + btn + d.routes.map((x, i) =>
    `<div class="ritem" onclick="showMap(BROWSE[${i}].route,'','',null)"><b>${esc(x.route)}</b>${esc(x.desc.replace(' to ', ' \u2192 '))}
     <span class="meta"> &middot; ${x.stops} stops${x.via ? ' &middot; via ' + esc(x.via) : ''}</span></div>`).join('');
  BROWSE = d.routes;
}
let BROWSE = [];

// ---- every bus stop on the map; click a dot to see the buses that stop there
async function showAllStops(){
  const r = await fetch('/allstops'); const pts = await r.json();
  ensureMap(); CUR = null;
  $('legend').style.display = 'none';
  $('maptitle').textContent = 'All bus stops (' + pts.length + ')';
  $('mapsub').textContent = 'Click any dot to see the buses that stop there. Zoom in to see stops closer.';
  $('line').innerHTML = '<div class="meta">Click a stop on the map, then click a bus number to see its full route.</div>';
  pts.forEach(s => {
    L.circleMarker([s.lat, s.lon], {radius: 3, color: '#2457d6', weight: 1, fillColor: '#2457d6', fillOpacity: 0.7})
      .bindTooltip(esc(s.name)).on('click', () => stopPopup(s)).addTo(layer);
  });
  map.fitBounds(pts.map(s => [s.lat, s.lon]), {padding: [20, 20]});
  setTimeout(() => map.invalidateSize(), 100);
  $('mapbox').scrollIntoView({behavior: 'smooth'});
}

async function stopPopup(s){
  const r = await fetch('/stopinfo?name=' + encodeURIComponent(s.name) + '&depart=' + encodeURIComponent($('depart').value));
  const d = await r.json();
  if(d.error) return;
  const rows = d.routes.map(x => {
    const times = x.next.length ? x.next.join(', ') : '<span style="color:#d6402b">no more buses today</span>';
    return `<div style="border-top:1px solid #eee;padding:4px 0"><a href="#" onclick="showMap('${esc(x.route)}','','',null);return false"><b>${esc(x.route)}</b></a>
      <span style="color:#5b6475;font-size:11px">${esc(x.desc.replace(' to ', ' \u2192 '))}</span><br>Next: <b>${times}</b>
      <span style="color:#5b6475;font-size:11px"> (last bus ${x.last})</span>
      <details><summary style="cursor:pointer;color:#2457d6;font-size:12px">All timings today (${x.all.length} buses)</summary>
      <div style="font-size:12px;line-height:1.7">${x.all.map((tm, i) => i >= x.upcoming_from ? '<b>' + tm + '</b>' : '<span style="color:#9aa3b5">' + tm + '</span>').join(', ')}
      <div style="color:#5b6475;font-size:11px">Dark = still to come. Grey = already gone. * = after midnight.</div></div></details></div>`;
  }).join('');
  const more = d.total > d.routes.length ? `<div style="font-size:11px;color:#5b6475">Showing ${d.routes.length} of ${d.total} buses</div>` : '';
  L.popup({maxWidth: 340}).setLatLng([s.lat, s.lon])
    .setContent(`<b>${esc(d.name)}</b><div style="font-size:12px;color:#5b6475">Scheduled buses after ${esc(d.after || 'now')}</div>
      <div style="max-height:300px;overflow-y:auto;font-size:13px">${rows}</div>${more}`).openOn(map);
}

function focusStop(k){
  if(!CUR) return;
  const s = CUR.stops[k];
  map.setView([s.lat, s.lon], 15);
  stopPopup(s);
}

// ---- several buses on one map, each bus in its own colour (like metro lines)
const PALETTE = ['#e6194b','#3cb44b','#4363d8','#f58231','#911eb4','#008b8b','#f032e6','#9a6324','#800000','#000075','#808000','#e6a700'];

function showOption(oi){ showRoutes(OPTS[oi].legs.map(l => ({route: l.route, board: l.board, alight: l.alight}))); }

function showTop(){
  // UP and DOWN of the same bus use the same road, so keep one of them; show at most 8 buses
  const seen = new Set(), items = [];
  for(const x of BROWSE){
    const base = x.route.replace(/(UP|DOWN)$/, '');
    if(seen.has(base)) continue;
    seen.add(base); items.push({route: x.route, board: '', alight: ''});
    if(items.length === 8) break;
  }
  showRoutes(items);
}

async function showRoutes(items){
  const results = await Promise.all(items.map(it =>
    fetch('/routemap?' + new URLSearchParams({route: it.route, depart: $('depart').value, day: $('day').value,
                                              board: it.board || '', alight: it.alight || ''})).then(r => r.json())));
  const ok = results.filter(d => !d.error);
  if(!ok.length) return;

  ensureMap(); CUR = null;
  $('legend').style.display = 'none';
  $('maptitle').textContent = ok.length === 1 ? 'Route ' + ok[0].route : ok.length + ' buses on the map';
  $('mapsub').textContent = 'Each bus has its own colour. Click a stop to see all buses there, or a bus name on the right to see it alone.';

  const all = [];
  ok.forEach((d, i) => {
    const col = PALETTE[i % PALETTE.length];
    const pts = d.stops.map(s => [s.lat, s.lon]);
    all.push(...pts);
    const partial = d.stretches.some(s => !s.in_trip);      // only part of the route is used in the journey
    L.polyline(pts, {color: col, weight: partial ? 3 : 5, opacity: partial ? 0.4 : 0.9}).addTo(layer);
    if(partial){
      d.stretches.forEach((s, k) => { if(s.in_trip) L.polyline([pts[k], pts[k+1]], {color: col, weight: 7, opacity: 0.95}).addTo(layer); });
    }
    d.stops.forEach((s, k) => {
      const end = k === 0 || k === d.stops.length - 1;
      L.circleMarker(pts[k], {radius: end ? 6 : 3, color: col, weight: 2, fillColor: '#fff', fillOpacity: 1})
        .bindTooltip(esc(s.name) + ' (' + esc(d.route) + ')').on('click', () => stopPopup(s)).addTo(layer);
    });
  });
  map.fitBounds(all, {padding: [20, 20]});
  setTimeout(() => map.invalidateSize(), 100);

  $('line').innerHTML = ok.map((d, i) =>
    `<div class="lg" onclick="showMap('${esc(d.route)}','','',null)" title="Show only this bus"><i style="background:${PALETTE[i % PALETTE.length]}"></i><span><b>${esc(d.route)}</b><br><span class="meta">${esc(d.desc.replace(' to ', ' \u2192 '))}</span></span></div>`).join('');
  $('mapbox').scrollIntoView({behavior: 'smooth'});
}

async function showMap(route, board, alight, depart){
  const p = new URLSearchParams({route, depart: depart || $('depart').value, day: $('day').value, board, alight});
  const r = await fetch('/routemap?' + p); const d = await r.json();
  if(d.error){ $('out').insertAdjacentHTML('afterbegin', `<div class="err">${esc(d.error)}</div>`); return; }

  ensureMap();
  CUR = d;
  $('legend').style.display = 'block';
  $('maptitle').textContent = 'Route ' + d.route + (d.desc ? ' - ' + d.desc : '');
  $('mapsub').textContent = `Crowding shown for: ${d.band}, ${d.daytype}` + (board ? `. Thick line = your ride (${board} to ${alight}).` : '.');

  const pts = d.stops.map(s => [s.lat, s.lon]);
  d.stretches.forEach((s, k) => {
    L.polyline([pts[k], pts[k+1]], {color: COL[s.level], weight: s.in_trip ? 7 : 3, opacity: s.in_trip ? 0.95 : 0.45})
      .bindTooltip(`${esc(d.stops[k].name)} to ${esc(d.stops[k+1].name)}: ${s.level}`).addTo(layer);
  });
  d.stops.forEach((s, k) => {
    const end = k === 0 || k === d.stops.length - 1;
    L.circleMarker(pts[k], {radius: end ? 6 : 3, color: '#222', fillColor: '#fff', fillOpacity: 1, weight: 1.5})
      .bindTooltip(esc(s.name)).on('click', () => stopPopup(s)).addTo(layer);
  });
  map.fitBounds(pts, {padding: [20, 20]});
  setTimeout(() => map.invalidateSize(), 100);

  // metro-style line: one row per stop, coloured bar to the next stop
  $('line').innerHTML = d.stops.map((s, k) => {
    const st = d.stretches[k];
    const bar = st ? `<div class="bar" style="background:${COL[st.level]};opacity:${st.in_trip ? 1 : 0.4}" title="${st.level}"></div>` : '';
    return `<div class="stp"><div class="rail"><div class="dot"></div>${bar}</div><div class="nm click" title="Buses at this stop" onclick="focusStop(${k})">${esc(s.name)}</div></div>`;
  }).join('');
  $('mapbox').scrollIntoView({behavior: 'smooth'});
}
</script></body></html>
"""

if __name__ == "__main__":
    app.run(debug=False)
