# M5 Core2 v1.5

Branch **`v1.5/m5-core2`**, including Eamon's `fc7e610` / kart 0.2.7 (2026-11-10).
Owner confirmed the display is **Core2 v1.3 / K010-V13** on 2026-11-09.
An alternative driver display for the existing Heltec + pit stack. The Pi v2 display remains
available. This milestone implements telemetry, mode requests, base-station status and a simple
north-up map. **Kart 3 live telemetry and authenticated Core2 OTA are verified on hardware;
mode writes and full fleet/driving acceptance remain pending.**

**2026-11-10 setup:** both full 16 MB rollback images are retained privately. Earlier USB
uploads and the four-target touch diagnostic succeeded; the owner also saw kart 3 in the pit.
Kart ID **3** is the owner-assigned fleet identity. It does **not** establish which VESC belongs
to this kart. Eamon's `fc7e610` identifies the previously reused BLE address as kart 2's controller;
verify kart 3's physical controller and both identity pins before the read-only telemetry test.
See the [identity check](BRINGUP.md#verify-kart-3s-controller-identity).

Core2 Wi-Fi maintenance/OTA is implemented for `m5-espnow`. **An authenticated application
upload succeeded; credentials survived restart, the maintenance window returned to off, and
ESP-NOW telemetry recovered.** The owner confirms live readings and working DASH/MAP tabs.
Kart 3 now has its own verified 6.02 / 75_300_R2 identity, recorded in the
[handoff](../../HANDOFF.md) and [sanitized evidence](../../hardware/m5/2026-11-10-kart3/README.md).
The installed Heltec remains read-only, so M5/pit mode selection is deliberately disabled.

## Ownership and compatibility

```text
VESC <-- BLE --> Heltec V4.3 + L76K <-- LoRa --> existing T-Beam / Pi 4 pit
                     |
             encrypted ESP-NOW
              or 230400 UART
                     |
                  M5 Core2
```

Heltec owns VESC identity, polling, motor profiles, calibration, LoRa and GPS. Core2 owns display
and touch only. The original M5 BLE client/profile writer is not included. It must be replaced
by this display image before using this topology. No two devices should connect to the same
VESC. The motor's wired controls and protection stay with the VESC.

The M5 targets are **opt-in**. Integration now includes Eamon's kart0.2.7 and 46/47/54-byte
radio support; an idle kart still sends 47 bytes. M5 ignores the multiplayer-only fields.
Active multiplayer requires updated base/repeater0.2.2; this first M5 telemetry test stays
out of game sessions. Normal `kart`, `kart-uart`, base, repeater and Pi builds retain
existing behavior. The M5 adapter changes no LoRa packet structs, IDs, frequency/rate/slots or
pit APIs. Both local transports carry the existing `self` and `fleet` JSON plus display-only
`display` metadata; existing USB telemetry stays compatible. ESP-NOW adds local USB pairing
and diagnostics. See [SERIAL_PROTOCOL](SERIAL_PROTOCOL.md) for display messages and
[wireless transport](../libraries/M5EspNowLink/README.md) for framing and recovery.
All eight IDs are supported. This board is **kart 3** by owner assignment; Eamon remains
kart 2 and kart 1 is the older development kart. Do not assign a new ID based on display type.
PIT OK means a recent pit beacon was heard; it does not prove the pit received this kart.
Both display types use the same pit. Local display refresh targets 5 Hz; fleet updates remain
at the configured LoRa rate (currently 2 Hz direct / 1 Hz with a repeater). No physical
eight-kart UART or RF load test is claimed. Current Heltec `self` telemetry arrives at 2 Hz (500 ms);
5 Hz is the screen redraw rate, not a promise of 5 new telemetry samples per second.

Neither an SD card nor a base station is required for own VESC telemetry or the live GPS map
of directly heard peers. A peer must transmit a valid GPS fix to appear. Central pit monitoring,
commands and pit-managed race features require the base station. These describe the design;
they are not a claim that this assembly has passed physical testing.

## What the display does

- DASH: GPS MPH, pack volts, battery watts, motor/battery amps, ESC temperature, actual mode,
  VESC/link status, fault code, STOP/SLOW state and Heltec-reported speed calibration.
- MAP: own kart plus up to seven other directly/repeater-heard kart positions, labeled by ID;
  own kart gets a white ring. North up, automatic fit, optional offline course outline.
  FRESH ONLY shows fresh positions. STALE TOO shows hollow last-known dots for at most 15 s.
  Missing GPS is unavailable, never an invented position at (0,0). This is not geofencing.
- On the later write-capable wired build, hold ECO/NORMAL/SPORT for 650 ms to request.
  Both initial read-only targets keep these controls unavailable. Pending, rejected, unavailable and unknown
  outcomes stay distinct from confirmed mode. Buttons use the Heltec's current cap definitions;
  the M5 does not duplicate its speed calibration or current scales. No mode is selected on boot.
- Driver mode requests cannot release pit SLOW, STOP or race grid hold. The Heltec rejects an
  M5 selection while stopped, holding the grid, busy writing, uncommissioned, OTA-active or
  baseline-suspect; it does not remember that selection for later.
- No wheel-speed estimate is fabricated without GPS. No motor temperature is displayed:
  the motors have no temperature sensors wired. `M5_BEGINNER_MODE` hides the driver fault code,
  leaving VESC protection, telemetry and pit reporting intact.

No aerial maps, race-entry filter (not present in the local telemetry contract), game zones,
FREEPLAY, boost actions, lap counting, sounds or Wi-Fi map sync yet. The wireless Core2 build
has its own explicit [maintenance/OTA window](#core2-maintenance-and-ota); the Heltec's separate
Wi-Fi OTA path remains upstream. Neither source support nor a saved password proves that an
OTA transfer has completed on this assembly.

## Wireless option: no jumper wires

Use **`m5-espnow` + `kart-m5-espnow-readonly`** for the local Core2-to-Heltec link. Each board
needs power, but no Grove/UART jumper wires or shared ground wire are required. The Heltec
continues to own VESC BLE, GPS and LoRa; the base station connection stays on LoRa.

The installed `kart-m5-espnow-readonly` checkpoint disables every VESC write. The separate
**`kart-m5-espnow`** target enables M5 mode requests and the full existing base/pit/USB/game
command implementation, as requested on November 10. This is a build capability, not evidence
of deployment. It requires fresh matched identity, a validated atomic baseline record, and a
recent current-session configuration read before motor-command state changes or writes.
Unchanged temporary-command fields come from that recent read; no saved configuration is written.
The baseline record cannot import the older split-key cache. Reconnects stay read-only.

This control target polls motor configuration every 500 ms and refuses a snapshot older than
1000 ms; BLE/LoRa performance at that rate still needs hardware measurement. This bounds snapshot
age but is not atomic against simultaneous external VESC Tool edits. STOP ramps never increase
current allowance, and pending writes/ramp steps become unknown on a controller-session change.
Actual M5/base command acceptance and controller tune alignment remain commissioning work.

Pairing is local USB provisioning, not over-the-air discovery. The helper generates independent
random 16-byte LMK and PMK keys, saves a private recovery record before provisioning, then writes
one validated atomic NVS pairing record on each board and reboots both. These are separate
per-board writes, so retain the recovery record if setup stops partway. Keys are never printed
or committed; the record stays in ignored `firmware/build/bench-private/` with restricted
permissions. Existing pairings are not silently replaced.

The Heltec keeps its existing Wi-Fi station channel and OTA connection. During normal display
operation, Core2 searches channels 1–11 for its authenticated Heltec without joining an access
point. Only an explicitly enabled maintenance window joins the Core2's saved Wi-Fi network.
The access point then owns its radio channel, which can temporarily interrupt ESP-NOW if the
Heltec is on a different channel. Disabling maintenance resumes channel search. Reacquisition
can take several seconds; radio coexistence, range and recovery need physical validation.

## Wired option (verify on the actual boards before connecting)

The existing **`m5` + `kart-m5-readonly`** UART path remains available. The wiring below is
only for that option; skip it when using ESP-NOW.

Use the Core2's exposed **PORT.A / Grove** (G32/G33), not the USB connector. GPIO numbers are
for Core2 v1.3 and Heltec HTIT-WB32LAF V4.3; check the exact unit and connector orientation.

| Connection | Core2 | Heltec |
| --- | --- | --- |
| Telemetry receive | G33 (white Grove signal) RX | G47 TX |
| Mode request transmit | G32 (yellow Grove signal) TX | G48 RX |
| Ground | GND (black) | GND |
| Power | Regulated supply to Core2 | Independently adequate regulated supply to Heltec |

UART signals are **3.3 V logic**, 230400 baud, 8N1. For the initial USB-powered bench setup, leave the red 5 V wire disconnected and insulated.
The Heltec pads labeled TX/RX are GPIO43/44; use the pads marked **47/48** for this link.
Do not tie independently powered 5 V outputs together or feed a signal pin from 5 V. The Heltec
must remain powered when the screen loses power. Power budgeting/backfeed and connector pinout
are unverified on this assembly. The earlier Pi-powered Heltec had brownouts; a display's
auxiliary power output is not assumed to support the Heltec's transmit peaks.

Heltec UART2 pins 47/48 are free in the BLE build. `GK_M5_UART` plus `VESC_TRANSPORT_UART` is a
compile-time error: those builds would contend for UART2. USB-C remains available for the
Heltec's existing console/provisioning. GPS UART1 and LoRa pins remain unchanged.

References: [Core2 pin map](https://docs.m5stack.com/en/core/Core2_v1.3),
[Heltec V4](https://heltec.org/project/wifi-lora-32-v4/), existing `kart-heltec-v4/config.h`.

## Build

Same Arduino ESP32 core as Eamon: **esp32:esp32 3.3.8**. Add these pinned display dependencies:

```sh
arduino-cli lib install 'M5Unified@0.2.29' 'M5GFX@0.2.36' 'ArduinoJson@7.4.3'
cd firmware
./build.sh m5                  # real UART display, no BLE or VESC library
./build.sh m5-demo             # standalone synthetic screen data; UART not initialized
./build.sh kart-m5-readonly    # companion Heltec: UART enabled, ALL VESC writes disabled
./build.sh kart-m5             # companion Heltec: guarded mode requests, existing pit commands
./build.sh m5-espnow            # Core2 encrypted wireless display
./build.sh kart-m5-espnow-readonly # companion Heltec: ESP-NOW, ALL VESC writes disabled
./build.sh kart-m5-espnow          # M5 modes + full existing base/game controls; commission separately
```

Other Heltec dependencies remain those in [firmware README](../README.md).
M5 FQBN is `esp32:esp32:m5stack_core2`; this is not a CoreS3 or generic ESP32 image.
Build output stays under ignored `firmware/build/`. Never commit binaries or credentials.

Upload is a separate hardware step: `./build.sh <target> upload <explicit-device-port>`.
First capture/retain each board's existing image and commissioning values for rollback. No flash,
VESC settings write, detection or motor test is part of the build/test commands above.

After installing both wireless targets, confirm the Heltec's saved ID is **3** and
`writes:false`. With both explicit USB ports connected, run from the repository root
(Python with `pyserial` installed; replace the two example port names):

```sh
python3 tools/m5/pair_espnow.py \
  --core2-port /dev/cu.CORE2_PORT \
  --heltec-port /dev/cu.HELTEC_PORT \
  --kart-id 3
```

The ID argument verifies the intended kart; it does not assign an ID. This command writes
pairing NVS and reboots both boards, so run it while parked with the VESC off. Afterward,
USB `espnow status` on each board should show the intended peer and eventually `linked:true`;
Core2 `status` should show `transport:"espnow"` and live kart-3 telemetry. Pairing readback
alone does not establish a working radio link. USB provisioning cannot be forwarded over
ESP-NOW. Keep the VESC off until the display pair is ready for the first read-only VESC test.

## Core2 maintenance and OTA

Available in **`m5-espnow` only**. Updates use ordinary Wi-Fi and the Core2's own hostname,
**`gokart-display-3.local`**, not the Heltec's `gokart-3.local`, LoRa, or the pit server.
No SD card is needed. First install the maintenance-capable image over USB; subsequent
application updates can use the password-protected OTA uploader.

Maintenance is **inactive after every boot**, including after an update. Saved credentials do
not start Wi-Fi or OTA. Hold the dashboard's **top status bar for 1.8 seconds** to open DISPLAY
UPDATES, then tap **ENABLE UPDATES**. The USB equivalent is `ota on`. This starts a ten-minute
window, including the time spent joining Wi-Fi. Repeating `ota on` does not extend it. The screen
shows the hostname, readiness, remaining time and upload progress. Returning to the dashboard
does not close the window; use **DISABLE UPDATES**, USB `ota off`, or let it expire.

While maintenance is active, the Core2 sends **no driver mode requests**. It follows the access
point's Wi-Fi channel and pauses its ESP-NOW channel search, so live display data may pause.
During the actual firmware transfer, the updater blocks normal display telemetry processing;
progress is drawn from the update callbacks. The Heltec continues to own VESC BLE and LoRa.
Maintenance expiry does not interrupt an authenticated flash transfer already in progress;
success restarts the Core2, and normal ESP-NOW discovery resumes with maintenance off.

Provision through the **Core2's physical USB console**, with maintenance off. The command is
`ota config ` followed by one JSON object with exactly these four fields (example values only):

```text
ota config {"ssid":"YOUR_WIFI_SSID","wifi_password":"YOUR_WIFI_PASSWORD","ota_password":"REPLACE_WITH_UNIQUE_12_TO_64_CHAR_SECRET","hostname":"gokart-display-3"}
```

`ssid` is 1–32 bytes, `wifi_password` is 0–64 bytes, and `ota_password` is 12–64 bytes.
`hostname` is 1–31 letters/digits/hyphens without leading/trailing hyphens; omit `.local` here.
The JSON is limited to 300 bytes. One NVS record stores the validated configuration. Neither
credentials nor configuration commands are accepted over ESP-NOW, and status output omits
SSID/passwords. `ota status` reports `configured`, `active`, `wifi`, `ready`, `progress`,
`remaining_ms`, hostname and any error. Wait for `ready:true` before uploading.

Keep a private JSON file containing the same `ota_password` under ignored
`firmware/build/bench-private/` with file permissions `0600` and a private parent directory.
It may also contain the other provisioning fields. Do not put real credentials into shared
terminal logs, source files or Git. From the repository root:

```sh
bash firmware/build.sh m5-espnow
python3 tools/m5/ota_core2.py \
  --host gokart-display-3.local \
  --image firmware/build/m5-core2-m5-espnow/m5-core2.ino.bin \
  --credentials firmware/build/bench-private/core2-ota-private.json \
  --espota /path/to/esp32/3.3.8/tools/espota.py
```

Replace the credentials and installed-core paths with the actual private file and official
`espota.py` from ESP32 Arduino **3.3.8**. Use an application `.ino.bin`, never a merged-flash,
bootloader or Heltec image. The helper snapshots the image and prints its exact SHA-256, passes
the password through a private pipe rather than argv, requires password authentication plus an
explicit success acknowledgement, and enforces a maximum 120-second upload deadline. It sends
no VESC commands. A timeout or uncertain result requires status verification before any retry.

A successful uploader response must be followed by Core2 reboot/status verification, maintenance
`active:false`, renewed ESP-NOW telemetry, and confirmation that the Heltec still reports
`writes:false`. Record the image hash and observed results in the handoff. The ordered checks
are in [BRINGUP](BRINGUP.md#core2-ota-check), and helper details are in the [tools README](../../tools/README.md#core2-ota).

## Course outline

An SD card is optional and used only for a local course outline. The dashboard and live
own/peer GPS map work without one; no map image or SD card is needed to begin telemetry testing.

Draw or record the course with the existing pit editor, then export its `zones.json`:

```sh
python3 tools/m5/export_course.py --zones pit/server/map/zones.json \
  --name 'Shop test course' --out /tmp/m5-course.json
```

Copy the resulting file to a FAT32 microSD card at `/gokart/course.json`, insert into the Core2,
and restart the display. The exporter refuses an existing output and invalid or >128-point
tracks; simplify a large route in the pit first. It exports the track only, no game effects.
The repository's shop route is a demonstration, not a surveyed Manresa course.

Without a valid file, the map fits heard GPS positions and says GPS only. A malformed/oversize
file is ignored. Removing/rebooting the display never writes to the VESC. Course files contain
only geographic geometry, never Wi-Fi credentials or motor limits.

## Reliability and commissioning

- New data replaces stale data; reconnection never sends a mode. No stored desired mode or
  command resend queue exists on the M5. An interrupted request becomes outcome unknown.
- On the wired mode-capable path, each request carries a CRC16 and a single-use one-second token from this Heltec boot.
  Tokens are invalidated on readiness/link-session changes. This is accidental corruption/replay
  protection on a physical wire, **not authentication** and not a heartbeat driving lease.
- The adapter accepts only mode requests. It cannot forward arbitrary console commands, change
  credentials, reset boards, set power/current, start/stop the kart or stream motor commands.
- In addition to upstream gates, M5 requests require a pinned VESC UUID and fresh linked state.
  Existing controller limits and the upstream acknowledgement/readback path remain authoritative.
- Whole JSON lines are dropped if the UART TX buffer has insufficient space. Input work is
  bounded, oversized/partial lines are discarded. Blocking a display must not stall radio service.
- ESP-NOW uses encrypted unicast plus authenticated framing for the provisioned peer, bounded
  queues and expiring fragments. It has no plaintext fallback or command replay. Link loss
  changes display freshness only; it must not change VESC state. See the transport README for
  buffer and recovery limits. Both read-only builds keep pit and driver VESC writes disabled.
- Eamon's existing write/OTA policy differs from Colin's older integration safeguards. This
  branch does not merge PR #4 or declare those outstanding integration questions resolved.

The [first-session guide](BRINGUP.md) has pairing/wiring steps, expected screens, troubleshooting
and a results checklist for the 2026-11-10 bench. The earlier USB uploads and touch diagnostic
are complete; continue the final display and end-to-end checks without treating them as passed:

1. Retain the completed private rollback images and verify independent board power.
2. Install the selected display/companion pair and confirm the enlarged DASH/MAP controls.
   For ESP-NOW, use the USB pairing helper; for UART, connect the three signal/ground wires.
3. Confirm kart 3 reaches the display while the VESC is off, then run the first read-only VESC
   telemetry test. Compare volts/current/ESC values, GPS fix, transport drops and simultaneous
   USB telemetry. No SD card or base is needed for this step. When the
   base is available, separately confirm the existing pit sees kart 3 and can ping it.
4. Test outdoor GPS positions with another kart, course loading, 1/2 Hz and a full eight-kart
   simulated load on the chosen local transport. Test UART disconnect/reconnect or ESP-NOW
   loss/channel recovery, reboot only the display, and confirm no VESC configuration writes.
   Measure actual refresh/latency alongside BLE and LoRa.
5. Only after reviewing/commissioning the controller, use `kart-m5-espnow` (wireless) or `kart-m5` (wired) for supervised mode readback
   checks. Verify ECO/NORMAL/SPORT, pit SLOW remains through a driver selection, STOP/GRID rejects
   selections, and pending requests are not replayed after cable/BLE loss. No unattended motor test.

## Verification

Host tests exercise the real shared telemetry encoder, JSON parser, expiry/CRC/single-use gate,
request outcomes, boot/link loss, timestamp rollover, map freshness and course export. A second
native test simulates 600 seconds of eight-kart traffic, losses, corrupt frames and restart
recovery; old GPS samples keep their source age instead of becoming fresh upon arrival.
The printed UART utilization is ideal serialization arithmetic, not measured hardware throughput.
These tests need C++17 plus ArduinoJson's installed header directory:

```sh
export ARDUINOJSON_DIR='/path/to/Arduino/libraries/ArduinoJson/src'
python3 -I firmware/tests/test_m5.py
python3 -I firmware/tests/test_m5_espnow.py
python3 -I firmware/tests/test_m5_ota.py  # fake uploader; no hardware/network
tools/run_tests.sh                 # all existing suites plus M5 tests
```

See [handoff](../../HANDOFF.md) for current build/test results and hardware status.


## Exact ESP-NOW channel alignment (prepared source, 2026-11-10)

Both new companion images are required before mode testing. Authenticated telemetry received on
an adjacent Wi-Fi channel no longer enables controls: the pair exchanges channel/challenge/boot
proof and the Core2 follows the Heltec's actual channel. Status separates `channel`, `rx_channel`,
`peer_channel` and `channel_aligned`. Maintenance clears control readiness until fresh proof after
exit. Old/new firmware pairs still show telemetry but intentionally keep mode controls unavailable.
See the [transport contract](../libraries/M5EspNowLink/README.md#channel-alignment-protocol).
All nine affected targets compile; matching-channel recovery, AP channel changes, OTA and mode
acceptance on the new pair still need supervised bench verification. The previously verified
read-only pair remains installed; source build success is not hardware deployment.
