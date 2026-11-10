# Core2 v1.3 + Heltec: first bench session

Bench session **2026-11-10**. This is a test guide, not a record that hardware passed.
Use branch `v1.5/m5-core2` and [the M5 README](README.md). Initial targets are `m5-demo`,
then either `m5-espnow` + `kart-m5-espnow-readonly` (wireless) or `m5` + `kart-m5-readonly`
(UART). Both live pairs keep all VESC writes disabled. Mode writes are a later, separately
supervised wired check.

**Current checkpoint:** both full 16 MB backups are retained privately. Core2 demo/live and
Heltec `kart-m5-readonly` images were uploaded and hash-verified. Saved kart ID is **3**,
VESC UUID/MAC are pinned, and `writes:false`/radio OK at 2 Hz are reported. GPS data is arriving
with no fix. Wi-Fi is connected and `gokart-3` is verified; an OTA password is stored but no
actual OTA upload has been tested. The owner sees kart 3 in the pit. No UART wires are fitted.
Four diagnostic touch targets worked in normal IRQ mode with logged coordinates. The new
outlined 40-pixel tabs await final UI confirmation. Wireless builds, installation and end-to-end
acceptance remain pending. Keep the VESC off until the first read-only telemetry test.

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
| 2b. VESC telemetry | Once the display link works, turn on the intended VESC for a read-only check | Electrical values match Heltec USB `self` telemetry; no throttle or motor command is sent. |
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

## Quick diagnosis

| Symptom | First checks |
| --- | --- |
| Display dark | Run standalone `m5-demo`; verify USB power, Core2 power button and correct Core2 target before debugging the Heltec wires. |
| Demo dots still shown | `m5-demo` is still installed. Use `m5` for UART or `m5-espnow` for wireless telemetry. |
| Tabs do not respond | The four-target diagnostic confirmed touch input in IRQ mode. Verify the new image has outlined 40-pixel tabs; inspect Core2 USB `status` for page, touch count and coordinates. Final dashboard UI confirmation is still pending. |
| HELTEC DATA LOST over ESP-NOW | Correct wireless targets, both boards powered, reciprocal peer IDs and pairing on USB `espnow status`; allow channel search. Core2 does not join an access point. No jumper wires are needed. |
| HELTEC DATA LOST over UART | Common ground, white G33 to Heltec47, both boards powered, correct M5 UART companion target, 230400 baud. |
| VESC DISCONNECTED | Check the Heltec's existing BLE pin/identity and VESC power. The M5 does not own BLE. |
| Electrical data works but no map/speed | GPS needs a valid fix. M5 v1.5 speed is GPS-derived; spinning wheels on a stationary stand will not show road speed. |
| Mode or pit motor controls unavailable | Expected with either read-only Heltec target. The ESP-NOW target is compile-time telemetry-only. Do not switch on writes just to make the first telemetry test pass. |
| PIT LOST | Expected with no base station. When testing the pit, confirm base power, antenna and matching fleet/radio settings. Own VESC telemetry and direct peer positions do not require a pit beacon. |
| No other kart on map | Confirm another kart is transmitting with a valid GPS fix, antennas are attached and fleet/radio settings match. Neither a base station nor an SD card is required for direct peers. |
| Course absent | FAT32, `/gokart/course.json`, schema1, 2–128 valid points, file <=24576 bytes; restart the display after inserting the card. |

## Record before calling it passed

- Date/operator, board revisions, source commit, targets and which image was actually flashed.
- Rollback image location (private), power arrangement, selected transport and a wiring photo if UART.
- For ESP-NOW: nonsecret peer identities, pairing readback, channel, link/drop counters and recovery
  time; never include LMK/PMK or the private recovery file in shared evidence.
- Kart ID, VESC identity and `writes:false`; strip credentials from anything shared.
- Screen/touch, GPS/course, second kart and pit observations; mark unavailable checks pending.
- Measured report cadence, any resets/freezes, link-loss/recovery outcome and VESC active limits
  before/after. Retain local logs with timing if a problem occurs.

Then update HANDOFF.md with **observed** results. Mode acknowledgements, STOP/SLOW interactions,
controller tuning and motor movement belong to the later supervised control session.
