/* GoKart Core2 item screen ("your items", bar-mounted M5Stack Core2).
 *
 * Listens for the kart Heltec's ESP-NOW inventory broadcasts (kart-0.3.0 `inv` line from the Pi),
 * shows the carried item-box prizes, swipe left/right to pick one, tap to USE it (sent back to the
 * Heltec, which relays {"t":"invuse",...} to the Pi over USB). No WiFi join: it hops channels until
 * it hears a kart, then stays on that channel. The rotation is fixed for the bar cradle (ROT below):
 * no flip gesture, so a resting palm can never turn the screen over mid-ride.
 *
 * Build: firmware/build.sh core2 [upload /dev/cu.usbserial-XXXX]
 */
#include <M5Unified.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

struct __attribute__((packed)) GkInvFrame { char m0, m1; uint8_t ver, kart, seq, n, items[3]; };
struct __attribute__((packed)) GkUseFrame { char m0, m1; uint8_t ver, kart, slot, seq; };

static M5Canvas cv(&M5.Display);
static const uint8_t ROT = 2;                 // fixed for the bar cradle (owner 2026-11-10: "lock it")

// link / inventory (written from the ESP-NOW callback)
static volatile bool frameFresh = false;
static uint8_t rxItems[3], rxN = 0, rxSeq = 0, rxKart = 0;
static uint8_t heltecMac[6]; static bool heltecKnown = false;
static uint32_t lastRxMs = 0;

// UI state
static uint8_t items[3], n = 0, invSeq = 0xFF, kart = 0;
static int sel = 0;
static uint32_t scanHopMs = 0; static uint8_t scanCh = 1; static bool locked = false;
static uint32_t useSentMs = 0; static uint8_t useSeq = 0, useTries = 0, useSlot = 0;
static uint32_t lastDrawMs = 0; static bool dirty = true;

static const char* NAMES[6] = {"?", "BOOST", "ROCKET", "SHELL", "LIGHTNING", "MUD"};
static const uint16_t COLORS[6] = {0xFFFF, 0xFD20, 0xFFE0, 0x3FE8, 0xFFE6, 0xCC68};

static void onRecv(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
  if (len != (int)sizeof(GkInvFrame)) return;
  const GkInvFrame* f = (const GkInvFrame*)data;
  if (f->m0 != 'G' || f->m1 != 'I' || f->ver != 1) return;
  rxKart = f->kart; rxSeq = f->seq; rxN = f->n > 3 ? 3 : f->n;
  for (int i = 0; i < 3; i++) rxItems[i] = f->items[i];
  memcpy(heltecMac, info->src_addr, 6); heltecKnown = true;
  lastRxMs = millis(); frameFresh = true;
}

static void sendUse(uint8_t slot) {
  if (!heltecKnown) return;
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, heltecMac, 6);
  peer.channel = 0; peer.ifidx = WIFI_IF_STA; peer.encrypt = false;
  esp_now_del_peer(heltecMac); esp_now_add_peer(&peer);
  GkUseFrame f = {'G', 'U', 1, kart, slot, ++useSeq};
  esp_now_send(heltecMac, (const uint8_t*)&f, sizeof f);
  useSentMs = millis(); useTries = 1; useSlot = slot;
}

static void glyph(int cx, int cy, uint8_t code, uint16_t col) {
  if (code == 1) {                      // boost: double chevron up
    for (int k = 0; k < 2; k++) {
      int y = cy + 18 - k * 34;
      cv.fillTriangle(cx - 38, y + 18, cx + 38, y + 18, cx, y - 18, col);
      cv.fillTriangle(cx - 26, y + 18, cx + 26, y + 18, cx, y - 4, TFT_BLACK);
    }
  } else if (code == 2) {               // rocket
    cv.fillTriangle(cx, cy - 46, cx - 20, cy - 6, cx + 20, cy - 6, col);
    cv.fillRect(cx - 20, cy - 6, 40, 44, col);
    cv.fillTriangle(cx - 20, cy + 38, cx - 38, cy + 52, cx - 20, cy + 14, col);
    cv.fillTriangle(cx + 20, cy + 38, cx + 38, cy + 52, cx + 20, cy + 14, col);
    cv.fillTriangle(cx - 10, cy + 40, cx + 10, cy + 40, cx, cy + 62, 0xFC00);
    cv.fillCircle(cx, cy + 8, 9, TFT_BLACK);
  } else if (code == 3) {               // shell
    cv.fillCircle(cx, cy, 42, col);
    cv.fillCircle(cx, cy, 26, TFT_WHITE);
    cv.fillRect(cx - 46, cy + 18, 92, 26, col);
  } else if (code == 4) {               // lightning
    cv.fillTriangle(cx + 16, cy - 50, cx - 26, cy + 10, cx + 2, cy + 10, col);
    cv.fillTriangle(cx - 16, cy + 50, cx + 26, cy - 10, cx - 2, cy - 10, col);
  } else if (code == 5) {               // mud
    cv.fillCircle(cx, cy + 10, 40, col);
    cv.fillCircle(cx - 18, cy - 14, 18, col);
    cv.fillCircle(cx + 16, cy - 18, 14, col);
  }
}

static void draw() {
  int W = M5.Display.width(), H = M5.Display.height();
  cv.createSprite(W, H);
  cv.fillSprite(TFT_BLACK);
  bool link = locked && millis() - lastRxMs < 3000;
  cv.setTextDatum(top_left);
  cv.setFont(&fonts::DejaVu18);
  cv.setTextColor(link ? TFT_GREEN : TFT_RED);
  cv.drawString(link || kart ? (String("KART ") + kart) : "NO KART", 10, 8);
  cv.setTextDatum(top_right);
  cv.setTextColor(TFT_DARKGREY);
  cv.drawString(String(M5.Power.getBatteryLevel()) + "%", W - 10, 8);
  cv.fillCircle(W / 2, 17, 6, link ? TFT_GREEN : TFT_RED);

  if (!link) {
    cv.setTextDatum(middle_center);
    cv.setTextColor(TFT_WHITE);
    cv.setFont(&fonts::DejaVu24);
    cv.drawString("LOOKING", W / 2, H / 2 - 30);
    cv.drawString("FOR KART", W / 2, H / 2);
    cv.setFont(&fonts::DejaVu18);
    cv.setTextColor(TFT_DARKGREY);
    cv.drawString(locked ? "signal lost" : (String("channel ") + scanCh), W / 2, H / 2 + 40);
  } else if (n == 0) {
    cv.setTextDatum(middle_center);
    cv.setFont(&fonts::DejaVu40);
    cv.setTextColor(TFT_DARKGREY);
    cv.drawString("?", W / 2, H / 2 - 24);
    cv.setFont(&fonts::DejaVu18);
    cv.setTextColor(TFT_WHITE);
    cv.drawString("NO ITEMS", W / 2, H / 2 + 28);
    cv.setTextColor(TFT_DARKGREY);
    cv.drawString("hit a ? box", W / 2, H / 2 + 56);
  } else {
    if (sel >= n) sel = n - 1;
    uint8_t code = items[sel] < 6 ? items[sel] : 0;
    uint16_t col = COLORS[code];
    glyph(W / 2, H / 2 - 40, code, col);
    cv.setTextDatum(middle_center);
    cv.setFont(&fonts::DejaVu24);
    cv.setTextColor(col);
    cv.drawString(NAMES[code], W / 2, H / 2 + 46);
    bool using_ = useTries && millis() - useSentMs < 1500;
    cv.setFont(&fonts::DejaVu18);
    cv.setTextColor(using_ ? TFT_YELLOW : TFT_WHITE);
    cv.drawString(using_ ? "USING..." : "TAP TO USE", W / 2, H / 2 + 82);
    for (int i = 0; i < n; i++)                             // slot dots
      cv.fillCircle(W / 2 + (i - (n - 1) / 2.0f) * 24, H - 26, i == sel ? 8 : 5,
                    i == sel ? TFT_WHITE : TFT_DARKGREY);
    if (n > 1) {                                            // swipe arrows
      cv.setTextColor(TFT_DARKGREY);
      cv.setTextDatum(middle_left);  cv.drawString("<", 8, H / 2 - 40);
      cv.setTextDatum(middle_right); cv.drawString(">", W - 8, H / 2 - 40);
    }
  }
  cv.pushSprite(0, 0);
  cv.deleteSprite();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setRotation(ROT);
  M5.Display.setBrightness(200);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_now_init();
  esp_now_register_recv_cb(onRecv);
  esp_wifi_set_channel(scanCh, WIFI_SECOND_CHAN_NONE);
}

void loop() {
  M5.update();
  uint32_t ms = millis();

  if (frameFresh) {                      // adopt the newest broadcast
    frameFresh = false;
    locked = true; kart = rxKart;
    if (rxSeq != invSeq) {
      invSeq = rxSeq; n = rxN;
      for (int i = 0; i < 3; i++) items[i] = rxItems[i];
      if (sel >= n) sel = n ? n - 1 : 0;
      useTries = 0;                      // inventory changed: the use landed (or is moot)
      dirty = true;
    }
  }
  if (!locked && ms - scanHopMs > 400) { // hunt for the kart across channels
    scanHopMs = ms;
    scanCh = scanCh >= 13 ? 1 : scanCh + 1;
    esp_wifi_set_channel(scanCh, WIFI_SECOND_CHAN_NONE);
    dirty = true;
  }
  if (locked && ms - lastRxMs > 10000) { // lost for 10 s: hunt again
    locked = false; scanHopMs = 0; dirty = true;
  }
  if (useTries && useTries < 3 && ms - useSentMs > 120) {   // use: 3 sends, the Pi de-duplicates by seq
    GkUseFrame f = {'G', 'U', 1, kart, useSlot, useSeq};
    esp_now_send(heltecMac, (const uint8_t*)&f, sizeof f);
    useTries++;
  }

  // touch: swipe = pick a slot, tap = use (rotation is fixed: no gestures can flip it)
  static bool down = false; static int x0 = 0, y0 = 0; static uint32_t downMs = 0; static bool acted = false;
  auto t = M5.Touch.getDetail();
  if (t.isPressed() && !down) { down = true; acted = false; x0 = t.x; y0 = t.y; downMs = ms; }
  else if (t.isPressed() && down && !acted) {
    int dx = t.x - x0;
    if (abs(dx) > 50 && n > 1) {                                           // swipe
      sel = (sel + (dx < 0 ? 1 : n - 1)) % n; acted = true; dirty = true;
    }
  } else if (!t.isPressed() && down) {
    down = false;
    if (!acted && ms - downMs < 400 && n > 0 && locked && !useTries) {     // tap: use
      sendUse((uint8_t)sel); dirty = true;
    }
  }

  if (useTries && ms - useSentMs > 1400 && ms - useSentMs < 1600) dirty = true;   // clear USING...
  if (dirty && ms - lastDrawMs > 80) { lastDrawMs = ms; dirty = false; draw(); }
  if (!locked) dirty = true;             // scanning: keep the channel number live
  delay(5);
}
