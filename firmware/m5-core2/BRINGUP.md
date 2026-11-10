# Core2 v1.3 + Heltec: first bench session

Bench session **2026-11-10**. This is a test guide, not a record that hardware passed.
Use branch `v1.5/m5-core2` and [the M5 README](README.md). Initial targets are `m5-demo`,
then either `m5-espnow` + `kart-m5-espnow-readonly` (wireless) or `m5` + `kart-m5-readonly`
(UART). Both live pairs keep all VESC writes disabled. Mode writes are a later, separately
supervised wired check.

**Setup checkpoint:** full rollback images are retained privately; earlier USB uploads and
the four-target touch diagnostic succeeded. Kart ID **3** is assigned to this board. The
previously reused VESC pin is not proof of kart 3's controller identity; see the identity check
below. Core2 maintenance/OTA is implemented and host-tested, but its actual transfer/reboot
and the read-only VESC telemetry test remain unverified here. Record observed hardware results
in [HANDOFF](../../HANDOFF.md), independently of build success.

## Bring to the bench

- M5Stack **Core2 v1.3 / K010-V13**, Heltec **WiFi LoRa 32 V4.3** with its GPS attached.
- Keep the LoRa antenna attached. ESP-NOW needs **no jumper wires** between boards. For the
  optional UART path only, use a Grove/HY2.0 cable broken out securely to the Heltec header.
- Two known-good USB-C data cables and adequate USB power, one per board. Label each cable
  so upload ports cannot be confused. For UART, the red Grove lead stays disconnected and insulated.
- Optional FAT32 microSD for a local course outline. Dashboard telemetry and the live GPS/peer
  map need no SD card. GPS map checks need sky view; peer checks also need another kart
  transmitting. A USB-only bench inside may show no GPS fix.
- Optional access to the existing pit dashboard to confirm **kart 3** is being received.
  Eamon remains kart 2; kart 1 is the older development kart. The owner assigned this board
  kart 3; an M5 display does not itself need a separate fleet ID.

The base station is optional for own VESC telemetry and directly received peer positions.
Central pit monitoring, commands and pit-managed race features need the base station. These
are design capabilities; their physical operation on this assembly still needs the checks below.

## Choose the local link

For wireless telemetry, use `m5-espnow` and `kart-m5-espnow-readonly`, power each board by USB,
and follow the pairing step below. The wireless build has a compile-time read-only guard:
driver modes and pit commands that would write to the VESC remain disabled.

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

Confirm which physical controller belongs to kart 3, then verify its actual BLE address and
UUID before commissioning this Heltec's pins. Coordinate with Eamon so only the intended
Heltec owns each VESC. Do not copy a historical baseline identity or adopt the first nearby
controller simply because it answers. `id_ok:true` alone does not prove physical ownership,
and an absent UUID pin allows address-only identity checks.

The merged 0.2.7 source releases a VESC whose UUID mismatches its pin and rejects reconnecting
to that address until re-pinned or rebooted. Confirm the installed Heltec version includes
that change; a source merge does not update hardware. Both `writes:false` and the correct
physical identity are required for the read-only telemetry check.

## Ordered physical checks

Before the first flash, identify both explicit serial ports and retain each board's previous
image and commissioning values for rollback. Flash backups may include Wi-Fi/OTA secrets;
keep them local under ignored `firmware/build/bench-private/`, never in Git or a public PR.
Record the source commit and target for each new image. Upload only after choosing the exact
board/port; build success alone does not establish that an image is installed.

For ESP-NOW, install both wireless targets first, verify the Heltec is saved as kart 3 with
`writes:false`, then run this from the repository root using Python with `pyserial` installed:

```sh
python3 tools/m5/pair_espnow.py \
  --core2-port /dev/cu.CORE2_PORT \
  --heltec-port /dev/cu.HELTEC_PORT \
  --kart-id 3
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
| 2. Local telemetry | Run the paired ESP-NOW targets, or the UART targets with three wires connected; begin with VESC off | Demo label disappears. Kart ID is 3 and Heltec status reaches the display; VESC is disconnected while off. DASH/MAP and map filter respond. Mode controls remain unavailable. No base station or SD card is required. |
| 2b. VESC telemetry | Complete the kart-3 identity check above, then turn on its intended VESC for a read-only check | Electrical values match Heltec USB `self` telemetry; no throttle or motor command is sent. |
| 3. Identity/read-only | On Heltec USB console, request `status` | `writes:false`, `transport:"ble"`, intended `vescmac`/`vesc_uuid`, `id_ok:true` and `radio:true`. Before later mode testing, verify nonempty `uuid_pin` matches `vesc_uuid`; `id_ok` alone also allows address-only binding. No motor test or settings write is needed. |
| 4. GPS/map | Allow an outdoor fix; power another transmitting kart for the peer check; install optional course SD before starting display | Own numbered dot gets a white ring; a directly received peer with a valid fix appears without a base station or SD card. Course outline is visible if loaded. With no fix, GPS speed is `--`, not a fabricated zero/location. |
| 5. Shared pit (when available) | View kart 3 in existing pit dashboard | Pit receives live kart-3 updates. M5 PIT OK means it heard a beacon, so confirm both directions separately. Record this stage as pending if no base is available; it does not block own telemetry/direct peer checks. |
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
SD card. The Heltec remains read-only. First install the maintenance-capable Core2 application
over USB and provision its four-field configuration using the [README procedure](README.md#core2-maintenance-and-ota).
Keep the matching `ota_password` in a private `0600` JSON file under ignored
`firmware/build/bench-private/`; never put the credentials in shared evidence.

1. Reboot Core2 and request USB `ota status`: credentials may be `configured:true`, but
   `active`, `ready` and `updating` must be false. Confirm ordinary ESP-NOW telemetry first.
2. Hold the **top status bar for 1.8 seconds** to open DISPLAY UPDATES, then tap ENABLE UPDATES;
   alternatively send Core2 USB `ota on`. Expect a ten-minute window and
   **`gokart-display-3.local`**. Wait for `ota status` to report `ready:true`.
3. Run `tools/m5/ota_core2.py` with explicit `--host`, application `--image`, private
   `--credentials`, and official `--espota` paths as shown in the README. Preserve the printed
   SHA-256 and acknowledgement. The tool stops within 120 seconds; it never sends a VESC command.
4. Observe upload progress and the display restart. Read Core2 `status` and `ota status` after
   reboot: maintenance must be off. Confirm the expected installed build with the image/build
   evidence, not just the generic `m5-v1.5` status label.
5. Confirm reciprocal `espnow status` becomes linked again and fresh own/peer telemetry returns.
   Check the Heltec still reports `writes:false`, the intended VESC identity, and unchanged active
   limits. Record transfer, reboot and recovery outcomes separately; neither uploader ACK nor
   host tests alone establishes these results.

Maintenance pins Core2 to its access point's Wi-Fi channel while ESP-NOW search is paused;
telemetry may temporarily disappear if the Heltec is on another channel. The actual flash
transfer also pauses normal telemetry parsing. Mode requests remain blocked throughout the
active window, including when BACK TO DASHBOARD is selected. DISABLE UPDATES or USB `ota off`
closes an idle window and resumes channel discovery; repeating `ota on` does not extend the
deadline. An authenticated transfer already in progress is allowed to finish before expiry.

For a timeout, authentication error or missing reboot, inspect status first and keep USB
recovery available; do not infer success or automatically repeat the upload. Actual hardware
OTA acceptance is **pending** until the observations above are recorded in HANDOFF.

## Quick diagnosis

| Symptom | First checks |
| --- | --- |
| Display dark | Run standalone `m5-demo`; verify USB power, Core2 power button and correct Core2 target before debugging the Heltec wires. |
| Demo dots still shown | `m5-demo` is still installed. Use `m5` for UART or `m5-espnow` for wireless telemetry. |
| Tabs do not respond | The four-target diagnostic confirmed touch input in IRQ mode. Verify the new image has outlined 40-pixel tabs; inspect Core2 USB `status` for page, touch count and coordinates. Final dashboard UI confirmation is still pending. |
| HELTEC DATA LOST over ESP-NOW | Correct wireless targets, both boards powered, reciprocal peer IDs and pairing on USB `espnow status`; allow channel search. Outside maintenance, Core2 does not join an access point; during maintenance its AP channel can temporarily interrupt telemetry. No jumper wires are needed. |
| HELTEC DATA LOST over UART | Common ground, white G33 to Heltec47, both boards powered, correct M5 UART companion target, 230400 baud. |
| VESC DISCONNECTED | Verify kart 3's physical controller and both pins; the historical d8:94:35:be:e5:32 controller belongs to kart 2. Check VESC power and UUID-mismatch rejection. The M5 does not own BLE. |
| Electrical data works but no map/speed | GPS needs a valid fix. M5 v1.5 speed is GPS-derived; spinning wheels on a stationary stand will not show road speed. |
| Mode or pit motor controls unavailable | Expected with either read-only Heltec target. The ESP-NOW target is compile-time telemetry-only. Do not switch on writes just to make the first telemetry test pass. |
| PIT LOST | Expected with no base station. When testing the pit, confirm base power, antenna and matching fleet/radio settings. Own VESC telemetry and direct peer positions do not require a pit beacon. |
| No other kart on map | Confirm another kart is transmitting with a valid GPS fix, antennas are attached and fleet/radio settings match. Neither a base station nor an SD card is required for direct peers. |
| Core2 OTA unavailable | Use `m5-espnow`, provision over USB, explicitly enable the window, and inspect `ota status`. Host is `gokart-display-3.local`, distinct from Heltec `gokart-3.local`; no SD is required. |
| Course absent | FAT32, `/gokart/course.json`, schema1, 2–128 valid points, file <=24576 bytes; restart the display after inserting the card. |

## Record before calling it passed

- Date/operator, board revisions, source commit, targets and which image was actually flashed.
- Rollback image location (private), power arrangement, selected transport and a wiring photo if UART.
- For ESP-NOW: nonsecret peer identities, pairing readback, channel, link/drop counters and recovery
  time; never include LMK/PMK or the private recovery file in shared evidence.
- Kart ID, physically verified VESC ownership, actual BLE/UUID pins and `writes:false`; strip credentials from anything shared.
- For Core2 OTA: application SHA-256, target hostname, authentication/ACK result, observed reboot,
  maintenance disabled after boot, and ESP-NOW telemetry recovery. Keep passwords out of evidence.
- Screen/touch, GPS/course, second kart and pit observations; mark unavailable checks pending.
- Measured report cadence, any resets/freezes, link-loss/recovery outcome and VESC active limits
  before/after. Retain local logs with timing if a problem occurs.

Then update HANDOFF.md with **observed** results. Mode acknowledgements, STOP/SLOW interactions,
controller tuning and motor movement belong to the later supervised control session.
