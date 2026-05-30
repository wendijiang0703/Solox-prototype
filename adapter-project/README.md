# Solo X Adapter — firmware

Companion code for the Legacy Socket Adapter prototype. See `../ADAPTER_PROJECT.md`
for project context, hardware list, wiring, and design narrative.

## Files

- `firmware/boot.py` — runs on every boot, sets up garbage collection
- `firmware/main.py` — entrypoint: brings up Wi-Fi AP, reads sensors, opens a log entry, starts the web server
- `firmware/sensors.py` — DHT22/RHT03 and Adafruit GPS wrappers
- `firmware/logger.py` — JSON log entry creation + persistence to flash
- `firmware/webserver.py` — socket-based HTTP server, serves the dashboard
- `firmware/micropyGPS.py` — NMEA parser (third-party, download separately)
- `firmware/test_dht.py` — REPL test for the RHT03 sensor
- `firmware/test_gps.py` — REPL test for the GPS
- `firmware/test_wifi.py` — REPL test for AP mode + minimal web page
- `web/index.html` — design reference for the dashboard (real one is inlined in `webserver.py`)

## Setup (macOS, mpremote workflow)

### 1. Host tools

```sh
python3 -m pip install --user esptool mpremote
```

### 2. Flash MicroPython

Download the latest ESP32-S3 GENERIC build from
https://micropython.org/download/ESP32_GENERIC_S3/ (file is named like
`ESP32_GENERIC_S3-20250214-v1.24.1.bin`).

Plug the XIAO into your Mac via USB-C, then find its port:

```sh
ls /dev/tty.usbmodem*
```

You'll see something like `/dev/tty.usbmodem101`. Use that path in the
commands below (replace `PORT` with it).

If the XIAO doesn't show up, press and hold the **BOOT** button on the
board, briefly tap **RESET**, then release BOOT. That puts it into
download mode so esptool can talk to it.

Erase and flash:

```sh
esptool.py --chip esp32s3 --port PORT erase_flash
esptool.py --chip esp32s3 --port PORT write_flash -z 0 ~/Downloads/ESP32_GENERIC_S3-20250214-v1.24.1.bin
```

Open the REPL to confirm MicroPython booted:

```sh
mpremote connect PORT repl
```

You should see `>>>`. Press Ctrl-X to exit.

### 3. Install micropyGPS on the board

```sh
mpremote connect PORT mip install github:inmcm/micropyGPS
```

### 4. Upload the firmware

From `adapter-project/`:

```sh
mpremote connect PORT cp firmware/boot.py firmware/main.py firmware/sensors.py firmware/logger.py firmware/webserver.py :
```

### 5. Test each subsystem individually first

```sh
mpremote connect PORT run firmware/test_dht.py
mpremote connect PORT run firmware/test_gps.py
mpremote connect PORT run firmware/test_wifi.py
```

Each should print useful output. Only after all three pass should you reset
and let `main.py` run for the full integrated demo.

### 6. Soft-reset to run main.py

```sh
mpremote connect PORT reset
```

Then on your phone:
- Join Wi-Fi network **ADAPTER-ARCHIVE** (password `archive2026`)
- Open http://192.168.4.1 in any browser

## Troubleshooting

- **No port appears.** Check the USB-C cable is data-capable (not power-only). Try a different cable.
- **esptool can't connect.** Hold BOOT + tap RESET on the XIAO, release BOOT, then run esptool again.
- **DHT read times out.** Confirm the 10K pull-up resistor sits between VCC and DATA. Confirm DATA is on D2 (GPIO3).
- **GPS prints nothing.** Confirm TX/RX are crossed: GPS TX → XIAO D7 (GPIO44), GPS RX → XIAO D6 (GPIO43).
- **No GPS fix indoors.** Expected. Move near a window for the first fix; once acquired, the cold-start cache helps subsequent fixes.
- **Can't see ADAPTER-ARCHIVE network.** iOS sometimes hides networks with no internet — pull down the Wi-Fi list and tap explicitly.
