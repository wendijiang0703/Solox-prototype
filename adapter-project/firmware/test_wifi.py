"""REPL test: bring up the AP and serve a one-line page.

Run, then on your phone join "ADAPTER-ARCHIVE-TEST" (password archive2026)
and visit http://192.168.4.1 in a browser. Page should say "hello from XIAO".
"""

import time
import network
import socket

SSID = "ADAPTER-ARCHIVE-TEST"
PASSWORD = "archive2026"

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=SSID, password=PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
ap.ifconfig(("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1"))
while not ap.active():
    time.sleep_ms(100)
print("AP up:", ap.ifconfig())

addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(2)
print("listening on", addr)

body = b"<!doctype html><meta charset=utf-8><h1>hello from XIAO</h1>"
resp = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
    b"Connection: close\r\n\r\n" + body
)

while True:
    conn, client = s.accept()
    print("client:", client)
    conn.recv(1024)
    conn.send(resp)
    conn.close()
