"""Capture one image from the OV3660 on the FireBeetle 2 ESP32-S3 with Camera.

This firmware build (cnadler86 mpy_cam v1.27.0 DFRobot_ESP32S3) does not
expose working JPEG mode for this OV3660. We capture RGB565, convert to a
24-bit BMP on the board, and save to /photo.bmp. macOS Preview opens BMP
natively, so the retrieval flow is:

    mpremote connect /dev/tty.usbmodem1101 cp :photo.bmp ./photo.bmp
    open ./photo.bmp
"""

import time
import struct
from camera import Camera, FrameSize, PixelFormat

# DFRobot FireBeetle 2 ESP32-S3 with Camera (DFR1075) camera pin map.
# Verified empirically — SCCB I2C scan finds the OV3660 at 0x3C with these.
PINS = dict(
    data_pins=[39, 40, 41, 4, 7, 8, 46, 48],
    vsync_pin=6, href_pin=42,
    sda_pin=1, scl_pin=2,
    pclk_pin=5, xclk_pin=45, xclk_freq=20000000,
    powerdown_pin=-1, reset_pin=-1,
)

# QVGA (320x240) gives a ~230 KB BMP and converts in a few seconds.
# Bump to FrameSize.VGA for 640x480 (~922 KB, ~30 s conversion).
FRAME = FrameSize.QVGA


def rgb565_buf_to_bmp_bytes(buf, width, height):
    """Convert an RGB565 framebuffer to a 24-bit Windows BMP byte array."""
    row_bytes = width * 3
    pad = (4 - row_bytes % 4) % 4
    padded_row = row_bytes + pad
    image_size = padded_row * height
    file_size = 54 + image_size

    bmp = bytearray(file_size)
    # BMP file header (14 bytes): "BM", filesize, reserved x2, data offset
    struct.pack_into('<2sIHHI', bmp, 0,
                     b'BM', file_size, 0, 0, 54)
    # BITMAPINFOHEADER (40 bytes)
    struct.pack_into('<IiiHHIIiiII', bmp, 14,
                     40, width, height, 1, 24, 0,
                     image_size, 2835, 2835, 0, 0)

    # Rows are bottom-up in BMP convention; BGR byte order.
    for y in range(height):
        src = y * width * 2
        dst = 54 + (height - 1 - y) * padded_row
        for x in range(width):
            i = src + x * 2
            hi = buf[i]
            lo = buf[i + 1]
            pixel = (hi << 8) | lo
            r = ((pixel >> 11) & 0x1F) << 3
            g = ((pixel >> 5) & 0x3F) << 2
            b = (pixel & 0x1F) << 3
            # Replicate top bits into the low bits so 0xF8 becomes 0xFF, etc.
            r |= r >> 5
            g |= g >> 6
            b |= b >> 5
            j = dst + x * 3
            bmp[j] = b
            bmp[j + 1] = g
            bmp[j + 2] = r
    return bmp


def main():
    print("creating camera...")
    cam = Camera(
        pixel_format=PixelFormat.RGB565,
        frame_size=FRAME,
        fb_count=1,
        **PINS,
    )
    cam.init()
    w = cam.get_pixel_width()
    h = cam.get_pixel_height()
    print("sensor:", cam.get_sensor_name(), "  capture size:", w, "x", h)

    # Explicitly enable auto-exposure, auto-gain, auto-white-balance.
    # Defaults in this firmware build leave AE/AGC off, so frames come back near-black.
    cam.set_exposure_ctrl(1)
    cam.set_gain_ctrl(1)
    cam.set_whitebal(1)
    cam.set_awb_gain(1)
    cam.set_aec2(1)
    try:
        cam.set_ae_level(2)        # +2 EV brighter
    except Exception:
        pass
    try:
        from camera import GainCeiling
        cam.set_gainceiling(GainCeiling.X64)   # max sensitivity
    except Exception:
        pass
    print("AE / AGC / AWB enabled")

    # Discard more frames so auto-exposure / white-balance settle.
    print("warming up (10 frames)...")
    for _ in range(10):
        cam.capture()
        time.sleep_ms(120)

    print("capturing...")
    rgb565 = cam.capture()
    print("captured", len(rgb565), "bytes of RGB565")
    cam.deinit()

    print("converting RGB565 -> 24-bit BMP (this takes a few seconds)...")
    t0 = time.ticks_ms()
    bmp = rgb565_buf_to_bmp_bytes(rgb565, w, h)
    print("conversion took", time.ticks_diff(time.ticks_ms(), t0), "ms")

    with open('/photo.bmp', 'wb') as f:
        f.write(bmp)
    print("saved /photo.bmp (", len(bmp), "bytes)")
    print("retrieve with:")
    print("  mpremote connect /dev/tty.usbmodem1101 cp :photo.bmp ./photo.bmp && open ./photo.bmp")


main()
