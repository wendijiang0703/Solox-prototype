"""REPL test: paste or `mpremote run` this to confirm the RHT03 is wired right.

Expected: ~5 readings, ~2 seconds apart, with plausible room values
(15-30 C, 30-70 %RH). If you see OSError: ETIMEDOUT, the data line or
pull-up resistor is wrong.
"""

import time
import dht
from machine import Pin

DATA_PIN = 3   # XIAO D2 → GPIO3

sensor = dht.DHT22(Pin(DATA_PIN))

for i in range(5):
    try:
        sensor.measure()
        print("{}: temp={:.1f} C  hum={:.1f} %".format(i, sensor.temperature(), sensor.humidity()))
    except OSError as e:
        print("{}: read failed: {}".format(i, e))
    time.sleep(2)
