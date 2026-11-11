/* GoKart Core2 item screen ("your items", bar-mounted M5Stack Core2).
 *
 * Listens for the kart Heltec's ESP-NOW inventory broadcasts (kart-0.3.0 `inv` line from the Pi),
 * shows the carried item-box prizes, swipe left/right to pick one, tap to USE it (sent back to the
 * Heltec, which relays {"t":"invuse",...} to the Pi over USB). No WiFi join: it hops channels until
 * it hears a kart, then stays on that channel (tolerating the short gaps while the kart Heltec
 * retries its pit WiFi). The rotation is fixed for the bar cradle (ROT below):
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

/* Names, colors and shapes mirror the dash (app.js ITEM_SVG / ITEM_COLOR / ITEM_SUB).
   Codes: 1 boost, 2 rocket, 3 shell, 4 lightning, 5 mud, 6 boost3, 7 star, 8 magnet,
   9 hotlap, 10 shield; a frame byte is code | (charges-1)<<4. */
static const char* NAMES[11] = {"?", "BOOST", "ROCKET", "SHELL", "LIGHTNING", "MUD",
                                "BOOST x3", "STAR", "MAGNET", "HOT LAP", "SHIELD"};
static const char* SUBS[11]  = {"", "> NORMAL", "> SPORT", "", "", "",
                                "> NORMAL x3", "SPORT + IMMUNE", "BIG PICKUP", "BEAT YOUR BEST", "AUTO BLOCK"};
static const uint16_t COLORS[11] = {0xFFFF, 0xFD80, 0xFEA0, 0x3EF0, 0xFF20, 0xC449,
                                    0xFD80, 0xFEA0, 0xFAEB, 0x7EBF, 0x3D30};
static const uint16_t C_FLAME = 0xFBC0, C_FLAMEIN = 0xFEA0, C_PORT = 0x2BDF;

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

// glyphs in the dash's 100x100 viewBox, scaled to GS around (cx, cy)
static const float GS = 1.24f;
static int gx, gy;
static inline int X(float x) { return gx + (int)lroundf((x - 50) * GS); }
static inline int Y(float y) { return gy + (int)lroundf((y - 50) * GS); }
static void wline(float x0, float y0, float x1, float y1, float r, uint16_t col) {
  cv.drawWideLine(X(x0), Y(y0), X(x1), Y(y1), r * GS, col);
}
static void boltPoly(float grow, uint16_t col) {       // the dash bolt, fan-triangulated from (45,56)
  static const float P[6][2] = {{60, 3}, {18, 56}, {45, 56}, {34, 97}, {82, 40}, {54, 40}};
  float cxp = 48.8f, cyp = 48.7f, q[6][2];
  for (int i = 0; i < 6; i++) { q[i][0] = cxp + (P[i][0] - cxp) * grow; q[i][1] = cyp + (P[i][1] - cyp) * grow; }
  for (int i = 0; i < 4; i++)
    cv.fillTriangle(X(q[2][0]), Y(q[2][1]), X(q[(3 + i) % 6][0]), Y(q[(3 + i) % 6][1]),
                    X(q[(4 + i) % 6][0]), Y(q[(4 + i) % 6][1]), col);
}
static void glyph(int cx, int cy, uint8_t code, uint16_t col) {
  gx = cx; gy = cy;
  if (code == 1) {                      // boost: double chevron, black outline under amber (dash exact)
    for (int k = 0; k < 2; k++) {
      float dy = k * 26;
      wline(18, 50 + dy, 50, 22 + dy, 10, TFT_BLACK); wline(50, 22 + dy, 82, 50 + dy, 10, TFT_BLACK);
    }
    for (int k = 0; k < 2; k++) {
      float dy = k * 26;
      wline(18, 50 + dy, 50, 22 + dy, 5.5f, col); wline(50, 22 + dy, 82, 50 + dy, 5.5f, col);
    }
  } else if (code == 2) {               // rocket: white body, white fins, orange/yellow flame, blue porthole
    cv.fillTriangle(X(40), Y(76), X(50), Y(99), X(60), Y(76), TFT_BLACK);        // flame outline
    cv.fillTriangle(X(42), Y(78), X(50), Y(95), X(58), Y(78), C_FLAME);
    cv.fillTriangle(X(45), Y(78), X(50), Y(88), X(55), Y(78), C_FLAMEIN);
    cv.fillTriangle(X(36), Y(50), X(17), Y(81), X(39), Y(76), TFT_BLACK);        // fins, outlined
    cv.fillTriangle(X(64), Y(50), X(83), Y(81), X(61), Y(76), TFT_BLACK);
    cv.fillTriangle(X(37), Y(53), X(22), Y(77), X(39), Y(73), TFT_WHITE);
    cv.fillTriangle(X(63), Y(53), X(78), Y(77), X(61), Y(73), TFT_WHITE);
    for (int i = 0; i <= 20; i++) {                                              // teardrop body by slices
      float t = i / 20.0f, y = 3 + t * 73;                                       // y 3..76
      float half = 13.5f * sqrtf(t > 0.08f ? t : 0.08f) + (t > 0.8f ? -8 * (t - 0.8f) : 0);
      cv.fillRect(X(50 - half) - 2, Y(y) - 3, (int)(2 * half * GS) + 4, 7, TFT_BLACK);
    }
    for (int i = 0; i <= 20; i++) {
      float t = i / 20.0f, y = 3 + t * 73;
      float half = 13.5f * sqrtf(t > 0.08f ? t : 0.08f) + (t > 0.8f ? -8 * (t - 0.8f) : 0);
      cv.fillRect(X(50 - half), Y(y) - 2, (int)(2 * half * GS), 5, TFT_WHITE);
    }
    cv.fillCircle(X(50), Y(38), (int)(10 * GS), TFT_BLACK);                      // porthole
    cv.fillCircle(X(50), Y(38), (int)(8 * GS), C_PORT);
  } else if (code == 3) {               // shell: white disc, green dome, black hex plates (dash exact)
    cv.fillEllipse(X(50), Y(54), (int)(46 * GS), (int)(40 * GS), TFT_BLACK);
    cv.fillEllipse(X(50), Y(54), (int)(44 * GS), (int)(38 * GS), TFT_WHITE);
    cv.fillEllipse(X(50), Y(48), (int)(40 * GS), (int)(34 * GS), TFT_BLACK);
    cv.fillEllipse(X(50), Y(48), (int)(38 * GS), (int)(32 * GS), col);
    const float hx[6][2] = {{38, 34}, {62, 34}, {70, 48}, {62, 62}, {38, 62}, {30, 48}};
    for (int i = 0; i < 6; i++)
      wline(hx[i][0], hx[i][1], hx[(i + 1) % 6][0], hx[(i + 1) % 6][1], 2.5f, TFT_BLACK);
    wline(38, 34, 30, 22, 2.5f, TFT_BLACK); wline(62, 34, 70, 22, 2.5f, TFT_BLACK);
    wline(70, 48, 86, 48, 2.5f, TFT_BLACK); wline(62, 62, 70, 74, 2.5f, TFT_BLACK);
    wline(38, 62, 30, 74, 2.5f, TFT_BLACK); wline(30, 48, 14, 48, 2.5f, TFT_BLACK);
  } else if (code == 4) {               // lightning: the dash bolt, black outline
    boltPoly(1.16f, TFT_BLACK);
    boltPoly(1.0f, col);
  } else if (code == 5) {               // mud splat
    cv.fillCircle(X(50), Y(58), (int)(32 * GS), TFT_BLACK);
    cv.fillCircle(X(50), Y(58), (int)(29 * GS), col);
    cv.fillCircle(X(84), Y(22), (int)(8 * GS), col);
    cv.fillCircle(X(16), Y(84), (int)(7 * GS), col);
  } else if (code == 6) {               // triple boost: three chevrons (dash boost3)
    for (int pass = 0; pass < 2; pass++) {
      float r = pass ? 4.5f : 8.5f; uint16_t c = pass ? col : TFT_BLACK;
      for (int k = 0; k < 3; k++) {
        float dy = k * 22;
        wline(20, 42 + dy, 50, 16 + dy, r, c); wline(50, 16 + dy, 80, 42 + dy, r, c);
      }
    }
  } else if (code == 7) {               // star with eyes (dash star)
    static const float SP[10][2] = {{50, 4}, {61, 36}, {95, 37}, {68, 58}, {78, 91},
                                    {50, 71}, {22, 91}, {32, 58}, {5, 37}, {39, 36}};
    for (int pass = 0; pass < 2; pass++) {
      float grow = pass ? 1.0f : 1.12f; uint16_t c = pass ? col : TFT_BLACK;
      for (int i = 0; i < 10; i++) {
        int j = (i + 1) % 10;
        cv.fillTriangle(X(50), Y(50),
                        X(50 + (SP[i][0] - 50) * grow), Y(50 + (SP[i][1] - 50) * grow),
                        X(50 + (SP[j][0] - 50) * grow), Y(50 + (SP[j][1] - 50) * grow), c);
      }
    }
    cv.fillCircle(X(40), Y(48), (int)(4.5f * GS), TFT_BLACK);
    cv.fillCircle(X(60), Y(48), (int)(4.5f * GS), TFT_BLACK);
  } else if (code == 8) {               // horseshoe magnet (dash magnet)
    for (int pass = 0; pass < 2; pass++) {
      float r = pass ? 7.5f : 10.5f; uint16_t c = pass ? col : TFT_BLACK;
      wline(34, 14, 34, 50, r, c); wline(66, 14, 66, 50, r, c);
      for (int a = 0; a <= 8; a++) {
        float t0 = 3.14159f * a / 8, t1 = 3.14159f * (a + 1) / 8;
        wline(50 - 16 * cosf(t0), 50 + 16 * sinf(t0), 50 - 16 * cosf(t1), 50 + 16 * sinf(t1), r, c);
      }
    }
    cv.fillRect(X(27), Y(8), (int)(15 * GS), (int)(12 * GS), TFT_WHITE);
    cv.fillRect(X(59), Y(8), (int)(15 * GS), (int)(12 * GS), TFT_WHITE);
  } else if (code == 9) {               // stopwatch (dash hotlap)
    cv.fillRect(X(42), Y(2), (int)(16 * GS), (int)(10 * GS), col);
    cv.fillCircle(X(50), Y(56), (int)(40 * GS), TFT_BLACK);
    cv.fillCircle(X(50), Y(56), (int)(37 * GS), TFT_WHITE);
    cv.fillCircle(X(50), Y(56), (int)(29 * GS), col);
    wline(50, 56, 50, 34, 3.5f, TFT_BLACK); wline(50, 56, 66, 64, 3.5f, TFT_BLACK);
  } else if (code == 10) {              // shield badge (dash shield)
    for (int pass = 0; pass < 2; pass++) {
      float g = pass ? 1.0f : 1.1f; uint16_t c = pass ? col : TFT_BLACK;
      static const float SH[7][2] = {{50, 5}, {88, 18}, {88, 48}, {72, 82}, {50, 96}, {28, 82}, {12, 48}};
      for (int i = 0; i < 7; i++) {
        int j = (i + 1) % 7;
        cv.fillTriangle(X(50), Y(50), X(50 + (SH[i][0] - 50) * g), Y(50 + (SH[i][1] - 50) * g),
                        X(50 + (SH[j][0] - 50) * g), Y(50 + (SH[j][1] - 50) * g), c);
      }
    }
  }
}

static void draw() {
  int W = M5.Display.width(), H = M5.Display.height();
  cv.createSprite(W, H);
  cv.fillSprite(TFT_BLACK);
  bool link = locked && millis() - lastRxMs < 6000;      // WiFi-reconnect scans can gap ~4 s
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
    uint8_t code = items[sel] & 0x0F;
    if (code > 10) code = 0;
    uint8_t charges = (items[sel] >> 4) + 1;
    uint16_t col = COLORS[code];
    glyph(W / 2, H / 2 - 40, code, col);
    cv.setTextDatum(middle_center);
    cv.setFont(&fonts::DejaVu24);
    cv.setTextColor(col);
    cv.drawString(NAMES[code], W / 2, H / 2 + 46);
    if (SUBS[code][0]) {                 // the mode it gives, like the dash prize wheel
      cv.setFont(&fonts::DejaVu12);
      cv.setTextColor(TFT_BLACK, TFT_WHITE);
      cv.drawString(String(" ") + SUBS[code] + " ", W / 2, H / 2 + 66);
      cv.setTextColor(TFT_WHITE, TFT_BLACK);
    }
    bool using_ = useTries && millis() - useSentMs < 1500;
    cv.setFont(&fonts::DejaVu18);
    cv.setTextColor(using_ ? TFT_YELLOW : TFT_WHITE, TFT_BLACK);
    const char* act = code == 10 ? "BLOCKS BY ITSELF" : code == 9 ? "TAP TO ARM" : "TAP TO USE";
    cv.drawString(using_ ? "USING..." : act, W / 2, H / 2 + 88);
    if (charges > 1) {                  // triple boost: taps left
      cv.setFont(&fonts::DejaVu24);
      cv.setTextColor(col, TFT_BLACK);
      cv.drawString(String("x") + charges, W - 34, 44);
    }
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
  if (locked && ms - lastRxMs > 20000) { // really lost: hunt again, starting where it last was
    locked = false; scanHopMs = 0; dirty = true;
    uint8_t cur; wifi_second_chan_t sc;
    if (esp_wifi_get_channel(&cur, &sc) == ESP_OK && cur >= 1 && cur <= 13) scanCh = cur;
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
