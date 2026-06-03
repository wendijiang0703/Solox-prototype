"""Sensor wrappers for DHT22/RHT03 and Adafruit Ultimate GPS."""

import time
import dht
import machine
from machine import Pin, UART

import micropyGPS

DHT_PIN = 38      # WROOM-1 dev board: header label "D3" → GPIO38
                  # (the board's D# labels are Arduino-style, not GPIO numbers)
GPS_UART_ID = 1
GPS_TX_PIN = 43   # WROOM-1 "TX" / XIAO D6 → GPIO43 (ESP TX → GPS RX)
GPS_RX_PIN = 44   # WROOM-1 "RX" / XIAO D7 → GPIO44 (ESP RX ← GPS TX)
GPS_BAUD = 9600


class Environment:
    def __init__(self, pin=DHT_PIN):
        self._sensor = dht.DHT22(Pin(pin))
        self._last_temp = None
        self._last_hum = None

    def read(self):
        self._sensor.measure()
        self._last_temp = self._sensor.temperature()
        self._last_hum = self._sensor.humidity()
        return self._last_temp, self._last_hum

    @property
    def last(self):
        return {"temperature_c": self._last_temp, "humidity_pct": self._last_hum}


class GPS:
    def __init__(self, uart_id=GPS_UART_ID, tx=GPS_TX_PIN, rx=GPS_RX_PIN, baud=GPS_BAUD):
        self._uart = UART(uart_id, baudrate=baud, tx=tx, rx=rx, timeout=200)
        self._parser = micropyGPS.MicropyGPS(location_formatting="dd")
        self._last_fix = None

    def pump(self, duration_ms=1000):
        """Drain UART for `duration_ms`, feeding bytes to the NMEA parser."""
        deadline = time.ticks_add(time.ticks_ms(), duration_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if self._uart.any():
                for byte in self._uart.read(self._uart.any()):
                    self._parser.update(chr(byte))
            else:
                time.sleep_ms(10)

        self._try_sync_rtc_from_gps()

        if self._parser.fix_type > 1 and self._parser.latitude[0] != 0:
            self._last_fix = {
                "lat": self._parser.latitude[0] if self._parser.latitude[1] == "N" else -self._parser.latitude[0],
                "lng": self._parser.longitude[0] if self._parser.longitude[1] == "E" else -self._parser.longitude[0],
                "fix": True,
                "satellites": self._parser.satellites_in_use,
            }
        return self._last_fix

    def _try_sync_rtc_from_gps(self):
        """If GPS has valid UTC date+time and our RTC isn't set yet, sync it.

        Strict bounds (2025-2040). Without these, a corrupt NMEA sentence
        from a freshly-batteried GPS chip can poison the RTC with values
        like 2080-01-06 (GPS epoch + rollover artefact).
        """
        rtc = machine.RTC()
        if rtc.datetime()[0] >= 2025:
            return  # already set (by GPS earlier, or by the phone)
        try:
            day, month, year_2digit = self._parser.date
            hours, minutes, seconds = self._parser.timestamp
        except (ValueError, TypeError):
            return
        if year_2digit == 0:
            return  # no GPS time yet
        year = 2000 + year_2digit
        if not (2025 <= year <= 2040):
            return
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return
        if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= int(seconds) <= 60):
            return
        rtc.datetime((year, month, day, 0,
                      int(hours), int(minutes), int(seconds), 0))
        print("RTC synced from GPS:", year, month, day, hours, minutes, seconds)

    @property
    def last(self):
        return self._last_fix or {"lat": None, "lng": None, "fix": False, "satellites": 0}
