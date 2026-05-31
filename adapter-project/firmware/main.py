"""Adapter firmware entrypoint.

Boot sequence:
  1. Start Wi-Fi AP "ADAPTER-ARCHIVE" pinned to 192.168.4.1.
  2. Try to read DHT + GPS. Open a new log entry.
  3. Start the web server (blocking).
"""

import time

import network
from machine import Pin

import sensors
import logger
import webserver

AP_SSID = "ADAPTER-ARCHIVE"
AP_PASSWORD = "archive2026"   # WPA2 requires 8+ chars; set to "" for open if preferred
STATUS_LED_PIN = 2            # XIAO D1

# Demo override: when set, every plug-in creates an entry at these coordinates
# regardless of GPS state. Set to None to use real GPS readings.
FORCE_LOCATION = {
    "lat": 51.4994,
    "lng": -0.1741,
    "fix": True,
    "satellites": 12,
}


def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    if AP_PASSWORD:
        ap.config(essid=AP_SSID, password=AP_PASSWORD, authmode=network.AUTH_WPA_WPA2_PSK)
    else:
        ap.config(essid=AP_SSID, authmode=network.AUTH_OPEN)
    ap.ifconfig(("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1"))
    while not ap.active():
        time.sleep_ms(100)
    print("AP up:", ap.ifconfig())
    return ap


def blink(led, n=2):
    for _ in range(n):
        led.value(1)
        time.sleep_ms(120)
        led.value(0)
        time.sleep_ms(120)


def collect_initial_reading():
    env = sensors.Environment()
    gps = sensors.GPS()

    try:
        env.read()
    except OSError as e:
        print("DHT read failed:", e)

    # Give the GPS up to ~5s to spit out a sentence (indoors it likely won't get a fix).
    gps.pump(duration_ms=5000)

    return env.last, gps.last


def main():
    led = Pin(STATUS_LED_PIN, Pin.OUT)
    blink(led, 1)

    start_ap()
    blink(led, 2)

    env_reading, gps_reading = collect_initial_reading()
    if FORCE_LOCATION is not None:
        gps_reading = dict(FORCE_LOCATION)
        print("FORCE_LOCATION override applied")
    if gps_reading.get("fix"):
        entry = logger.open_entry(env_reading, gps_reading)
        print("opened entry:", entry["id"], env_reading, gps_reading)
    else:
        print("no GPS fix at boot - not opening entry; reading:", env_reading)
    blink(led, 3)

    led.value(1)  # solid on while serving
    webserver.serve()


if __name__ == "__main__":
    main()
