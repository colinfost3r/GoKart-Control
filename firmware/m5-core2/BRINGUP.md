# Core2 v1.3 + Heltec: commissioning and repeat builds

Use branch `v1.5/m5-core2` and [the M5 README](README.md). **Kart 3 has passed live telemetry,
DASH/MAP touch, an earlier authenticated Core2 OTA upload/recovery, and supervised M5 mode
selection on 2026-11-10.** The current `4a582f0` Heltec `kart-m5-espnow` and Core2 `m5-espnow`
applications were verified after segmented USB upload with NVS preserved. The README records
both installed hashes. A later radio-busy feedback patch was built but **not installed**.

The owner selected ECO/NORMAL/SPORT with **650 ms holds**; readback confirmed scales
**0.50 / 0.75 / 1.00** and forward caps **21661 / 36102 / 150000 ERPM**. Wired throttle was
exercised with wheels lifted; sampled VESC faults stayed zero. Driver/received/peer channels
all matched **6**, Heltec reported `writes:true`, `id_ok:true`, `limits_ok:true`, baseline `read`,
and Core2 reported `mode_ready:true`. See the
[mode commissioning record](../../hardware/m5/2026-11-10-kart3/mode-commissioning/README.md).
Pit MODE/STOP/START/SLOW/BOOST/RACE/game physical acceptance, loaded driving and fleet/range tests
remain pending; a received `rate 1` command does not establish motor-command acceptance.

**The next two M5 karts are not commissioned and their IDs are unassigned.** For each, begin
with `m5-demo`, then `m5-espnow` + `kart-m5-espnow-readonly` (or `m5` + `kart-m5-readonly` for UART).
Both initial Heltec targets keep every VESC write disabled. Use the repeat-build checklist below;
do not downgrade/re-pair the working kart 3 simply to repeat first-unit steps.

## Bring to the bench

- M5Stack **Core2 v1.3 / K010-V13**, Heltec **WiFi LoRa 32 V4.3** with its GPS attached.
- Keep the LoRa antenna attached. ESP-NOW needs **no jumper wires** between boards. For the
  optional UART path only, use a Grove/HY2.0 cable broken out securely to the Heltec header.
- Two known-good USB-C data cables and adequate USB power, one per board. Label each cable
  so upload ports cannot be confused. For UART, the red Grove lead stays disconnected and insulated.
- Optional FAT32 microSD for a local course outline. Dashboard telemetry and the live GPS/peer
  map need no SD card. GPS map checks need sky view; peer checks also need another kart
  transmitting. A USB-only bench inside may show no GPS fix.
- Optional access to the existing pit dashboard to confirm the intended kart is received.
  Kart 3 is the commissioned M5 unit; Eamon remains kart 2 and kart 1 is the older development
  kart. Coordinate new unique IDs before provisioning. A display does not get a second fleet ID.

The base station is optional for own VESC telemetry and directly received peer positions.
Central pit monitoring, commands and pit-managed race features need the base station. Kart 3's
own telemetry and M5 modes have passed; record each new unit's acceptance separately below.

## Choose the local link

For a new unit's wireless telemetry checkpoint, use `m5-espnow` and `kart-m5-espnow-readonly`,
power each board by USB and follow the pairing step below. That companion target has a
compile-time read-only guard. The separately commissioned `kart-m5-espnow` control target,
currently installed on kart 3, enables M5 modes and existing base/USB/game controls.

For the retained UART option, use `m5` and `kart-m5-readonly` and wire as follows with both
boards off. This table does not apply to ESP-NOW.

| Standard M5 cable | Core2 PORT.A | Heltec header |
| --- | --- | --- |
| Yellow | GPIO32 / TX in this firmware | GPIO48 / RX |
| White | GPIO33 / RX in this firmware | GPIO47 / TX |
| Black | GND | GND |
| Red | 5 V | **Unconnected and insulated** |

The connector is labeled I2C but the firmware assigns its two signals to **UART, 230400 baud,
8N1, 3.3 V logic**. Use Heltec pads marked **47/48**, not the pads simply marked TX/RX
(GPIO43/44). Verify labels if a cable uses different colors. Power each board by its own USB
connection for this first session; do not join their 5 V power outputs.

Official references: [Core2 v1.3 pin map](https://docs.m5stack.com/en/core/Core2_v1.3),
[Heltec V4 pin map](https://heltec.org/project/wifi-lora-32-v4/).
Internal Core2 touch/PMU/RTC/IMU I2C is on GPIO21/22, separate from these Port A signals.
Actual assembly power, signal integrity and behavior with either device off remain to be tested.

## Prepare without touching hardware

From the repository root, with dependencies from the README installed:

```sh
export ARDUINOJSON_DIR='/path/to/Arduino/libraries/ArduinoJson/src'
tools/run_tests.sh
bash firmware/build.sh m5-demo
bash firmware/build.sh m5
bash firmware/build.sh kart-m5-readonly
bash firmware/build.sh m5-espnow
bash firmware/build.sh kart-m5-espnow-readonly
python3 tools/m5/export_course.py --zones pit/server/map/zones.json \
  --name 'Shop bench outline' --out firmware/build/m5-bringup/course.json
```

These commands build, run host simulations and export a course; none open a device port or
flash a board. The exporter refuses to overwrite an existing file. The sample is the pit's
shop track, **not a surveyed Manresa course**. If testing the optional course outline, copy
the exported file to `/gokart/course.json` on the SD card. Skip the export and SD steps for
dashboard telemetry and the GPS-only map.

## Verify kart 3's controller identity

Eamon's [kart 0.2.7 change (`fc7e610`)](https://github.com/colinfost3r/GoKart-Control/commit/fc7e610457b59bc2ee7c580c771573c9e03d16d0)
identifies BLE address `d8:94:35:be:e5:32` and VESC UUID `2c004c000951343037353739` as
**kart 2's** controller. The earlier kart-3 setup reused that BLE address and could occupy
kart 2's single BLE connection even while refusing writes. These are reference values for
avoiding that conflict, **not kart-3 provisioning values**.

Kart 3's corrected physical identity is now verified: BLE **`f7:bd:23:cc:62:0e`**, VESC UUID
**`37004e000951343037353739`**, firmware **6.02**, hardware **75_300_R2**. Its pins survived
accessory restarts. These values are **only for kart 3**, never provisioning defaults for a new kart.

For each new unit, identify its physical VESC and independently read its BLE address and UUID.
Coordinate with Eamon so one intended Heltec owns each controller. Never adopt the first nearby
VESC or copy historical pins. `id_ok:true` alone is insufficient with an absent UUID pin; require a
nonempty `uuid_pin` matching `vesc_uuid` and the physical ownership record. The merged firmware
releases a mismatched UUID and rejects that address until re-pinned or rebooted, but cannot
protect two units deliberately provisioned with the same correct MAC and UUID.

For the initial telemetry check require the new unit's correct identity **and `writes:false`**.
Preserve all Hall/motor electrical/pedal calibration and the complete application configuration.
Kart 3's latest owner clarification is throttle **ADC1**, reverse switch **RX**; the earlier TX
mismatch explanation is ruled out. Any remaining reverse symptom needs separate diagnosis;
this display commissioning procedure changes no input wiring or VESC application settings.

## Ordered physical checks

Before the first flash, identify both explicit serial ports and retain each board's previous
image and commissioning values for rollback. Flash backups may include Wi-Fi/OTA secrets;
keep them local under ignored `firmware/build/bench-private/`, never in Git or a public PR.
Record the source commit and target for each new image. Upload only after choosing the exact
board/port; build success alone does not establish that an image is installed.

For each new ESP-NOW pair, install the initial read-only targets, provision and verify its
confirmed unique kart ID with `writes:false`, then run this from the repository root using Python
with `pyserial` installed. Replace `N` with the assigned ID; the next two IDs are still unassigned:

```sh
python3 tools/m5/pair_espnow.py \
  --core2-port /dev/cu.CORE2_PORT \
  --heltec-port /dev/cu.HELTEC_PORT \
  --kart-id N
```

Replace both example ports with the identified devices. This provisions random private LMK/PMK
keys over USB, saves an atomic pairing record in each board's NVS, and reboots both. The helper
retains its private recovery file under ignored `firmware/build/bench-private/` before writing
either board; keep that file out of Git. It refuses existing pairings instead of replacing them.
The two board writes are not one transaction, so retain the file if setup is interrupted.
Check `espnow status` on both boards for the intended peer and `linked:true`; allow several
seconds for Core2's channel search. Pairing readback alone is not radio acceptance.

| Stage | Setup/action | Expected result |
| --- | --- | --- |
| 1. Display alone | Run `m5-demo`; Heltec link not needed | Screen says **DEMO / NO OUTPUT**. DASH/MAP tabs and FRESH ONLY/STALE TOO toggle respond; eight synthetic dots appear. Mode buttons send nothing. |
| 2. Local telemetry | Run the paired ESP-NOW targets, or the UART targets with three wires connected; begin with VESC off | Demo label disappears. Kart ID is the unit's assigned ID and Heltec status reaches the display; VESC is disconnected while off. DASH/MAP and map filter respond. Mode controls remain unavailable. No base station or SD card is required. |
| 2b. VESC telemetry | Complete the per-unit identity check above, then turn on its intended VESC for a read-only check | Electrical values match Heltec USB `self` telemetry; no throttle or motor command is sent. |
| 3. Identity/read-only | On Heltec USB console, request `status` | `writes:false`, `transport:"ble"`, intended `vescmac`/`vesc_uuid`, `id_ok:true` and `radio:true`. Before later mode testing, verify nonempty `uuid_pin` matches `vesc_uuid`; `id_ok` alone also allows address-only binding. No motor test or settings write is needed. |
| 4. GPS/map | Allow an outdoor fix; power another transmitting kart for the peer check; install optional course SD before starting display | Own numbered dot gets a white ring; a directly received peer with a valid fix appears without a base station or SD card. Course outline is visible if loaded. With no fix, GPS speed is `--`, not a fabricated zero/location. |
| 5. Shared pit (when available) | View the assigned kart in the existing pit dashboard | Pit receives that kart's live updates. M5 PIT OK means it heard a beacon, so confirm both directions separately. Record this stage as pending if no base is available; it does not block own telemetry/direct peer checks. |
| 6. Link loss | UART: interrupt/reconnect telemetry data. ESP-NOW: test radio loss/recovery and channel reacquisition. Also restart display alone | Own telemetry becomes lost after ~1.5 s, fresh map positions age out after ~3 s, optional stale dots vanish by ~15 s. Wireless reacquisition may take several seconds. Recovery sends no mode and VESC active settings stay unchanged. |
| 7. Sustained run | Leave telemetry running for 10 minutes; log boot messages and rates | No unexpected resets, repeated freezes or unexplained mode changes. Check both USB and display still work. This measures real hardware; host simulation is not a substitute. |

For the UART option, change wiring only with power removed. For live link-loss checks use a prepared switch or
secure removable signal connector so adjacent pins cannot be shorted. Keep the grounds joined.
Power-cycle only the display for that step, not the Heltec or the VESC.

The display redraws at **5 Hz**. The current Heltec `self` reports are **2 Hz** (500 ms);
fleet data follows the selected radio rate, normally 2 Hz direct or 1 Hz with the repeater.
Metadata also updates when its command token changes. Capture actual latency and drops rather
than expecting every redraw to contain a new sensor sample.

## Core2 OTA check

This is a separate parked maintenance check for **`m5-espnow`**, with no motor commands and no
SD card. On a new unit, keep the Heltec read-only. On commissioned kart 3, its write-capable
Heltec stays unchanged; an OTA recovery check sends no mode request. First install the
maintenance-capable Core2 application over USB and provision its four-field configuration using the [README procedure](README.md#core2-maintenance-and-ota).
Keep the matching `ota_password` in a private `0600` JSON file under ignored
`firmware/build/bench-private/`; never put the credentials in shared evidence.

1. Reboot Core2 and request USB `ota status`: credentials may be `configured:true`, but
   `active`, `ready` and `updating` must be false. Confirm ordinary ESP-NOW telemetry first.
2. Hold the **top status bar for 1.8 seconds** to open DISPLAY UPDATES, then tap ENABLE UPDATES;
   alternatively send Core2 USB `ota on`. Expect a ten-minute window and
   **`gokart-display-3.local`** on kart 3, or that new unit's unique provisioned hostname.
   Wait for `ota status` to report `ready:true`.
3. Run `tools/m5/ota_core2.py` with explicit `--host`, application `--image`, private
   `--credentials`, and official `--espota` paths as shown in the README. Preserve the printed
   SHA-256 and acknowledgement. The tool stops within 120 seconds; it never sends a VESC command.
4. Observe upload progress and the display restart. Read Core2 `status` and `ota status` after
   reboot: maintenance must be off. Confirm the expected installed build with the image/build
   evidence, not just the generic `m5-v1.5` status label.
5. Confirm reciprocal `espnow status` becomes linked again and fresh own/peer telemetry returns.
   Check the Heltec retains its intended write capability (`false` for initial read-only commissioning,
   `true` for commissioned kart 3), the correct VESC identity and unchanged active limits. Record
   transfer, reboot and recovery outcomes separately; neither uploader ACK nor host tests alone
   establishes these results.

Maintenance pins Core2 to its access point's Wi-Fi channel while ESP-NOW search is paused;
telemetry may temporarily disappear if the Heltec is on another channel. The actual flash
transfer also pauses normal telemetry parsing. Mode requests remain blocked throughout the
active window, including when BACK TO DASHBOARD is selected. DISABLE UPDATES or USB `ota off`
closes an idle window and resumes channel discovery; repeating `ota on` does not extend the
deadline. An authenticated transfer already in progress is allowed to finish before expiry.

For a timeout, authentication error or missing reboot, inspect status first and keep USB
recovery available; do not infer success or automatically repeat the upload. Actual hardware
OTA acceptance was **verified on kart 3 at the earlier telemetry checkpoint**, including authentication,
reboot, retained credentials, maintenance off and telemetry recovery. Repeat and record it for each
new unit; a previous kart's result does not commission another pair.

## Quick diagnosis

| Symptom | First checks |
| --- | --- |
| Display dark | Run standalone `m5-demo`; verify USB power, Core2 power button and correct Core2 target before debugging the Heltec wires. |
| Demo dots still shown | `m5-demo` is still installed. Use `m5` for UART or `m5-espnow` for wireless telemetry. |
| Tabs do not respond | The four-target diagnostic confirmed touch input in IRQ mode. Verify the new image has outlined 40-pixel tabs; inspect Core2 USB `status` for page, touch count and coordinates. Kart 3 DASH/MAP and 650 ms mode holds are owner-confirmed; test each new panel separately. |
| HELTEC DATA LOST over ESP-NOW | Correct wireless targets, both boards powered, reciprocal peer IDs and pairing on USB `espnow status`; allow channel search. Outside maintenance, Core2 does not join an access point; during maintenance its AP channel can temporarily interrupt telemetry. No jumper wires are needed. |
| HELTEC DATA LOST over UART | Common ground, white G33 to Heltec47, both boards powered, correct M5 UART companion target, 230400 baud. |
| VESC DISCONNECTED | Verify the unit's physical controller and both pins; the historical d8:94:35:be:e5:32 controller belongs to kart 2. Check VESC power and UUID-mismatch rejection. The M5 does not own BLE. |
| Electrical data works but no map/speed | GPS needs a valid fix. M5 v1.5 speed is GPS-derived; spinning wheels on a stationary stand will not show road speed. |
| Mode or pit motor controls unavailable | Expected with either read-only Heltec target. For a commissioned control pair, check `writes:true`, correct fresh UUID/configuration, baseline not suspect, maintenance off, `mode_ready:true`, and matching `channel`/`rx_channel`/`peer_channel` with alignment. Release and repeat the 650 ms hold if an attempt was unavailable; requests are never saved for later. |
| PIT LOST | Expected with no base station. When testing the pit, confirm base power, antenna and matching fleet/radio settings. Own VESC telemetry and direct peer positions do not require a pit beacon. |
| No other kart on map | Confirm another kart is transmitting with a valid GPS fix, antennas are attached and fleet/radio settings match. Neither a base station nor an SD card is required for direct peers. |
| Core2 OTA unavailable | Use `m5-espnow`, provision over USB, explicitly enable the window, and inspect `ota status`. Use that unit's display hostname; kart 3 uses `gokart-display-3.local`, distinct from Heltec `gokart-3.local`. No SD is required. |
| Course absent | FAT32, `/gokart/course.json`, schema1, 2–128 valid points, file <=24576 bytes; restart the display after inserting the card. |

## Record before calling it passed

- Date/operator, board revisions, source commit, targets and which image was actually flashed.
- Rollback image location (private), power arrangement, selected transport and a wiring photo if UART.
- For ESP-NOW: nonsecret peer identities, pairing readback, channel, link/drop counters and recovery
  time; never include LMK/PMK or the private recovery file in shared evidence.
- Kart ID, physically verified VESC ownership, actual BLE/UUID pins and expected write capability;
  `writes:false` for initial inspection, `writes:true` only at the control commissioning stage. Strip credentials.
- For Core2 OTA: application SHA-256, target hostname, authentication/ACK result, observed reboot,
  maintenance disabled after boot, and ESP-NOW telemetry recovery. Keep passwords out of evidence.
- Screen/touch, GPS/course, second kart and pit observations; mark unavailable checks pending.
- Measured report cadence, any resets/freezes, link-loss/recovery outcome and VESC active limits
  before/after. Retain local logs with timing if a problem occurs.

Then update HANDOFF.md with **observed** results. Keep driver mode confirmations separate from
pit STOP/SLOW/BOOST/race acceptance, controller tuning and loaded driving. Kart 3's three confirmed
mode readbacks and wheels-lifted throttle check do not establish those remaining stages.

## After the read-only checkpoint

After the individual controller's identity, complete configuration and display link are verified,
commission `kart-m5-espnow` (wireless) or `kart-m5` (UART) on that unit. Keep its pairing, OTA
configuration and controller pins; segmented application uploads must preserve NVS. Verify the
installed image, `writes:true`, fresh `id_ok`/`limits_ok`, a trustworthy baseline and, for wireless,
exact channel alignment before attempting a driver selection.

With the owner supervising the supported wheels-lifted setup, hold each mode for **650 ms**;
release between selections and record the request result **and actual VESC readback**. Calculate expected caps from that
kart's verified drivetrain/calibration and controller ceiling. Do not use kart 3's ERPM values as
another controller's calibration. Confirm no reconnect selection or command replay. Pit SLOW,
STOP/GRID rejection, base commands and driving acceptance need their own recorded checks.

Kart 3 completed the M5 portion with the installed pair listed in the README. Its separate
12-field persistent tune trial is an already-completed maintenance action, **not a commissioning
step to repeat**; [evidence](../../hardware/vesc/kart3/2026-11-10/tune-applied-v1/README.md).
The firmware's normal profile writes remain temporary (`store=0`). No unattended motor test is
part of these instructions.

## Build the next two M5 karts

Use the working kart-3 design, with a separate record for each new physical kart:

1. **Assign identity with Eamon.** Both new IDs are currently unassigned. Record the confirmed
   fleet ID, Core2/Heltec revisions and board MACs; never duplicate kart 3 or another live ID.
2. **Back up that unit.** Retain its own board flash/NVS recovery data privately. Capture all
   motor/app settings (189 + 187 on the verified 6.02 schema) from its own VESC using the [capture guide](../../tools/vesc/README.md).
   A runtime capture is not a verified saved-flash image. Keep Hall tables, motor R/L/flux,
   offsets/gains, drivetrain measurements, pedal endpoints and all application settings intact.
   Do not clone kart 3's full VESC tune or run its completed apply trial on another controller.
3. **Start read-only.** Install `m5-espnow` and `kart-m5-espnow-readonly` for wireless, with
   per-board rollback/source/image records. Provision only this unit's confirmed kart ID and
   independently measured BLE MAC + VESC UUID; require fresh identity/configuration readback.
4. **Pair just this Core2 and Heltec.** Use the explicit USB ports and assigned ID with
   `pair_espnow.py`. Generate a separate encrypted peer pairing and private LMK/PMK recovery
   file; never clone NVS, peer records or another kart's keys. Confirm both peer addresses and
   radio channel proof. New boards may use a different AP channel; channel 6 is an observation
   from kart 3, not a fleet requirement.
5. **Provision maintenance separately.** Use unique display/Heltec hostnames and OTA secrets
   per unit, retained only in private recovery files. Verify authenticated Core2 OTA, restart,
   maintenance off and telemetry recovery on that pair. Do not reuse kart 3's private files.
6. **Run the ordered read-only checks above.** Record own telemetry, touch, GPS/peer display,
   pit visibility, power/loss recovery and actual cadence. Confirm the intended kart appears
   at the pit while Eamon's units remain correctly assigned and independently connected.
7. **Commission control per unit.** Install its write-capable companion only after reviewing
   that unit's baseline and calibration. Verify the three driver modes by readback and then
   perform the separately supervised pit-command and driving checks. Preserve current ESC
   behavior on display/Heltec/BLE loss; never restore/replay a saved desired mode automatically.
8. **Share the evidence.** Record installed source/target/hashes, sanitized identity and mode
   results, and pending checks in the handoff. Coordinate checked Git milestones with Eamon;
   keep raw flash, keys/passwords and private recovery files out of Git.
