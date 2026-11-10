#pragma once
#include <ArduinoJson.h>
#include <cstdint>
#include <cstring>

namespace m5dash {
namespace maintenance {
constexpr size_t MAX_CONFIG_JSON = 300;
constexpr uint32_t WINDOW_MS = 10 * 60 * 1000;

// Same parser validates USB input and the single versioned NVS record.
struct Config {
  char ssid[33]{};
  char wifiPassword[65]{};
  char otaPassword[65]{};
  char host[32]{};
};

inline bool hostnameValid(const char* s) {
  size_t n = std::strlen(s);
  if (!n || n > 31 || s[0] == '-' || s[n - 1] == '-') return false;
  for (size_t i = 0; i < n; ++i) {
    char c = s[i];
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-')) return false;
  }
  return true;
}

inline bool copyField(JsonVariantConst value, char* dst, size_t capacity, size_t minimum) {
  if (!value.is<const char*>()) return false;
  JsonString s = value.as<JsonString>();
  size_t n = s.size();
  if (n < minimum || n >= capacity || std::strlen(s.c_str()) != n) return false;
  for (size_t i = 0; i < n; ++i) {
    uint8_t c = uint8_t(s.c_str()[i]);
    if (c < 32 || c == 127) return false;
  }
  std::memcpy(dst, s.c_str(), n + 1);
  return true;
}

inline bool parseConfig(const char* json, Config& out) {
  if (!json || strnlen(json, MAX_CONFIG_JSON + 1) > MAX_CONFIG_JSON) return false;
  JsonDocument d;
  if (deserializeJson(d, json, DeserializationOption::NestingLimit(2))) return false;
  JsonObjectConst object = d.as<JsonObjectConst>();
  if (object.isNull() || object.size() != 4) return false;
  Config next;
  bool ok = copyField(object["ssid"], next.ssid, sizeof next.ssid, 1)
    && copyField(object["wifi_password"], next.wifiPassword, sizeof next.wifiPassword, 0)
    && copyField(object["ota_password"], next.otaPassword, sizeof next.otaPassword, 12)
    && copyField(object["hostname"], next.host, sizeof next.host, 1)
    && hostnameValid(next.host);
  if (ok) out = next;
  std::memset(&next, 0, sizeof next);
  return ok;
}

inline uint32_t remaining(uint32_t started, uint32_t now) {
  uint32_t elapsed = now - started;
  return elapsed >= WINDOW_MS ? 0 : WINDOW_MS - elapsed;
}
} // namespace maintenance
} // namespace m5dash

#ifdef ARDUINO
#include <Arduino.h>
#include <ArduinoOTA.h>
#include <Preferences.h>
#include <WiFi.h>
#include <memory>
#include <new>

namespace m5dash {
// Display-only maintenance. Call command() only from the physical USB parser.
// Pause ESP-NOW channel search while active(), but keep its poll() running.
// Stopping disconnects the AP, not the STA radio needed by ESP-NOW.
class DisplayMaintenance {
 public:
  bool begin() {
    if (active_) return false;
    configured_ = false;
    std::memset(&config_, 0, sizeof config_);
    Preferences p;
    if (!p.begin("m5maint", true)) return false;
    size_t n = p.getStringLength("cfg_v1");
    char json[maintenance::MAX_CONFIG_JSON + 1]{};
    // Preferences reports the stored terminating NUL in its length.
    if (n > 1 && n <= sizeof json && p.getString("cfg_v1", json, sizeof json) == n) {
      configured_ = maintenance::parseConfig(json, config_);
    }
    p.end();
    std::memset(json, 0, sizeof json);
    return configured_; // Loading credentials never starts Wi-Fi or OTA.
  }

  bool command(const char* line, Print& out) {
    if (!line || std::strncmp(line, "ota", 3) || (line[3] && line[3] != ' ')) return false;
    if (!std::strcmp(line, "ota status")) { status(out); return true; }
    if (!std::strcmp(line, "ota on")) {
      bool ok = start();
      out.printf("{\"t\":\"ota_result\",\"action\":\"on\",\"ok\":%s}\n", ok ? "true" : "false");
      status(out); return true;
    }
    if (!std::strcmp(line, "ota off")) {
      bool ok = stop();
      out.printf("{\"t\":\"ota_result\",\"action\":\"off\",\"ok\":%s}\n", ok ? "true" : "false");
      status(out); return true;
    }
    if (!std::strncmp(line, "ota config ", 11)) {
      bool ok = !active_ && save(line + 11);
      out.printf("{\"t\":\"ota_config\",\"stored\":%s}\n", ok ? "true" : "false");
      if (active_) lastError_ = "maintenance_active";
      status(out); return true;
    }
    out.println("{\"t\":\"ota_result\",\"ok\":false,\"error\":\"use USB ota config, on, off, or status\"}");
    return true;
  }

  bool start() {
    if (active_) return true; // Repeated commands cannot extend the ten-minute deadline.
    if (!configured_) { lastError_ = "not_configured"; return false; }
    ota_.reset(new (std::nothrow) ArduinoOTAClass());
    if (!ota_) { lastError_ = "allocation_failed"; return false; }
    active_ = true; updating_ = false; restarting_ = false; serverStarted_ = false;
    progress_ = 0; lastError_ = ""; startedMs_ = millis(); lastUiMs_ = 0;
    WiFi.setAutoReconnect(false);
    if (!WiFi.mode(WIFI_STA)) { lastError_ = "wifi_start_failed"; stop(); return false; }
    WiFi.setSleep(false);
    WiFi.disconnect(false, false);
    WiFi.setHostname(config_.host);
    WiFi.begin(config_.ssid, config_.wifiPassword);
    notify();
    return true;
  }

  bool stop() {
    if (updating_ || restarting_) { lastError_ = "update_in_progress"; return false; }
    if (!active_) return true;
    ota_.reset(); // Destructor closes OTA/mDNS before the access point is disconnected.
    WiFi.setAutoReconnect(false);
    WiFi.disconnect(false, false); // Keep STA/ESP-NOW alive; do not use WIFI_OFF.
    active_ = false; serverStarted_ = false;
    notify();
    return true;
  }

  void poll() {
    if (!active_) return;
    // Never interrupt an authenticated flash write. ArduinoOTA's transfer timeout bounds
    // stalled receives; an error returns here and an expired window then closes.
    if (!updating_ && !restarting_ && remainingMs() == 0) { stop(); return; }
    if (!serverStarted_ && wifiConnected()) {
      ota_->setHostname(config_.host);
      ota_->setPassword(config_.otaPassword); // Always required: parser enforces >=12 bytes.
      ota_->setPort(3232);
      ota_->setTimeout(5000);
      ota_->setRebootOnSuccess(true);
      ota_->onStart([this]() {
        updating_ = true; progress_ = 0; lastError_ = ""; notify();
      });
      ota_->onProgress([this](unsigned done, unsigned total) {
        progress_ = total ? uint8_t((uint64_t(done) * 100) / total) : 0;
        uint32_t now = millis();
        if (now - lastUiMs_ >= 200 || progress_ == 100) { lastUiMs_ = now; notify(); }
      });
      ota_->onEnd([this]() {
        progress_ = 100; updating_ = false; restarting_ = true; notify();
      });
      ota_->onError([this](ota_error_t error) {
        updating_ = false; restarting_ = false;
        switch (error) {
          case OTA_AUTH_ERROR: lastError_ = "authentication_failed"; break;
          case OTA_BEGIN_ERROR: lastError_ = "update_begin_failed"; break;
          case OTA_CONNECT_ERROR: lastError_ = "upload_connect_failed"; break;
          case OTA_RECEIVE_ERROR: lastError_ = "upload_receive_failed"; break;
          default: lastError_ = "update_finalize_failed"; break;
        }
        notify();
      });
      ota_->begin();
      serverStarted_ = true;
      notify();
    }
    if (serverStarted_ && wifiConnected()) ota_->handle();
    if (active_ && !updating_ && !restarting_ && remainingMs() == 0) stop();
  }

  bool configured() const { return configured_; }
  bool active() const { return active_; }
  bool updating() const { return updating_; }
  bool restarting() const { return restarting_; }
  bool wifiConnected() const { return active_ && WiFi.status() == WL_CONNECTED; }
  bool ready() const { return active_ && serverStarted_ && wifiConnected(); }
  uint8_t progress() const { return progress_; }
  const char* hostname() const { return configured_ ? config_.host : ""; }
  const char* lastError() const { return lastError_; }
  uint32_t remainingMs() const { return active_ ? maintenance::remaining(startedMs_, millis()) : 0; }
  // ArduinoOTA::handle blocks during upload; this callback lets the sketch draw progress.
  // Keep it short and display-only: do not call poll(), start(), stop(), or command() here.
  void setUiCallback(void (*callback)()) { uiCallback_ = callback; }

  void status(Print& out) const {
    // SSID, Wi-Fi password and OTA password are deliberately absent.
    out.printf("{\"t\":\"ota_status\",\"configured\":%s,\"active\":%s,\"wifi\":%s,\"ready\":%s,\"updating\":%s,\"restarting\":%s,\"progress\":%u,\"remaining_ms\":%lu,\"hostname\":\"%s\",\"error\":\"%s\"}\n",
      configured_ ? "true" : "false", active_ ? "true" : "false", wifiConnected() ? "true" : "false",
      ready() ? "true" : "false", updating_ ? "true" : "false", restarting_ ? "true" : "false",
      progress_, (unsigned long)remainingMs(), hostname(), lastError_);
  }

 private:
  maintenance::Config config_{};
  std::unique_ptr<ArduinoOTAClass> ota_;
  bool configured_ = false, active_ = false, updating_ = false, restarting_ = false, serverStarted_ = false;
  uint8_t progress_ = 0;
  uint32_t startedMs_ = 0, lastUiMs_ = 0;
  const char* lastError_ = "";
  void (*uiCallback_)() = nullptr;

  void notify() { if (uiCallback_) uiCallback_(); }

  bool save(const char* json) {
    maintenance::Config next;
    if (!maintenance::parseConfig(json, next)) { lastError_ = "invalid_config"; return false; }
    // One NVS string/key is the commit unit; never save credentials as separate keys.
    Preferences p;
    bool opened = p.begin("m5maint", false);
    bool ok = opened && p.putString("cfg_v1", json) == std::strlen(json);
    if (opened) p.end();
    if (ok) { config_ = next; configured_ = true; lastError_ = ""; }
    else lastError_ = "config_save_failed";
    std::memset(&next, 0, sizeof next);
    return ok;
  }
};
} // namespace m5dash
#endif
