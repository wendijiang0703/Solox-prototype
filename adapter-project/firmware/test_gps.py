"""REPL test: confirm the Adafruit GPS is wired and producing NMEA sentences.

Phase 1 prints raw bytes for 10 s — you should see lines starting with $GP/$GN.
Phase 2 feeds the bytes into the parser and prints latitude/longitude/fix every
second for 30 s. Indoors the fix will almost certainly be False; near a window
or outside you should see lat/lng resolve within ~30-90 s of cold start.
"""

import time
from machine import UART

import micropyGPS

UART_ID = 1
TX_PIN = 43  # XIAO D6
RX_PIN = 44  # XIAO D7
BAUD = 9600

uart = UART(UART_ID, baudrate=BAUD, tx=TX_PIN, rx=RX_PIN, timeout=200)

print("--- phase 1: raw bytes for 10s ---")
deadline = time.ticks_add(time.ticks_ms(), 10_000)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    if uart.any():
        chunk = uart.read(uart.any())
        try:
            print(chunk.decode("ascii", "ignore"), end="")
        except Exception:
            pass
    time.sleep_ms(20)

print("\n--- phase 2: parsed fix for 30s ---")
parser = micropyGPS.MicropyGPS(location_formatting="dd")
deadline = time.ticks_add(time.ticks_ms(), 30_000)
next_print = time.ticks_ms()

while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    if uart.any():
        for byte in uart.read(uart.any()):
            parser.update(chr(byte))
    if time.ticks_diff(time.ticks_ms(), next_print) >= 0:
        print(
            "fix_type={} sats={} lat={} lng={}".format(
                parser.fix_type,
                parser.satellites_in_use,
                parser.latitude,
                parser.longitude,
            )
        )
        next_print = time.ticks_add(time.ticks_ms(), 1000)
    time.sleep_ms(10)
