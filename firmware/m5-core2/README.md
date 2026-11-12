# M5 Core2 v1.5

**November 12 candidate, not installed:** [Claude handoff](../../docs/CLAUDE_HANDOFF.md). Full-screen map, compact MPH/pack-voltage HUD, five-second startup credits and page-button hold for updates.

**New source, not installed:** [Hunter-style native pages and no-output player rehearsal](../../docs/m5-offline-rehearsal.md). Real JOIN/download/native FIRE are now implemented for `m5-espnow`; see [player integration](../../docs/m5-player-mode.md). Physical acceptance is pending. The standalone `m5-demo` uses RAM-only simulated data and no UART/ESP-NOW command transport.

Branch **`v1.5/m5-core2`** now integrates Eamon source through `c21baf8` (kart0.3.3),
preserving paired M5 safeguards and adding the native player path. The later separate
`core2-items`/Pi-fastboot commits remain outside this candidate. Owner confirmed **Core2 v1.3 /
K010-V13**. Existing kart3 installed evidence below remains the earlier `4a582f0` applications.


**Kart 3 is commissioned for M5 mode selection as of 2026-11-10.** The owner selected ECO,
NORMAL and SPORT on the Core2; each request received VESC readback confirmation. Wired throttle
was exercised with the wheels lifted, and sampled VESC faults remained zero. The owner reports
the setup works. This does not establish pit motor-command acceptance, track speed, sustained
loaded operation, RF range or eight-kart acceptance.

| Confirmed mode | Current scale | Forward ERPM cap read back |
| --- | ---: | ---: |
| ECO | 0.50 | 21661 |
| NORMAL | 0.75 | 36102 |
| SPORT | 1.00 | 150000 |

These are **kart 3's observed settings**, not values to clone into another controller. Its
physically verified VESC is BLE **`f7:bd:23:cc:62:0e`**, UUID **`37004e000951343037353739`**,
firmware **6.02**, hardware **75_300_R2**. Heltec reported `writes:true`, `id_ok:true`,
`limits_ok:true`, baseline source `read`; Core2 reported `mode_ready:true`. ESP-NOW driver,
received and peer channels all matched **6**, with alignment confirmed.

| Installed application | Source | SHA-256 |
| --- | --- | --- |
| Heltec `kart-m5-espnow` | `4a582f0` | `11e556e8d525632916f9ef05ac12e8f3f4346ed70f0adfbd6a3ecc3aa08821f2` |
| Core2 `m5-espnow` | `4a582f0` | `996c4387cb51a16286e89760ac035aa421bfbede608a8f56092f2a319cec9b0a` |

Both segmented USB uploads were verified and preserved NVS. Full rollback images, pairing keys
and OTA credentials remain private. A later Core2 radio-busy touch-feedback patch was built
(SHA-256 `35162e477bf917464b88840378913ced7ecab43bed83b333810b4cfba6901df1`) but **was not
installed**; the known working pair above remains in service. See the
[mode commissioning evidence](../../hardware/m5/2026-11-10-kart3/mode-commissioning/README.md).

Core2 authenticated Wi-Fi OTA was verified at the earlier telemetry checkpoint: the application
uploaded, credentials survived restart, maintenance returned to off and ESP-NOW telemetry
recovered. DASH/MAP touch is also owner-confirmed. That OTA result remains valid historical
acceptance; the currently installed applications above were uploaded over USB.
[Earlier evidence](../../hardware/m5/2026-11-10-kart3/README.md) and
[handoff](../../HANDOFF.md) retain the chronology.

The next two M5 karts are **4 and 5**; **1 and 2 remain Eamon's test karts**. Follow [repeat commissioning](BRINGUP.md#build-the-next-two-m5-karts). Each new unit starts
with the read-only Heltec target and its own physical VESC identity, pairing and calibration.
Do not copy kart 3's NVS, VESC tune, identity pins or secrets.

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
and touch, plus native inventory/local game logic and host course downloads over ESP-NOW.
See [player integration](../../docs/m5-player-mode.md) for host deployment and acceptance. VESC supervision stays on Heltec.
The original M5 BLE client/profile writer is not included. It must be replaced
by this display image before using this topology. No two devices should connect to the same
VESC. The motor's wired controls and protection stay with the VESC.

The M5 targets are **opt-in**. Integration now includes Eamon's kart0.2.7 and 46/47/54-byte
radio support; an idle kart still sends 47 bytes. Native player uses session/attack metadata.
Active multiplayer requires updated base/repeater0.2.2; M5 game UI and physical game-command
acceptance remain separate from the verified driver mode checks. Normal `kart`, `kart-uart`,
base, repeater and Pi builds retain existing behavior. Existing telemetry/command structs, IDs, frequencies and slots remain unchanged. Optional
14-byte COURSE identities replace one host telemetry slot every2s; older nodes ignore them. Both local transports carry the existing `self` and `fleet` JSON plus display-only
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

The new [no-SD follow map](COURSE_MAP.md) is source/test work awaiting a separate display
deployment. It does not change the installed acceptance checkpoint above.

Neither an SD card nor a base station is required for own VESC telemetry or the live GPS map
of directly heard peers. A peer must transmit a valid GPS fix to appear. Central pit monitoring,
commands and pit-managed race features require the base station. Their physical acceptance
remains separate from kart 3's completed telemetry and driver-mode checks.

## What the display does

- DASH: GPS MPH, pack volts, battery watts, motor/battery amps, ESC temperature, actual mode,
  VESC/link status, fault code and STOP/SLOW state. Speed calibration remains Heltec-owned
  metadata; the compact display does not show its calibration factor.
- MAP: own kart plus up to seven other directly/repeater-heard kart positions, labeled by ID;
  own kart gets an amber ring. North up, fixed 70 m own-follow view, optional internally stored or SD course outline.
  Only fresh markers inside the current view are drawn; distant peers do not zoom the map out.
  DASH opens telemetry/modes. FIRE is enabled only with a live confirmed native session,
  eligible inventory, fresh generation/controller state and (for shells) an in-range target.
  Missing GPS is unavailable, never an invented position at (0,0). This is not geofencing.
- Hold ECO/NORMAL/SPORT for **650 ms** to request a mode on a commissioned write-capable
  companion; release before trying again. This works over ESP-NOW on kart 3 and is also supported by UART.
  Both initial read-only Heltec targets keep these controls unavailable. Pending, rejected,
  unavailable and unknown outcomes stay distinct from confirmed mode. Buttons use the Heltec's current cap definitions;
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
Wi-Fi OTA path remains upstream. Each new pair needs its own recorded OTA transfer and recovery;
source support or a saved password alone does not establish acceptance.

## Wireless option: no jumper wires

For a new kart, begin with **`m5-espnow` + `kart-m5-espnow-readonly`**. Commissioned kart 3
uses **`m5-espnow` + `kart-m5-espnow`** for the local Core2-to-Heltec link. Each board
needs power, but no Grove/UART jumper wires or shared ground wire are required. The Heltec
continues to own VESC BLE, GPS and LoRa; the base station connection stays on LoRa.

`kart-m5-espnow-readonly` disables every VESC write and remains the initial inspection/rollback
target. **`kart-m5-espnow`**, now installed on kart 3, enables M5 mode requests and the full
existing base/pit/USB/game command implementation requested on November 10. M5 mode acceptance
is verified; pit MODE/STOP/START/SLOW/BOOST/RACE and game acceptance on this assembly is pending.
Only periodic pit `rate 1` commands were observed during this commissioning session. The control
target requires fresh matched identity, a validated atomic baseline record, and a recent
current-session configuration read before motor-command state changes or writes.
Unchanged temporary-command fields come from that recent read; no saved configuration is written.
The baseline record cannot import the older split-key cache. Reconnects stay read-only.

This control target polls motor configuration every 500 ms and refuses a snapshot older than
1000 ms; BLE/LoRa performance at that rate still needs hardware measurement. This bounds snapshot
age but is not atomic against simultaneous external VESC Tool edits. STOP ramps never increase
current allowance, and pending writes/ramp steps become unknown on a controller-session change.
Kart 3's M5 mode readbacks passed. Its separately authorized, backed-up motor tune trial is
recorded in [tune evidence](../../hardware/vesc/kart3/2026-11-10/tune-applied-v1/README.md);
that persistent maintenance write is distinct from temporary supervisory profiles. Do not rerun
that trial or import it wholesale into another kart. Base-command and loaded-driving acceptance remain open.

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

For a **new pair**, install the read-only companion, provision its confirmed fleet ID and
verify `writes:false`. The next two IDs are **4 and 5**; **do not reuse 1, 2 or 3**. With both
explicit USB ports connected, run from the repository root (Python with `pyserial` installed;
replace the two port names and `N` with that unit's confirmed ID):

```sh
python3 tools/m5/pair_espnow.py \
  --core2-port /dev/cu.CORE2_PORT \
  --heltec-port /dev/cu.HELTEC_PORT \
  --kart-id N
```

The ID argument verifies the intended kart; it does not assign an ID. This command writes
pairing NVS and reboots both boards, so run it while parked with the VESC off. Afterward,
USB `espnow status` on each board should show the intended peer and eventually `linked:true`;
Core2 `status` should show `transport:"espnow"` and that unit's live kart telemetry. Pairing readback
alone does not establish a working radio link. USB provisioning cannot be forwarded over
ESP-NOW. Keep the VESC off until the display pair is ready for the first read-only VESC test.

## Core2 maintenance and OTA

Available in **`m5-espnow` only**. Updates use ordinary Wi-Fi and the Core2's own hostname,
**`gokart-display-3.local`**, not the Heltec's `gokart-3.local`, LoRa, or the pit server.
No SD card is needed. First install the maintenance-capable image over USB; subsequent
application updates can use the password-protected OTA uploader. The hostname/examples below
belong to kart 3. Each new kart needs its own `gokart-display-N` hostname, private OTA password
and recovery record; do not clone the existing NVS or password file.

Maintenance is **inactive after every boot**, including after an update. Saved credentials do
not start Wi-Fi or OTA. Hold the dashboard's **upper-right DASH/MAP page button for 1.8 seconds** to open DISPLAY
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
`active:false`, renewed ESP-NOW telemetry and unchanged Heltec identity/write capability:
`writes:false` for a new read-only unit, or the expected `writes:true` for commissioned kart 3.
Do not select a mode as part of an OTA recovery check. Record the image hash and observed results
in the handoff. The ordered checks are in [BRINGUP](BRINGUP.md#core2-ota-check), and helper details are in the [tools README](../../tools/README.md#core2-ota).

## Course outline

The new Core2 source starts on a close-follow map and stores a course internally when
provisioned over USB; **this change is not yet deployed or physically accepted**. No SD card
or Pi is required. The map follows the own fresh fix at 70 m vertical span; distant karts do
not change the zoom. DASH retains the existing telemetry/mode controls and the page-button
hold opens OTA. This legacy outline upload remains available; the new native player workflow
downloads a full host game package. See the player integration above for live JOIN/FIRE.

Follow [course provisioning, diagnostics and acceptance](COURSE_MAP.md) to export the pit's
track, validate it offline, and install it on the intended Core2. Internal storage is preferred;
the existing FAT32 SD `/gokart/course.json` remains an optional boot-time fallback. No valid
course is removed by a malformed upload. The repository shop outline is a demonstration,
not a surveyed Manresa course. With no course, fresh GPS still draws the own marker.

## Reliability and commissioning

- New data replaces stale data; reconnection never sends a mode. No stored desired mode or
  command resend queue exists on the M5. An interrupted request becomes outcome unknown.
- Both local transports use CRC16 mode requests and a single-use one-second token from the
  Heltec boot; readiness/link-session changes invalidate tokens. UART alone provides corruption/replay
  checks, not authentication. ESP-NOW additionally authenticates the provisioned peer and exact channel.
  Neither transport is a heartbeat driving lease.
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

The [commissioning guide](BRINGUP.md) separates the passed kart-3 checkpoint from first-unit
checks for the next two karts. Keep the installed working pair unchanged unless deliberately
updating it. Outstanding work includes outdoor GPS/course/peer checks, range and recovery under
load, a prolonged soak, eight-kart RF traffic, pit motor-command acceptance and driving validation.
Pit SLOW persistence through driver modes and STOP/GRID rejection require their own supervised
acceptance; the three successful mode readbacks do not establish those interactions.

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

## Exact ESP-NOW channel alignment (installed on kart 3, 2026-11-10)

The installed `4a582f0` pair exchanges authenticated channel/challenge/boot proof before enabling
mode requests. Kart 3 reported `channel:6`, `rx_channel:6`, `peer_channel:6` and alignment true;
all three driver mode requests subsequently reached the VESC and were read back. Adjacent-channel
telemetry alone does not enable controls. Maintenance clears readiness until fresh proof after exit.
Old/new firmware pairs still show telemetry but intentionally keep mode controls unavailable.

See the [transport contract](../libraries/M5EspNowLink/README.md#channel-alignment-protocol).
This checkpoint proves the paired channel and mode path on the bench, not AP channel-change
recovery, RF range or prolonged coexistence. Those remain distinct physical acceptance checks.
