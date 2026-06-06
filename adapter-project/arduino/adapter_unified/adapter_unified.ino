/*
 * Adapter Unified — Phase 2: archive + auto-entry on plug-in
 *
 * Hardware: DFRobot FireBeetle 2 ESP32-S3 with Camera (DFR1075)
 *           OV3660 camera + DHT22 (GPIO38) + Adafruit Ultimate GPS (UART1)
 *
 * What this phase adds on top of Phase 1:
 *   - Custom 12.9 MB LittleFS partition for photos + entries log
 *   - Boot-time auto-capture: plug in → photo + sensor reading → new entry
 *   - JSON archive at /littlefs/entries.json (ring buffer, 30-entry cap)
 *   - Photos at /littlefs/photos/entry_NNN.jpg
 *   - HTTP endpoints:
 *       GET  /                  → plain dashboard (Phase 3 will redesign)
 *       GET  /log               → entries.json raw
 *       GET  /photos/<file>     → serve a stored JPEG
 *       POST /capture           → take fresh photo + create new entry
 *       POST /sync-time         → phone pushes ISO time, board sets RTC
 *
 * Required libraries (Tools → Manage Libraries):
 *   - "DHT sensor library" by Adafruit
 *   - "Adafruit Unified Sensor" by Adafruit
 *   - "TinyGPSPlus" by Mikal Hart
 *   - "ArduinoJson" by Benoit Blanchon  (v7.x)
 *
 * IDE settings (one-time, MUST change):
 *   - Tools → Partition Scheme → "Custom"   (uses partitions.csv in this folder)
 *   - Tools → PSRAM → "OPI PSRAM"
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <time.h>
#include <sys/time.h>

// --- Camera pin map (unchanged) ---
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    45
#define SIOD_GPIO_NUM     1
#define SIOC_GPIO_NUM     2
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

// --- Sensor pins ---
#define DHT_PIN          38   // "D3"
#define DHT_TYPE         DHT22
#define GPS_RX_PIN       44
#define GPS_TX_PIN       43
#define GPS_BAUD         9600

// --- Wi-Fi AP ---
const char* AP_SSID = "ADAPTER-ARCHIVE";
const char* AP_PASS = "archive2026";

// --- Archive policy ---
const int   MAX_ENTRIES        = 30;
const char* ENTRIES_PATH       = "/entries.json";
const char* PHOTOS_DIR         = "/photos";
const int   GPS_WARMUP_MS      = 5000;
const int   DHT_WARMUP_MS      = 2500;

// --- Subsystem objects ---
DHT            dht(DHT_PIN, DHT_TYPE);
TinyGPSPlus    gps;
HardwareSerial GPSSerial(1);
WebServer      server(80);
Preferences    prefs;

// --- Loop pacing ---
unsigned long lastSensorPrintMs = 0;
const unsigned long SENSOR_PRINT_INTERVAL_MS = 5000;

// Forward declarations
void initCamera();
void initDHT();
void initGPS();
void initAP();
bool initFilesystem();
void pumpGPS(unsigned long durationMs);
String currentIsoTimestamp();
bool rtcIsSet();
JsonDocument loadEntries();
bool saveEntries(JsonDocument& doc);
uint32_t nextEntryId();
String photoFilenameFor(uint32_t id);
bool captureJpegToFile(const String& path, size_t* outBytes);
bool createEntryNow(bool autoCapture);
bool captureAndSavePhoto(uint32_t id, String& outPhotoName);
bool writeEntryRecord(uint32_t id, const String& photoName, bool autoCapture);
void trimToCap(JsonDocument& doc);
void restampUnsetEntries();

// ============================================================
// Setup
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== Adapter Unified Phase 2 boot ===");

  if (!initFilesystem()) {
    Serial.println("FATAL: LittleFS failed to mount. Did you select Custom partition scheme?");
  }

  prefs.begin("adapter", false);

  initCamera();
  initDHT();
  initGPS();
  initAP();

  // Routes
  server.on("/",          HTTP_GET,  []() {
    // Simple dashboard placeholder. Phase 3 will replace this with the
    // travel-journal redesign.
    String html = R"HTML(<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Adapter Archive</title>
<style>
  body{font-family:-apple-system,system-ui,sans-serif;background:#fafafa;color:#1a1a1a;
       margin:0;padding:1.5rem;max-width:520px;}
  h1{font-weight:500;letter-spacing:.12em;text-transform:uppercase;font-size:.85rem;color:#555;}
  button{background:#1a1a1a;color:#fff;border:none;border-radius:6px;
         padding:.8rem 1.4rem;font-size:.95rem;cursor:pointer;}
  .entry{background:#fff;border:1px solid #e5e5e5;border-radius:6px;
         padding:.9rem;margin:.9rem 0;}
  .entry img{width:100%;max-width:300px;border-radius:4px;display:block;margin-top:.5rem;}
  .meta{font-family:ui-monospace,monospace;font-size:.75rem;color:#666;}
  .row{display:flex;gap:.6rem;align-items:center;margin:.2rem 0;}
</style></head><body>
<h1>Adapter Archive — Phase 2</h1>
<button onclick="cap()">+ New entry (photo)</button>
<div id="status" class="meta" style="margin-top:.4rem;"></div>
<div id="list"></div>
<script>
async function syncTime(){
  try{
    await fetch('/sync-time',{method:'POST',headers:{'Content-Type':'text/plain'},
      body:new Date().toISOString()});
  }catch(e){}
}
async function load(){
  const r = await fetch('/log'); const data = await r.json();
  const html = data.slice().reverse().map(e=>`
    <div class="entry">
      <div class="row"><b>#${e.id}</b><span class="meta">${e.ts||'(no time)'}</span></div>
      <div class="row meta">${e.temperature_c!=null?e.temperature_c.toFixed(1)+'°C':'—'} &nbsp;
        ${e.humidity_pct!=null?e.humidity_pct.toFixed(0)+'% RH':'—'}</div>
      <div class="row meta">${e.fix?`${e.lat.toFixed(5)}, ${e.lng.toFixed(5)} (${e.satellites} sats)`:'no GPS fix'}</div>
      ${e.photo?`<img src="/photos/${e.photo}" alt="">`:''}
    </div>`).join('');
  document.getElementById('list').innerHTML = html || '<p class="meta">No entries yet.</p>';
}
async function cap(){
  document.getElementById('status').textContent = 'capturing…';
  const r = await fetch('/capture',{method:'POST'});
  document.getElementById('status').textContent = r.ok?'captured':'capture failed';
  await load();
}
syncTime().then(load);
</script></body></html>)HTML";
    server.send(200, "text/html; charset=utf-8", html);
  });

  server.on("/log", HTTP_GET, []() {
    File f = LittleFS.open(ENTRIES_PATH, "r");
    if (!f) { server.send(200, "application/json", "[]"); return; }
    server.streamFile(f, "application/json");
    f.close();
  });

  // /photos/<filename> — manual route (WebServer.h doesn't do path params).
  server.onNotFound([]() {
    String uri = server.uri();
    if (uri.startsWith("/photos/")) {
      String path = String(PHOTOS_DIR) + "/" + uri.substring(8);
      File f = LittleFS.open(path, "r");
      if (!f) { server.send(404, "text/plain", "not found"); return; }
      server.streamFile(f, "image/jpeg");
      f.close();
      return;
    }
    server.send(404, "text/plain", "not found");
  });

  server.on("/capture", HTTP_POST, []() {
    bool ok = createEntryNow(false);
    server.send(ok ? 200 : 500, "text/plain", ok ? "ok" : "capture failed");
  });

  server.on("/sync-time", HTTP_POST, []() {
    String iso = server.arg("plain");
    // Expect "2026-06-06T22:30:00Z" or "...+01:00"
    int Y, M, D, h, m, s;
    if (sscanf(iso.c_str(), "%d-%d-%dT%d:%d:%d",
               &Y, &M, &D, &h, &m, &s) == 6) {
      struct tm t = {};
      t.tm_year = Y - 1900;
      t.tm_mon  = M - 1;
      t.tm_mday = D;
      t.tm_hour = h;
      t.tm_min  = m;
      t.tm_sec  = s;
      time_t epoch = mktime(&t);
      struct timeval tv = { .tv_sec = epoch, .tv_usec = 0 };
      settimeofday(&tv, nullptr);
      Serial.printf("RTC synced from phone: %s\n", iso.c_str());
      restampUnsetEntries();
      server.send(200, "text/plain", "ok");
    } else {
      server.send(400, "text/plain", "bad iso");
    }
  });

  server.begin();
  Serial.println("HTTP server started");

  // --- Boot-time auto-entry: PHOTO FIRST, then sensors ---
  // The photo is the hero moment of plugging in, so we capture+save it
  // immediately (~1s). Then we use the 5s sensor warm-up window to pump
  // GPS bytes + let DHT settle, and finally write the entry record
  // pointing at the photo we already saved.
  uint32_t bootId = nextEntryId();
  String bootPhoto;
  bool photoOk = captureAndSavePhoto(bootId, bootPhoto);

  Serial.printf("warming sensors (%d ms)…\n", max(GPS_WARMUP_MS, DHT_WARMUP_MS));
  unsigned long warmStart = millis();
  while (millis() - warmStart < (unsigned long)max(GPS_WARMUP_MS, DHT_WARMUP_MS)) {
    while (GPSSerial.available() > 0) gps.encode(GPSSerial.read());
    delay(20);
  }

  if (photoOk) {
    writeEntryRecord(bootId, bootPhoto, true);
  } else {
    Serial.println("boot entry skipped: photo capture failed");
  }

  Serial.println("=== boot complete; serving ===\n");
}

// ============================================================
// Loop
// ============================================================
void loop() {
  while (GPSSerial.available() > 0) gps.encode(GPSSerial.read());
  server.handleClient();

  unsigned long now = millis();
  if (now - lastSensorPrintMs >= SENSOR_PRINT_INTERVAL_MS) {
    lastSensorPrintMs = now;
    float tC = dht.readTemperature();
    float rh = dht.readHumidity();
    if (!isnan(tC) && !isnan(rh)) {
      Serial.printf("DHT: %.1f C  %.1f %%RH | ", tC, rh);
    } else {
      Serial.printf("DHT: NaN | ");
    }
    if (gps.location.isValid()) {
      Serial.printf("GPS: %.5f,%.5f sats=%u\n", gps.location.lat(), gps.location.lng(),
                    gps.satellites.value());
    } else {
      Serial.printf("GPS: no fix (chars=%lu)\n", gps.charsProcessed());
    }
  }
}

// ============================================================
// Init helpers
// ============================================================
void initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer   = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM; c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size   = FRAMESIZE_SVGA;
  c.jpeg_quality = 10;
  c.fb_count     = 2;
  c.grab_mode    = CAMERA_GRAB_LATEST;
  c.fb_location  = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("camera init FAILED: 0x%x\n", err);
    return;
  }
  Serial.println("camera init OK");
  sensor_t* s = esp_camera_sensor_get();
  if (s) { s->set_brightness(s, 1); s->set_saturation(s, 0); }
}

void initDHT() { dht.begin(); Serial.println("DHT init OK"); }

void initGPS() {
  GPSSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.printf("GPS UART1 init OK (RX=%d TX=%d)\n", GPS_RX_PIN, GPS_TX_PIN);
}

void initAP() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  IPAddress ip = WiFi.softAPIP();
  Serial.printf("AP \"%s\" at http://%s\n", AP_SSID, ip.toString().c_str());
}

bool initFilesystem() {
  // `true` = format on failure (first boot after flashing new partition).
  if (!LittleFS.begin(true)) {
    return false;
  }
  if (!LittleFS.exists(PHOTOS_DIR)) {
    LittleFS.mkdir(PHOTOS_DIR);
  }
  if (!LittleFS.exists(ENTRIES_PATH)) {
    File f = LittleFS.open(ENTRIES_PATH, "w");
    if (f) { f.print("[]"); f.close(); }
  }
  size_t total = LittleFS.totalBytes();
  size_t used  = LittleFS.usedBytes();
  Serial.printf("LittleFS OK: %u / %u bytes used\n", (unsigned)used, (unsigned)total);
  return true;
}

// ============================================================
// Time / RTC
// ============================================================
bool rtcIsSet() {
  time_t now = time(nullptr);
  // Anything before 2024-01-01 means RTC never got set.
  return now > 1704067200;
}

String currentIsoTimestamp() {
  if (!rtcIsSet()) return String("");
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);
  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

void restampUnsetEntries() {
  // Walk entries.json — any entry with empty/missing ts gets stamped with
  // current RTC. Conservative: we don't try to back-date based on entry index.
  JsonDocument doc = loadEntries();
  if (!doc.is<JsonArray>()) return;
  String now = currentIsoTimestamp();
  if (now.length() == 0) return;
  bool changed = false;
  for (JsonObject e : doc.as<JsonArray>()) {
    const char* ts = e["ts"] | "";
    if (!ts || strlen(ts) == 0) {
      e["ts"] = now;
      changed = true;
    }
  }
  if (changed) {
    saveEntries(doc);
    Serial.println("restamped previously unset entries");
  }
}

// ============================================================
// Archive
// ============================================================
uint32_t nextEntryId() {
  uint32_t id = prefs.getUInt("nextId", 1);
  prefs.putUInt("nextId", id + 1);
  return id;
}

String photoFilenameFor(uint32_t id) {
  char buf[20];
  snprintf(buf, sizeof(buf), "entry_%03lu.jpg", (unsigned long)id);
  return String(buf);
}

JsonDocument loadEntries() {
  JsonDocument doc;
  File f = LittleFS.open(ENTRIES_PATH, "r");
  if (!f) { doc.to<JsonArray>(); return doc; }
  DeserializationError err = deserializeJson(doc, f);
  f.close();
  if (err || !doc.is<JsonArray>()) {
    doc.clear();
    doc.to<JsonArray>();
  }
  return doc;
}

bool saveEntries(JsonDocument& doc) {
  File f = LittleFS.open(ENTRIES_PATH, "w");
  if (!f) return false;
  serializeJson(doc, f);
  f.close();
  return true;
}

void trimToCap(JsonDocument& doc) {
  JsonArray arr = doc.as<JsonArray>();
  while ((int)arr.size() > MAX_ENTRIES) {
    JsonObject oldest = arr[0];
    const char* photo = oldest["photo"] | "";
    if (photo && strlen(photo) > 0) {
      String p = String(PHOTOS_DIR) + "/" + photo;
      LittleFS.remove(p);
      Serial.printf("trimmed photo: %s\n", p.c_str());
    }
    arr.remove(0);
  }
}

bool captureJpegToFile(const String& path, size_t* outBytes) {
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) { Serial.println("camera_fb_get failed"); return false; }
  File f = LittleFS.open(path, "w");
  if (!f) {
    Serial.printf("can't open %s for write\n", path.c_str());
    esp_camera_fb_return(fb);
    return false;
  }
  size_t written = f.write(fb->buf, fb->len);
  f.close();
  if (outBytes) *outBytes = written;
  esp_camera_fb_return(fb);
  return written == fb->len;
}

bool captureAndSavePhoto(uint32_t id, String& outPhotoName) {
  outPhotoName = photoFilenameFor(id);
  String path = String(PHOTOS_DIR) + "/" + outPhotoName;
  size_t bytes = 0;
  bool ok = captureJpegToFile(path, &bytes);
  if (!ok) {
    Serial.printf("entry %lu: photo failed\n", (unsigned long)id);
    return false;
  }
  Serial.printf("entry %lu: photo %s (%u bytes) saved\n",
                (unsigned long)id, outPhotoName.c_str(), (unsigned)bytes);
  return true;
}

bool writeEntryRecord(uint32_t id, const String& photoName, bool autoCapture) {
  float tC = dht.readTemperature();
  float rh = dht.readHumidity();
  bool   fix = gps.location.isValid();
  double lat = fix ? gps.location.lat() : 0.0;
  double lng = fix ? gps.location.lng() : 0.0;
  uint32_t sats = gps.satellites.value();

  JsonDocument doc = loadEntries();
  JsonArray arr = doc.as<JsonArray>();
  JsonObject e = arr.add<JsonObject>();
  e["id"] = id;
  e["ts"] = currentIsoTimestamp();
  if (!isnan(tC)) e["temperature_c"] = tC; else e["temperature_c"] = nullptr;
  if (!isnan(rh)) e["humidity_pct"]  = rh; else e["humidity_pct"]  = nullptr;
  e["fix"] = fix;
  if (fix) { e["lat"] = lat; e["lng"] = lng; }
  else     { e["lat"] = nullptr; e["lng"] = nullptr; }
  e["satellites"] = sats;
  e["photo"]      = photoName;
  e["auto"]       = autoCapture;

  trimToCap(doc);
  saveEntries(doc);
  Serial.printf("entry %lu record written (auto=%s)\n",
                (unsigned long)id, autoCapture ? "yes" : "no");
  return true;
}

bool createEntryNow(bool autoCapture) {
  // Manual capture path (button on dashboard). Photo + record back-to-back —
  // we don't warm sensors here because by the time the user taps the button
  // the DHT/GPS have already been running for many seconds.
  uint32_t id = nextEntryId();
  String photoName;
  if (!captureAndSavePhoto(id, photoName)) return false;
  return writeEntryRecord(id, photoName, autoCapture);
}
