"""Tiny socket-based web server. Serves the dashboard and a JSON archive."""

import json
import socket

import logger

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adapter Archive</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, system-ui, sans-serif; background:#0a0a0a; color:#e8e8e8; margin:0; padding:1.5rem; }
  h1 { font-weight:300; letter-spacing:0.08em; text-transform:uppercase; font-size:1rem; opacity:0.7; }
  .entry { border:1px solid #1f1f1f; padding:1rem; margin:0.75rem 0; border-radius:4px; }
  .id { font-family: ui-monospace, monospace; font-size:0.75rem; opacity:0.5; }
  .ts { font-family: ui-monospace, monospace; font-size:0.9rem; margin:0.25rem 0; }
  .row { display:flex; gap:1.5rem; font-size:0.85rem; opacity:0.85; margin-top:0.5rem; }
  .empty { opacity:0.4; font-style:italic; }
</style>
</head>
<body>
<h1>Adapter Archive</h1>
<div id="entries"></div>
<script>
async function load() {
  const r = await fetch('/entries.json');
  const data = await r.json();
  const root = document.getElementById('entries');
  if (!data.length) { root.innerHTML = '<p class="empty">no entries yet</p>'; return; }
  root.innerHTML = data.slice().reverse().map(e => `
    <div class="entry">
      <div class="id">${e.id}</div>
      <div class="ts">${e.timestamp}</div>
      <div class="row">
        <span>${e.environment.temperature_c ?? '—'}°C</span>
        <span>${e.environment.humidity_pct ?? '—'}% RH</span>
        <span>${e.location.fix ? e.location.lat.toFixed(4)+', '+e.location.lng.toFixed(4) : 'no fix'}</span>
      </div>
    </div>
  `).join('');
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


def _route(conn, path):
    if path == "/" or path.startswith("/index"):
        _respond(conn, "200 OK", "text/html; charset=utf-8", INDEX_HTML)
    elif path.startswith("/entries.json"):
        _respond(conn, "200 OK", "application/json", json.dumps(logger.all_entries()))
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
