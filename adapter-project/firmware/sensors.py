"""Sensor wrappers for DHT22/RHT03 and Adafruit Ultimate GPS."""

import time
import dht
from machine import Pin, UART

import micropyGPS

DHT_PIN = 3       # XIAO D2 → GPIO3
GPS_UART_ID = 1
GPS_TX_PIN = 43   # XIAO D6 → GPIO43 (ESP TX → GPS RX)
GPS_RX_PIN = 44   # XIAO D7 → GPIO44 (ESP RX ← GPS TX)
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

        if self._parser.fix_type > 1 and self._parser.latitude[0] != 0:
            self._last_fix = {
                "lat": self._parser.latitude[0] if self._parser.latitude[1] == "N" else -self._parser.latitude[0],
                "lng": self._parser.longitude[0] if self._parser.longitude[1] == "E" else -self._parser.longitude[0],
                "fix": True,
                "satellites": self._parser.satellites_in_use,
            }
        return self._last_fix

    @property
    def last(self):
        return self._last_fix or {"lat": None, "lng": None, "fix": False, "satellites": 0}
