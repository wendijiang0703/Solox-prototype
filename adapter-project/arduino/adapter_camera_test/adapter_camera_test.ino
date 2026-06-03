/*
 * Adapter Camera — one-shot photo on demand
 *
 * Brings up the OV3660 on the DFRobot FireBeetle 2 ESP32-S3 with Camera
 * (DFR1075), starts a Wi-Fi access point, and serves a single web page
 * with a button that triggers a fresh JPEG capture.
 *
 * Demo flow:
 *   1. Upload to the FireBeetle via Arduino IDE.
 *   2. Open Serial Monitor (115200 baud) — confirms AP and IP.
 *   3. On phone, join Wi-Fi network "ADAPTER-CAMERA", password "archive2026".
 *   4. Open http://192.168.4.1/ in browser → click "Take photo".
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

// --- FireBeetle 2 ESP32-S3 with Camera (DFR1075) camera pin map ---
// These match what we proved by SCCB I2C scan + library detection on the
// MicroPython side. Don't change them unless you're on different hardware.
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    45
#define SIOD_GPIO_NUM     1   // SDA (SCCB)
#define SIOC_GPIO_NUM     2   // SCL (SCCB)
#define Y9_GPIO_NUM      48
#define Y8_GPIO_NUM      46
#define Y7_GPIO_NUM       8
#define Y6_GPIO_NUM       7
#define Y5_GPIO_NUM       4
#define Y4_GPIO_NUM      41
#define Y3_GPIO_NUM      40
#define Y2_GPIO_NUM      39
#define VSYNC_GPIO_NUM    6
#define HREF_GPIO_NUM    42
#define PCLK_GPIO_NUM     5

// --- Access-point config (matches the dashboard naming convention) ---
const char* AP_SSID = "ADAPTER-CAMERA";
const char* AP_PASS = "archive2026";

WebServer server(80);

// Simple landing page with a button.
const char INDEX_HTML[] PROGMEM = R"HTML(
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adapter Camera</title>
<style>
  body { font-family:-apple-system,system-ui,sans-serif; margin:0; padding:1.5rem;
         background:#fafafa; color:#1a1a1a; }
  h1 { font-weight:500; letter-spacing:0.12em; text-transform:uppercase;
       font-size:0.85rem; color:#555; }
  button { background:#ff3b30; color:#fff; border:none; border-radius:6px;
           padding:0.9rem 1.5rem; font-size:1rem; cursor:pointer; }
  img { max-width:100%; margin-top:1rem; border:1px solid #e5e5e5; border-radius:6px; }
  .meta { font-family:ui-monospace,monospace; font-size:0.75rem;
          color:#999; margin-top:0.25rem; }
</style>
</head>
<body>
<h1>Adapter Camera</h1>
<button onclick="snap()">Take photo</button>
<div class="meta" id="meta"></div>
<img id="photo" alt="">
<script>
function snap() {
  const url = '/capture?ts=' + Date.now();
  document.getElementById('meta').textContent = 'capturing...';
  const img = document.getElementById('photo');
  img.onload = () => { document.getElementById('meta').textContent = 'captured at ' + new Date().toLocaleTimeString(); };
  img.onerror = () => { document.getElementById('meta').textContent = 'capture failed'; };
  img.src = url;
}
</script>
</body>
</html>
)HTML";

void handleRoot() {
  server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void handleCapture() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("camera capture failed");
    server.send(500, "text/plain", "capture failed");
    return;
  }
  Serial.printf("captured %u bytes\n", fb->len);

  server.setContentLength(fb->len);
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.write(fb->buf, fb->len);

  esp_camera_fb_return(fb);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n--- Adapter Camera boot ---");

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_SVGA;     // 800x600
  config.jpeg_quality = 10;                 // 0-63, lower = better
  config.fb_count     = 2;                  // double-buffer in PSRAM
  config.grab_mode    = CAMERA_GRAB_LATEST;
  config.fb_location  = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("camera init FAILED: 0x%x\n", err);
    return;
  }
  Serial.println("camera init OK");

  // Optional: bump up brightness/contrast/saturation defaults.
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 1);
    s->set_saturation(s, 0);
    s->set_vflip(s, 0);
    s->set_hmirror(s, 0);
  }

  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  IPAddress ip = WiFi.softAPIP();
  Serial.print("AP \"");
  Serial.print(AP_SSID);
  Serial.print("\" up at http://");
  Serial.println(ip);

  server.on("/", HTTP_GET, handleRoot);
  server.on("/capture", HTTP_GET, handleCapture);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
}
