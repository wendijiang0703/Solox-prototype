"""Sweep GPIOs to find which one the RHT03 DATA wire is actually connected to.

On generic WROOM-1 dev boards, the silkscreen `D#` labels don't always match
the chip's GPIO numbers. This script tries each plausible GPIO; whichever
one returns valid temperature/humidity is the GPIO our sensor is wired to.

Keep the DATA wire connected to the pin you THINK is `D3` (or wherever you
wired it). Don't move anything — let the code do the searching.
"""

import time
import dht
from machine import Pin

# All ESP32-S3 GPIOs that are commonly broken out on dev boards and usable
# as digital I/O. Skips 0 (boot), 19/20 (USB), 22-25 (don't exist on S3),
# 26-32 (SPI flash), 33-37 (SPI flash / PSRAM on -R boards), 45/46 (strapping).
CANDIDATES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
              21, 38, 39, 40, 41, 42, 47, 48]

print("Sweeping {} candidate GPIOs for DHT22 response...\n".format(len(CANDIDATES)))

found = []
for gpio in CANDIDATES:
    try:
        sensor = dht.DHT22(Pin(gpio))
        # Two reads — first sometimes fails even on a good pin
        time.sleep_ms(50)
        try:
            sensor.measure()
        except OSError:
            time.sleep_ms(500)
            sensor.measure()
        t = sensor.temperature()
        h = sensor.humidity()
        if -40 <= t <= 80 and 0 <= h <= 100:
            print("  GPIO{:2d}  RESPONDED   temp={:.1f}C  hum={:.1f}%".format(gpio, t, h))
            found.append(gpio)
        else:
            print("  GPIO{:2d}  garbage     temp={}  hum={}".format(gpio, t, h))
    except OSError:
        print("  GPIO{:2d}  no response".format(gpio))
    except Exception as e:
        print("  GPIO{:2d}  error: {}".format(gpio, e))
    time.sleep_ms(100)

print("\n--- result ---")
if found:
    print("DHT22 is on GPIO(s): {}".format(found))
    print("Update DHT_PIN in sensors.py to: {}".format(found[0]))
else:
    print("No GPIO responded. Likely: wrong wiring, missing pull-up, or dead sensor.")
