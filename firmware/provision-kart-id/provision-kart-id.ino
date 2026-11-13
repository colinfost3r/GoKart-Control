// One-time helper for a NEW Heltec: store the fleet kart ID before the kart firmware first runs.
//
// kart-heltec-v4 falls back to DEFAULT_KART_ID 1 when no ID is stored and starts LoRa telemetry
// as soon as it boots, so a blank board would transmit as kart 1 next to the real kart 1 until
// someone types `id N`. Flash this first (same board options, so the partition table matches),
// read the confirmation line, then write the kart application at 0x10000 without erasing.
//
// This sketch starts no radio of any kind (no LoRa, Wi-Fi, BLE or ESP-NOW) and never talks to a
// VESC. It writes exactly one value: key "id" in the "gokart" preferences namespace.
//
//   arduino-cli compile --fqbn <the kart's Heltec FQBN> \
//     --build-property "compiler.cpp.extra_flags=-DKART_ID=4" \
//     --build-path build/provision-kart-id-4 provision-kart-id
#include <Preferences.h>

#ifndef KART_ID
#error "Build with -DKART_ID=N: the fleet ID assigned to this physical kart"
#endif
#if KART_ID < 1 || KART_ID > 8
#error "KART_ID must be 1..8"
#endif

static uint8_t before = 0, stored = 0;
static bool ok = false;

void setup() {
  Serial.begin(115200);
  Preferences prefs;
  const bool opened = prefs.begin("gokart", false);
  before = opened ? prefs.getUChar("id", 0) : 0;
  const size_t wrote = opened ? prefs.putUChar("id", (uint8_t)KART_ID) : 0;
  stored = opened ? prefs.getUChar("id", 0) : 0;
  prefs.end();
  ok = opened && wrote == 1 && stored == KART_ID;
}

void loop() {
  Serial.printf("{\"t\":\"provision_id\",\"want\":%d,\"before\":%u,\"stored\":%u,\"ok\":%s}\n",
                (int)KART_ID, (unsigned)before, (unsigned)stored, ok ? "true" : "false");
  delay(1000);
}
