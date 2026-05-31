"""Tiny socket-based web server. Serves the dashboard, JSON archive, and time-sync."""

import json
import socket

import logger

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adapter Archive</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin="" />
<style>
  :root { color-scheme: light; }
  html, body { margin:0; padding:0; background:#fafafa; color:#1a1a1a;
    font-family: -apple-system, system-ui, sans-serif; }
  header { padding: 1.25rem 1.5rem 0.75rem; }
  h1 { margin:0; font-weight:500; letter-spacing:0.12em; text-transform:uppercase;
    font-size:0.85rem; color:#555; }
  .sub { font-size:0.75rem; color:#999; margin-top:0.25rem; }
  #map { height: 45vh; background: #e8e8e8; }
  .leaflet-container { background: #e8e8e8; }
  main { padding: 0.5rem 1.5rem 2rem; }
  .entry { border:1px solid #e5e5e5; padding:1rem; margin:0.75rem 0; border-radius:8px;
    background:#fff; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
  .entry.latest { border-color:#ff3b30;
    box-shadow: 0 0 0 1px rgba(255,59,48,0.15), 0 2px 8px rgba(255,59,48,0.08); }
  .id { font-family: ui-monospace, monospace; font-size:0.7rem; color:#999;
    letter-spacing:0.05em; }
  .ts { font-family: ui-monospace, monospace; font-size:0.95rem; margin:0.35rem 0;
    color:#1a1a1a; }
  .row { display:flex; flex-wrap:wrap; gap:1.25rem; font-size:0.85rem; color:#444;
    margin-top:0.5rem; }
  .row a { color:#0066cc; text-decoration:none; }
  .row a:hover { text-decoration:underline; }
  .empty { color:#999; font-style:italic; padding:1rem; }
  .pulse { animation: pulse 1.6s ease-out infinite; transform-origin: center; }
  @keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
  }
</style>
</head>
<body>
<header>
  <h1>Adapter Archive</h1>
  <div class="sub" id="sub">loading…</div>
</header>
<div id="map"></div>
<main>
  <div id="entries"></div>
</main>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
        crossorigin=""></script>
<script>
// Tell the board what time it is. The board has no RTC battery.
fetch('/sync-time?t=' + new Date().toISOString().slice(0,19), { method: 'POST' })
  .catch(() => {});

const map = L.map('map', { zoomControl: true, attributionControl: false })
  .setView([51.5, -0.12], 3);  // default world-ish view
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
}).addTo(map);

let markers = [];

async function load() {
  let data;
  try {
    const r = await fetch('/entries.json');
    data = await r.json();
  } catch (e) {
    document.getElementById('sub').textContent = 'offline';
    return;
  }

  document.getElementById('sub').textContent =
    data.length + ' ' + (data.length === 1 ? 'entry' : 'entries');

  // Clear previous pins
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  const located = data.filter(e => e.location && e.location.fix);
  located.forEach((e, i) => {
    const isLatest = (i === located.length - 1);
    const marker = L.circleMarker([e.location.lat, e.location.lng], {
      radius: isLatest ? 10 : 6,
      color: isLatest ? '#ff3b30' : '#333',
      fillColor: isLatest ? '#ff3b30' : '#666',
      fillOpacity: 0.85,
      weight: 2,
      className: isLatest ? 'pulse' : '',
    }).addTo(map);
    marker.bindPopup(
      '<b>' + e.id + '</b><br>' + e.timestamp +
      '<br>' + (e.environment.temperature_c ?? '—') + '°C  ' +
      (e.environment.humidity_pct ?? '—') + '% RH'
    );
    markers.push(marker);
  });

  if (located.length > 0) {
    const last = located[located.length - 1].location;
    map.setView([last.lat, last.lng], located.length === 1 ? 13 : map.getZoom());
    if (located.length > 1) {
      const bounds = L.latLngBounds(located.map(e => [e.location.lat, e.location.lng]));
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
    }
  }

  // Render entry list
  const root = document.getElementById('entries');
  if (!data.length) {
    root.innerHTML = '<p class="empty">no entries yet — plug the adapter in</p>';
    return;
  }
  root.innerHTML = data.slice().reverse().map((e, idx) => {
    const isLatest = (idx === 0);
    const loc = e.location && e.location.fix
      ? `<a href="https://www.google.com/maps?q=${e.location.lat},${e.location.lng}" target="_blank">
           ${e.location.lat.toFixed(4)}, ${e.location.lng.toFixed(4)}
         </a>`
      : '<span style="opacity:0.4">no fix</span>';
    return `
      <div class="entry ${isLatest ? 'latest' : ''}">
        <div class="id">${e.id}${isLatest ? ' • latest' : ''}</div>
        <div class="ts">${e.timestamp}</div>
        <div class="row">
          <span>${e.environment.temperature_c ?? '—'}°C</span>
          <span>${e.environment.humidity_pct ?? '—'}% RH</span>
          <span>${loc}</span>
        </div>
      </div>`;
  }).join('');
}
load();
setInterval(load, 5000);
</script>
</body>
</html>
"""


def _respond(conn, status, content_type, body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    headers = (
        "HTTP/1.1 {status}\r\n"
        "Content-Type: {ct}\r\n"
        "Content-Length: {ln}\r\n"
        "Connection: close\r\n\r\n"
    ).format(status=status, ct=content_type, ln=len(body))
    conn.send(headers.encode("utf-8"))
    conn.send(body)


def _parse_query(path):
    if "?" not in path:
        return path, {}
    base, qs = path.split("?", 1)
    params = {}
    for pair in qs.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v
    return base, params


def _route(conn, path):
    base, params = _parse_query(path)
    if base == "/" or base.startswith("/index"):
        _respond(conn, "200 OK", "text/html; charset=utf-8", INDEX_HTML)
    elif base == "/entries.json":
        _respond(conn, "200 OK", "application/json", json.dumps(logger.all_entries()))
    elif base == "/sync-time":
        iso = params.get("t", "")
        ok = logger.set_time_from_iso(iso)
        if ok:
            logger.restamp_recent_if_unset()
            _respond(conn, "200 OK", "text/plain", "ok")
        else:
            _respond(conn, "400 Bad Request", "text/plain", "bad time")
    else:
        _respond(conn, "404 Not Found", "text/plain", "not found")


def serve(host="0.0.0.0", port=80):
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(2)
    print("web server listening on", addr)
    while True:
        try:
            conn, _client = s.accept()
            request = conn.recv(1024)
            line = request.split(b"\r\n", 1)[0].decode("utf-8", "ignore")
            parts = line.split(" ")
            path = parts[1] if len(parts) > 1 else "/"
            _route(conn, path)
            conn.close()
        except OSError as e:
            print("conn error:", e)
            try:
                conn.close()
            except Exception:
                pass
