# Prebuilt images

**M5 v1.5 Core2 dashboard:** the generic `core2-items`/kart merged images below are not
the paired no-Pi dashboard candidates. Use [the November 12 handoff](../../docs/CLAUDE_HANDOFF.md)
and its application-image manifest; preserve each board’s NVS.

> **Current images: kart 0.3.6, base and repeater 0.2.2, Core2 item screen 0.3.6** (2026-11-13, below). `kart-heltec-v4-ble-0.1.0.merged.bin` and the 0.2.0
> set are kept for rollback only; 0.1.0 predates the relay bit, `slow_mph`, BOOST, RACE and the
> 27-byte beacon. To refresh: `./build.sh kart compile` (also `base`, `repeater`), copy
> `build/<sketch>/<sketch>.ino.merged.bin` here under a new version name, add the row and the
> SHA-256 (`shasum -a 256 <file>`), and bump `FW_VERSION` in each `config.h`.

Built from this branch with `firmware/build.sh` (arduino-cli, esp32 core 3.3.8). No
credentials inside: WiFi/OTA settings live in the board's flash and are entered over
the USB console after flashing. Rebuild from source if you prefer; the hash lets you
check what you got.

| File | Board | Build | SHA-256 |
| --- | --- | --- | --- |
| `kart-heltec-v4-ble-0.3.2.merged.bin` | Heltec WiFi LoRa 32 V4.3 | ESP-NOW channel pinned across WiFi reconnect scans (stored AP channel, re-set 6 s after each retry), broadcasts every 400 ms | `da66b5f7c6958bd9f91deaa9f2668c191e5f43ef22d1d85cf65073528b7484ca` |
| `kart-heltec-v4-ble-0.3.3.merged.bin` | Heltec WiFi LoRa 32 V4.3 | WiFi reconnect scans only while the kart is stationary (VESC/GPS speed gate), channel re-pin 2.5 s after a retry | `faf7cef3f319c4e2bacb43c776c12d2b186dc2681ccc38ff51de1ee10a8088ed` |
| `kart-heltec-v4-ble-0.3.4.merged.bin` | Heltec WiFi LoRa 32 V4.3 | no WiFi at all when the stored SSID is empty / `none` / `clear` / `off` (the radio stays parked on the Core2 channel), no driver-side reconnect loop (`WiFi.setAutoReconnect(false)`: a missing network made the core rescan continuously and only one Core2 tap in three got through), `wifi clear` on the USB console. App-only flash keeps NVS: `esptool --chip esp32s3 write_flash 0xe000 otadata 0x10000 kart-heltec-v4.ino.bin` | `b157c64b6981f04bc1b6bb30d23a58aebf5e75e0eceeb8e43175cc091efa5e34` |
| `kart-heltec-v4-ble-0.3.5.merged.bin` | Heltec WiFi LoRa 32 V4.3 | **one fixed ESP-NOW channel** (`GK_ESPNOW_CH` = 1) whenever WiFi is off, pinned at init. ESP-NOW has no channel negotiation: the kart was parked on a remembered AP channel (6) while its Core2 had settled on another (4), so every tap went to an empty channel and no `invuse` ever reached the Pi (kart 1, 2026-11-13). A remembered AP channel is now only honoured while WiFi is actually in play (OTA at the pit). | `944958e51a6239dced9bd773c97a3a5da83bf8bca3c4e134f79633ca6aa60d21` |
| `kart-heltec-v4-ble-0.3.6.merged.bin` | Heltec WiFi LoRa 32 V4.3 | **a carried SHIELD blocks one hit**: a shell / lightning that would have applied is eaten instead (no SLOW, hit line `why:"shield"`, the shield leaves the Core2 at once, the Pi spends its copy and the dash says BLOCKED!). Before, a shield only blocked the pit game's mud: kart 1 took kart 2's shell while holding one (2026-11-13). App-only flash as 0.3.4. | `9d3069b5458f77e90c66e8dc9d06bc279c7f9374df270a05d518ff8667f03c40` |
| `core2-items-0.3.6.merged.bin` | M5Stack Core2 | matching fixed channel (`FIXED_CH` = 1): with no WiFi credentials it sits on the kart's channel instead of hopping 1-13 (hunting is how it settled on ch 4 while its kart sat on ch 6). Falls back to hopping after 30 s of silence, so a kart still on an AP channel is found anyway. | `06dc30df4b0b0ed8698e68edc18324c5c74c9ccca4e5d836507ab60d9638f5bb` |
| `core2-items-0.2.1.merged.bin` | M5Stack Core2 | rides out WiFi-scan gaps (6 s link grace, rehunt only after 20 s, from the last good channel) | `9816b295836c68a339f9b8106ac77bf3ed5de9856c71e33fae7d2d4582b900f0` |
| `core2-items-0.2.2.merged.bin` | M5Stack Core2 | power follows the kart key: USB power lost -> 15 s on-screen countdown -> power off (tap to stay on) | `c70d1cd812c5147864c0d444eaa3a19c80a94949d3f1c7b98e57c8545bb78228` |
| `core2-items-0.3.0.merged.bin` | M5Stack Core2 | OTA over the pit AP (joins at boot, ArduinoOTA as gokart-core2.local; `wifi SSID PASS` over USB once, NVS) | `e92c9f7e2111a4ec3d6318a13ead7ab2fe9b952d3dbb668300993547263781b3` |
| `core2-items-0.3.1.merged.bin` | M5Stack Core2 | kart pinning (`kart 1-8\|any` on the USB console, NVS): two karts broadcast now, a unit shows only its own kart | `d400f39dd64e0ea78bb3f0db9e67f1e4d3a83b31cc7247891f094bc0c8a5051c` |
| `core2-items-0.3.2.merged.bin` | M5Stack Core2 | kart-first channels: on WiFi with the pinned kart silent 15 s, drop WiFi and hunt (two shop APs share the SSID on different channels); per-kart OTA hostname gokart-core2-N | `04248c956b044721ea16e5edac2d62100d34a0028d0944404641e71f5c651095` |
| `core2-items-0.3.3.merged.bin` | M5Stack Core2 | use-frames reach the kart again: unicast peer pinned to the radio's real channel (stale ch-0 peer after the WiFi drop ate every send); spent retries clear after 2 s | `e89fbef781e6ca918b53e0ff89f26e9186ed383d10419bdd1dc6f48eeb568b47` |
| `core2-items-0.3.5.merged.bin` | M5Stack Core2 | radio sleep off, per-send delivery report + `use` on the USB console (bench testing); ROOT CAUSE of dead taps = the kart Heltec's WiFi power-save (see changelog) | `994e9c86e893ac4a86b81a436d8fbbe1b1e9d40edc990abde83394cbc9cb132a` |
| `kart-heltec-v4-ble-0.3.1.merged.bin` | Heltec WiFi LoRa 32 V4.3 | 0.3.0 with the five new item codes (boost3/star/magnet/hotlap/shield) and charge counts in the Core2 frames | `4d403b51b4793b804a459f72f2e19634efde77a7d5a8cda24f48689f29f892f3` |
| `core2-items-0.2.0.merged.bin` | M5Stack Core2 | item screen with the five new cards (dash-matched art, charge badge, per-item action labels) | `4a41df3a2fdff984bbe9b5c7d7b872d92470831ac1af4f39c57d7b03986587d8` |
| `kart-heltec-v4-ble-0.3.0.merged.bin` | Heltec WiFi LoRa 32 V4.3 | kart node 0.3.0: 0.2.7 + ESP-NOW Core2 item-screen bridge (`inv` line in, broadcast out, `invuse` relay) | `76f38e10ccc228ae6729db796d8f506811ad2550e6e3f438413d17f5335549f1` |
| `core2-items-0.1.0.merged.bin` | M5Stack Core2 | bar-mounted item screen: ESP-NOW channel hunt, swipe/tap to use, fixed rotation for the cradle | `667a1aa214b991d51231cc2c1658c48ea0b63744db050b5551a24fefc0e5e502` |
| `core2-items-0.1.1.merged.bin` | M5Stack Core2 | 0.1.0 with the rotation fixed for the cradle (flip gesture removed) and the item art redrawn to match the dash icons (chevrons / white rocket / turtle shell / bolt, mode sub-labels) | `c3ba83cd0192d530f935425549863d0a8f7e4c6e9dc14d19856fd4b69025c79a` |
| `kart-heltec-v4-ble-0.1.0.merged.bin` | Heltec WiFi LoRa 32 V4.3 | kart node, VESC over BLE (MTU-chunked writes), per-controller limits, SLOW + brake request, 2 Hz, 16777216 bytes | `9f2994756dc42af61051fbd7cfc24a81caafd142c01f7f0955c53c4353a30799` |

## Flash with esptool (PlatformIO's or pip's)

```sh
esptool.py --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 921600 \
  --before default_reset --after hard_reset write_flash 0x0 \
  firmware/releases/kart-heltec-v4-ble-0.1.0.merged.bin
```

The merged image includes bootloader, partition table and app, so it goes to address 0.
A board running an Arduino hardware-CDC image (Colin's bench image included) resets
into the bootloader by itself; if esptool says "No serial data received", hold BOOT
while plugging the USB cable in.

## Configure over the USB console (115200, newline-terminated)

```
id 1                                    # fleet id for this kart
vescuuid 2c004c000951343037353739       # the baseline kart's controller UUID (from the 2026-11-05 capture)
blescan                                 # lists every "VESC BLE UART" in range with RSSI (VESC must be powered and not connected to anything else)
vescmac AA:BB:CC:DD:EE:FF               # pin the VESC's address from that list; the board connects only to it
wifi <ssid> <password>                  # optional, for over-the-air updates
reboot
status                                  # vesc_fw 6.00, id_ok true, sync pps/beacon, rate 2
```

Nothing is written to the VESC until a command arrives (pit kiosk or console
`stop` / `start` / `mode 0..2`). First test with the drive wheels off the ground.
Roll back any time with your own image.

## 0.2.0 (2026-11-06 evening, built from this branch after the firmware review pass)

- `kart-heltec-v4-ble-0.2.0.merged.bin` — flash at 0x0 (16 MB layout, BLE transport). Includes the relay bit, slow_mph, BOOST, RACE (grid hold / finish), RATE, the 27-byte beacon with race positions, fixed-pin 9600/5 Hz GPS with recovery, and the review fixes (command history dedupe, write gating, slot timing).
- `base-tbeam-s3-0.2.0.merged.bin` — flash at 0x0 (8 MB layout). Beacon with race state/positions, repeater heartbeat decode, schedule-based command placement, host `race`/`issued` lines.
- `repeater-tbeam-s3-0.2.0.merged.bin` — flash at 0x0. Accepts 27-byte beacons; 400 ms dedupe; late-copy drop. Fleet must run `rate 1` while a repeater is in use.
Bench 2026-11-06 21:33: kart 2 + base on these builds, live bench 16 pass / 0 loss / ping + race + writes outcomes as expected (no VESC linked).

## 0.2.1 (2026-11-07, radio power)

Same radio parameters as 0.2.0 (915.0 MHz, BW500, SF7), so 0.2.0 and 0.2.1 boards interoperate.

- `repeater-tbeam-s3-0.2.1.merged.bin` — SX1262 at 22 dBm (was 20), boosted receive gain, `tx_dbm` in the stat line, `FW_VERSION` finally reports the real version. **Flashed** on the repeater 2026-11-07 12:22 (bench: `rx_bad` 0, heard = relayed, heartbeat decoded by the pit).
  SHA-256 `6a49788d5044981e96b612a0de24ae2ee685dc37fd7447038e9c5b20b4d42fdd`
- `base-tbeam-s3-0.2.1.merged.bin` — same two radio changes, `tx_dbm` in `stat`. **Flashed** on the pit base 2026-11-07 12:25 from the pit Pi (`~/flash_base.sh`, esptool 5.6 in `~/esptool-venv`; the Debian `esptool` package has no ESP32-S3 stub).
  SHA-256 `19976e0be07ed6bed5d6d9375106b120a5a0e76ccb01ce470b6c7ddccbdf264e`
- `kart-heltec-v4-ble-0.2.1.merged.bin` — SX1262 drive into the KCT8103L front end 16 dBm (about 27 dBm radiated; 0.2.0 used 10 -> ~23), boosted receive gain, stored console `txpower 0..22`, `tx_dbm` / `tx_radiated_dbm` in `status`. **Superseded by 0.2.2** before it was flashed (its radio change is in 0.2.2). After flashing, watch the kart Pi's `dmesg -w` for USB resets while it transmits; `txpower 14` or lower if the Pi's 5 V cannot carry the 750 mA peaks.
  SHA-256 `b24703a90fee717ce627b0815758af39d94b2babd6ea4582739b35998fb62c01`

## 0.2.2 (2026-11-07 evening, kart only: modes are speed caps)

Radio unchanged (interoperates with the 0.2.0 / 0.2.1 base and repeater, which stay on 0.2.1).

- `kart-heltec-v4-ble-0.2.2.merged.bin` — ECO / NORMAL / SPORT are now a top-speed cap plus a torque scale (`config.h MODES[]`: 15 mph + 0.50, 25 mph + 0.75, uncapped + 1.0; the old 80 / 100 / 140 A current-only modes were indistinguishable on the kart), the cap computed from the controller's own poles / gear / wheel like SLOW; a BOOST above the mode's scale lifts the cap one mode up for its duration; `mode_actual` and the write verify check the ERPM bound as well as the scale; a capped mode is `rejected` on a controller without drivetrain numbers; `cap_mph` / `cap_erpm` / `baseline_suspect` in `status`; the OLED shows the cap. **Flashed on kart 2** 2026-11-07 20:14 over WiFi (`python3 ~/Library/Arduino15/packages/esp32/hardware/esp32/3.3.8/tools/espota.py -i 192.168.151.44 -p 3232 -f firmware/build/kart-heltec-v4/kart-heltec-v4.ino.bin`; OTA takes the app image `kart-heltec-v4.ino.bin` from the same build, not the merged image). The mode read-back test is still owed (the VESC was off). Test wheels-up first: after `mode 0`, `status` must show `scale_max` 0.500 and `max_erpm` 6115 on the baseline drivetrain (`mode 1`: 0.750 / 10191; `mode 2`: 1.000 and the controller's own bound back); then the 0.2.1 radio-power watch (`dmesg -w` on the kart Pi for USB resets).
  SHA-256 `c3ecc33fe881f3ccd3b0636e24002a6a690b7a223e1d60b4671565ec187a6b20`

## 0.2.3 (2026-11-09 evening, kart only: speed calibration + pit mode releases SLOW)

Radio unchanged (interoperates with the 0.2.1 base and repeater).

- `kart-heltec-v4-ble-0.2.3.merged.bin` — the mode speed caps are now multiplied by a per-kart speed
  calibration (`config.h SPEED_CAL_DEFAULT 2.48`, console `speedcal X|clear`, status `speed_cal`):
  measured on kart 2 by GPS vs ERPM, the controller's si_* numbers are off by 2.48x, so the 15 / 25 mph
  caps were really 6 / 10 mph and SLOW 5 was 2 mph. A mode command from the pit now releases SLOW (the
  driver's own mode buttons still do not; START still does). Flashed to kart 2 by OTA 2026-11-09.
  SHA-256 `f04cba51e704c429c7cb1106acd147ea452e686c5bd6cf218554d107d55f0ab7`

## 0.2.4 (2026-11-09 night, kart only: timed SLOW for the game's mud)

Radio unchanged (interoperates with the 0.2.1 base and repeater).

- `kart-heltec-v4-ble-0.2.4.merged.bin` — USB console `slow MPH SECS` (SECS 1-60) caps speed for SECS
  seconds and then returns by itself to whatever cap was in force before (a pit SLOW comes back); a timed
  slow never raises a pit cap that is already lower. The kart display uses it for mud (`slow 5 4`): "mud
  mode should actually make the kart go into slow mode". START and a pit mode command still clear every
  SLOW. Flashed to kart 2 by OTA 2026-11-09.
  SHA-256 `2dfc5913466da0c4762649b516dc305920029c2c811645e9caac4caa764c0969`

## 0.3.0 kart + core2-items 0.1.0 (2026-11-10, Core2 item screen)

- `kart-heltec-v4-ble-0.3.0.merged.bin` — 0.2.7 plus the ESP-NOW bridge for the bar-mounted Core2
  item screen: the Pi pushes carried items with the USB `inv a b c` / `inv -` line, the Heltec
  broadcasts them once a second (12-byte frame, current WiFi channel), and a Core2 "use" frame
  comes back as a `{"t":"invuse","slot":N,"seq":Q}` line for the Pi (seq de-duplicated). No LoRa,
  BLE or drive-path changes. **Flashed on kart 2** 2026-11-10 over WiFi (espota).
- `core2-items-0.1.0.merged.bin` — M5Stack Core2 "your items" screen: hops channels until it hears
  a kart's inventory broadcast, then shows the carried prizes (swipe to pick, tap to use, slot
  dots, battery + link header). Rotation fixed for the bar cradle; no WiFi join, no credentials.
  Needs the kart Pi's `item_hold` config (default true) and kart 0.3.0.

## 0.3.1 kart + core2-items 0.2.0 (2026-11-10 evening, five new items)

- Five new carried freeplay prizes rolled on the kart Pi (kartcore): **shield** (auto-blocks one
  mud), **triple boost** (one card, three taps), **star** (8 s SPORT + mud immunity), **magnet**
  (double box pickup radius, 20 s), **hot lap** (beat your best lap -> a rocket, miss -> mud).
  The Heltec only forwards names/codes; no LoRa, BLE or drive-path changes.
- `kart-heltec-v4-ble-0.3.1.merged.bin` adds the codes 6-10 and a charges nibble to the ESP-NOW
  inventory frame. Flashed on kart 2 over WiFi (espota).
- `core2-items-0.2.0.merged.bin` draws the new cards, the "x3" charge badge, and per-item action
  text (hot lap arms, shield says it blocks by itself). Flashed over USB.

## kart 0.3.6 (2026-11-13 evening, the shield blocks a hit)

The Heltec applies a hit's SLOW itself, before the Pi hears of it, so the carried SHIELD (the
Pi's `inv` line, "AUTO BLOCK" on the dash) is spent there: `applyHit` checks it last in the
W-rules (a stopped / grid-held / writes-off kart keeps its shield), prints `why:"shield"` with
`applied:false`, drops it from the Core2 frame at once, and the Pi spends its own copy
(`shield_broke`) or resends the `inv` line if it carried none. The `inv` parser now reads every
token, so a shield past the three Core2 slots still counts. Why: the shield had only ever blocked
the pit game's mud; kart 1 took kart 2's shell with one loaded and kept it (2026-11-13). The
attacker is still acked and scores: no room in the game bytes for "blocked".

## core2-items 0.3.5 (2026-11-12 evening, the real tap bug: WiFi power-save on the kart)

0.3.3's channel pin was not it. A diagnostic build added the ESP-NOW send callback and a `use`
console command, and the bench showed `esp_now_send` accepting every frame while the callback
said FAILED: the kart Heltec, associated to the shop AP, naps its radio between beacons
(modem-sleep is the ESP32 default while joined) and never ACKs a directed frame -- its own
broadcasts still go out, so the item card looks perfect and taps die. With WiFi off on both ends
the callback says delivered and the use reaches the Pi (`core2@espnow` op). Interim fix in the
field: both kart Heltecs have their WiFi credentials replaced with a non-existent SSID (the kart
firmware has no `wifi clear` yet) and both Core2s have WiFi cleared -- updates go over USB (the
Core2 at the Mac; the Heltec from its own Pi with esptool). Proper fix to come in the kart
firmware: `WiFi.setSleep(false)` after `WiFi.begin` (bench-test first: an untested attempt
today reboot-looped kart 2) and a real `wifi clear`. Also: flashing a *merged* image wipes NVS
(kart id, VESC pin, WiFi, speedcal) -- re-provision afterwards, or OTA the app-only image.

## core2-items 0.3.3 (2026-11-12, taps reach the kart again)

Field bug behind "USING... flashed but nothing happened": after the WiFi-drop re-tune, the
unicast peer added with channel 0 ("current") still resolved against the old AP channel, so
every GkUseFrame died silently while the kart's broadcasts kept arriving (RX needs no peer
record). The peer is now pinned to esp_wifi_get_channel's live answer. Spent use-retries also
cleared only on an inventory change, eating later taps; they now reset after 2 s.

## core2-items 0.3.2 (2026-11-12, the kart comes first)

Field bug: the shop has two APs on the SSID on different channels. Kart 2's Core2 joined the
ch-6 AP for OTA while kart 2's Heltec sat pinned to the ch-9 AP -- the item screen never heard
its kart while WiFi was up. 0.3.2 drops WiFi whenever the pinned kart has been silent 15 s
after a join and goes hunting (OTA then waits for the next boot). OTA hostnames are per kart
(gokart-core2-N), since two units on one network collided on gokart-core2.local.

## core2-items 0.3.1 (2026-11-12, kart pinning + serial fix)

With two karts live, an unpinned Core2 adopts whichever inventory broadcast lands last and
flickers between karts. `kart N` on the USB console (NVS) makes a unit ignore every other kart;
`kart any` restores the old behaviour. Explicit Serial.begin (the console was silent on a fresh
unit), and set_wifi.py stops asserting DTR/RTS (which reset or held the board via the USB bridge).
Second Core2 (usbserial-0202E426) flashed, pinned to kart 1, WiFi stored, OTA confirmed.

## core2-items 0.3.0 (2026-11-11, OTA over the pit AP)

Updates no longer need the USB cable. The Core2 joins the pit AP at boot (25 s window, then it
gives up until the next boot -- a reconnect scan would drag the radio off the ESP-NOW channel
mid-ride; since 0.2.2 powers off at key-off, every session is a fresh boot and the pit always
gets a join) and runs ArduinoOTA as `gokart-core2.local`. While joined, the radio sits on the
AP's channel, which is the kart Heltec's pinned channel, so the item screen works at the pit too
(sky-blue dot next to the link dot = OTA reachable). Credentials are NVS-only (`wifi SSID PASS`
on the USB console, set once with core2-items/set_wifi.py; `status` and `wifi clear` also exist):
the repo is public, so they are never compiled into an image. Flash:
`espota.py -i gokart-core2.local -p 3232 -f core2-items.ino.bin`

## core2-items 0.2.2 (2026-11-11, power follows the kart key)

The cradle feeds the Core2 from the kart's USB, and the AXP PMIC already boots it when VBUS
appears -- but at key-off the internal battery kept it running for hours. 0.2.2 watches VBUS
(M5.Power.getVBUSVoltage, AXP192 and AXP2101 alike): power gone -> a full-screen 15 s countdown
("KART OFF / TAP TO STAY ON") -> clean M5.Power.powerOff(). A tap during the countdown keeps it
on for handheld use until USB power is next seen, which re-arms the auto-off. Units whose PMIC
cannot report VBUS (reading -1) never auto-off.

## 0.3.3 kart (2026-11-11, no WiFi scans while driving)

0.3.2's re-pin still left a ~6 s broadcast blackout every 30 s while away from the pit (the scan
itself, plus the 6 s wait before the re-pin), right at the Core2's link-grace limit. 0.3.3 skips
WiFi reconnects entirely while the kart is moving (VESC ERPM above ~1.5 mph, or GPS above 4 km/h) --
WiFi only matters at the pit for OTA, and the kart is stopped there -- and re-pins the channel 2.5 s
after a retry instead of 6. The Core2 image is unchanged (0.2.1).

## 0.3.2 kart + core2-items 0.2.1 (2026-11-10 night, Core2 link dropouts)

Field bug: away from the pit AP the kart's WiFi reconnect scan (every 30 s) hopped the radio and
parked it on a random channel, so the Core2's locked channel went quiet and the item screen kept
losing the kart. The Heltec now stores the AP's channel and pins the radio back to it once each
scan is over, and broadcasts the inventory every 400 ms; the Core2 tolerates the remaining short
gaps and, if truly lost, rehunts starting from the channel that last worked.
