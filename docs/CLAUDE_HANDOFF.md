# GoKart Control — Claude handoff, November 12, 2026

**Start here.** This is the current M5 v1.5 test-preparation handoff. `HANDOFF.md` is the
long chronological record; earlier dated sections describe earlier states. No hardware
was accessed, flashed, reset or driven during this overnight display work.

## Open the right project

- Canonical project: `~/Projects/50 Day/GoKart Control/`.
- Active software worktree: `~/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5`.
- Branch: **`v1.5/m5-core2`**. Remote: `git@github.com:colinfost3r/GoKart-Control.git`.
- [Draft PR 5](https://github.com/colinfost3r/GoKart-Control/pull/5).
- Read `AGENTS.md`, this file, then the relevant linked procedure. Check Git root/status
  and fetch before starting and before pushing. Do not switch/reset the canonical checkout:
  it contains separate CAD work. Do not force-push or overwrite another collaborator.
- Owner authorizes ongoing coherent tested commits/pushes. Keep handoff, requirements and
  `config/project.json` consistent. Keep passwords, pairing keys and full flash backups private.

```sh
cd "$HOME/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5"
git rev-parse --show-toplevel
git status --short --branch
git fetch origin
git log --oneline HEAD..origin/v1.5/m5-core2
```

The final overnight source, preview and documentation are on this branch. The corresponding
[test/build manifest](validation/m5-ready-2026-11-12.json) binds application hashes to source
hashes. Locally frozen application images are under ignored
`firmware/build/bench-candidates/2026-11-12/`; these local build artifacts are **not in Git**.
A fresh clone can rebuild using the pinned ESP32 Arduino 3.3.8 toolchain. The compiled image
hash can differ after rebuilding; record the bytes actually uploaded.

## Owner's intended outcome

First test this evening's Core2 changes on **kart 3**, fix real display/touch/link issues,
then commission two matching units as **karts 4 and 5**. **Karts 1 and 2 belong to Eamon's
ongoing tests.** Player Core2 has no Pi and no SD. ESP-NOW connects each Core2 to its own
Heltec; no I2C/UART cable is needed for that path.

Core2 should own the following map/course cache and eventually join-only player/inventory
logic. Heltec owns GPS, LoRa and exclusive VESC BLE supervision. User wants the host's course
published/downloaded over ESP-NOW, Hunter's original cyan/amber instrument styling on both
pages, a host notification and one compact FIRE control. Do not add host/course-editing UI
to the Core2 or substitute Eamon's Pi-dependent item screen.

Reliability comes first: wired throttle and reverse remain VESC-owned. Accessory/link loss
must leave current driving settings alone. Boot/reconnect must not restore a profile, stop,
replay a command or re-save configuration. Ordinary supervisory writes remain `store=0`.

## What is actually ready

| Capability | State at handoff |
| --- | --- |
| Native Hunter-style DASH and full-screen 320×240 own-follow MAP | Built/tested, not uploaded |
| Tiny GPS MPH + actual VESC pack volts relayed by Heltec | Built/tested; stale values become dashes; no estimated SOC |
| No kart header, scale, permanent course-name strip or full-width FIRE footer | Implemented |
| Attribution only at startup | Five visible seconds; nonblocking; source/license metadata retained |
| Touch page toggle; 1.8 s page-button hold for updates | Implemented; overlay/held-touch isolation tested |
| Fresh own/peer GPS, no-SD map, USB-uploaded persistent course outline | Source ready; new map still needs physical acceptance |
| Real surrounding shop geography, S/F checker, boost/pickup and game interaction | **Demo only**; geography real, course/positions/game events synthetic |
| Live JOIN, host course-package download, item authority and FIRE | **Not implemented**; live FIRE sends nothing |
| VESC tune/filter on kart 3 | Previously saved and supervised bench-verified; unchanged overnight |
| Karts 4/5 tune/filter replication | Offline preparation tool exists; target captures/application still needed |

The background is a compact crop of the Pi's cached SoNo OpenStreetMap extract. The Pi's
photographic maps are downloaded from its pit server, not Google Maps. The demo is at the
shop, **not a surveyed Manresa Island course**. Gold 3 is the own demo kart; blue numbers
are peers. S/F, boost and pickup symbols do not establish lap timing or motor effects.

Open [the self-contained rehearsal](previews/core2-player-rehearsal/index.html), or run:

```sh
python3 tools/m5/preview_driver.py --out /tmp/gokart-core2-preview --write-scenes
```

There are 32 native-rendered scene/page combinations. Browser labels approximate LCD fonts;
all browser scenarios, including LIVE, are fake. `m5-demo` initializes no radio/control link
and cannot send a mode or motor command. It also has **no OTA**, so installing it requires a
USB route back to `m5-espnow`. Do not leave the commissioned kart stuck on a demo image.

## Known installed kart-3 checkpoint — not the new candidate

Both accessory applications are still from **`4a582f0`**:

| Installed target | SHA-256 |
| --- | --- |
| Heltec `kart-m5-espnow` | `11e556e8d525632916f9ef05ac12e8f3f4346ed70f0adfbd6a3ecc3aa08821f2` |
| Core2 `m5-espnow` | `996c4387cb51a16286e89760ac035aa421bfbede608a8f56092f2a319cec9b0a` |

- Core2 v1.3 / K010-V13, Heltec WiFi LoRa 32 V4.3 + L76K. Encrypted local pair,
  last aligned channel 6. Existing private NVS contains pairing and Wi-Fi/OTA credentials.
- VESC BLE **`f7:bd:23:cc:62:0e`**, UUID **`37004e000951343037353739`**.
  Physical Flipsky **75100 Pro V2.0**, firmware 6.02/test0, reports `75_300_R2`, `no_hw_limits`.
  Do not replace its firmware based on the reported hardware string alone.
- Pack nominal 72 V, full 84 V. Motor temperature sensors are not wired.
- Last supervised November 11 state: ECO, forward/released/stopped, fault0; saved motor
  minimum **−5 A** persisted over normal cold boot. Saved VESC-local RX filter active.
  ECO/NORMAL/SPORT readbacks and smooth wired forward/reverse with both accessories passed.
  This is wheels-up ECO coexistence, not road/load/endurance or full pit-game acceptance.
- [Coexistence evidence](../hardware/vesc/kart3/2026-11-11/heltec-coexistence-01/README.md).
  [Saved −5 A evidence](../hardware/vesc/kart3/2026-11-11/brake-limit-persistent-01/README.md).

Do not repeat the tune or reinstall the filter just to update the screen.

## Next session: kart 3 first

1. Identify physical USB ports, capture read-only accessory status and preserve existing
   app/NVS rollback evidence. Never assume a previously used `/dev/cu.*` is the same board.
   For any powered kart test, establish wheels lifted, released pedal, operator at cutoff.
   Begin display programming with VESC off. No unattended motor test is queued.
2. Choose either a spare/USB-connected Core2 demo rehearsal or the live **`m5-espnow`**
   candidate. Use the manifest-matched application image, never `core2-items`, generic
   `core2`, or a merged release image that could overwrite provisioned state.
3. Leave the working Heltec application alone for the first display acceptance. The source
   also has newer channel recovery; deploying that is a **separate** acceptance step after
   the display works. New Heltec build hashes do not mean it is installed.
4. Existing installed Core2 opens OTA by holding its **old top status bar** 1.8 seconds.
   After this candidate is installed, hold the **upper-right DASH/MAP button** 1.8 seconds.
   First press changes page; continuing the hold opens maintenance; sliding away cancels.
   USB `ota on` is the alternative. Enable updates deliberately and wait for `ready:true`.
5. Use the authenticated application-only uploader below. Verify upload ACK, actual reboot,
   maintenance off, retained pairing/credentials, fresh telemetry, expected source/image record
   and correct kart ID independently. An ACK alone is not hardware acceptance. No blind retry
   after an uncertain upload. Keep USB recovery available.
6. Check five-second startup then MAP, text at mounted distance, page toggle, compact controls,
   stale GPS/link/voltage, and maintenance BACK held over each mode area. Mode requests require
   a **fresh deliberate 650 ms hold**; neither startup nor navigation/overlay presses may send one.
7. Get sky view. Verify real own position follows, fresh nearby peer labels, and no fabricated
   GPS. A dark/empty map is diagnosable using `status`: `gps_fresh`, `gps_has_position`,
   `gps_position_age_ms`, `course_source`, `course_points`, `map_follow`. A fix alone does not
   supply a course/background. See [course provisioning](../firmware/m5-core2/COURSE_MAP.md).
8. With the operator present and stopped, verify mode readbacks preserve −5 A and all unrelated
   settings. Then explicitly coordinate any brief wired-pedal forward/reverse checks. Record
   real observations; do not count an idle log or an earlier press as the current test.
9. Archive results per device, including hashes, mode/link/readback outcomes, and limitations.
   Only then repeat the accepted display process on new units.

Core2 OTA command (placeholders must be resolved locally; **do not run unattended**):

```sh
python3 tools/m5/ota_core2.py \
  --host gokart-display-3.local \
  --image firmware/build/bench-candidates/2026-11-12/m5-espnow.app.bin \
  --credentials /absolute/path/to/private-core2-credentials.json \
  --espota /absolute/path/to/esp32/3.3.8/tools/espota.py
```

On Colin's current Mac, the official uploader is under
`/private/tmp/gokart-arduino/data/packages/esp32/hardware/esp32/3.3.8/tools/espota.py`.
Private credentials/rollback files live under ignored `firmware/build/bench-private/`;
locate the intended kart's file without printing secrets. The uploader requires a 0600 file
with `ota_password`. Use `gokart-display-3.local`, not Heltec's `gokart-3.local`.
For USB, follow the existing segmented/NVS-preserving procedure; do not erase whole flash.

## Then karts 4 and 5: preserve calibration and identity

Use [the fleet preparation guide](kart4-kart5-replication.md) and
[repeat bring-up](../firmware/m5-core2/BRINGUP.md#build-the-next-two-m5-karts).
Neither new unit's UUID/BLE/pairing/capture is known yet. Never guess or clone kart 3 NVS.

- Start each new Heltec with **`kart-m5-espnow-readonly`**, Core2 **`m5-espnow`**.
  Label ID 4/5, identify its actual VESC, use fresh private reciprocal ESP-NOW keys and
  unique `gokart-N` / `gokart-display-N` OTA hostnames. Verify read-only telemetry first.
- Capture all 189 motor + 187 app settings and stored Lisp per target, with accessory BLE
  disconnected for USB inspection. Keep rollback evidence. Preserve Hall/pedal/electrical
  calibration, identities, motor direction and drivetrain metadata.
- Use `tools/vesc/prepare_fleet_kart.py` offline. The full-scale source is:
  `hardware/vesc/kart3/2026-11-11/brake-limit-persistent-01/coldboot-forward/raw`.
  **Do not use the last temporary ECO capture** as the full-scale tune baseline.
- The tool copies twelve reviewed operating fields including −5 A and produces a UUID-bound
  filter. All other motor bytes and all app fields remain target-specific. Review all 376
  fields; retained operating differences block equivalent-tune acceptance. In particular,
  battery regen minimum and current scales are not copied automatically.
- **There is no validated kart4/5 apply tool yet.** Existing `apply_tune.py` and
  `install_rx_filter.py` are deliberately kart3-pinned. Do not bypass pins/hash checks.
  Build/review a per-target apply procedure after real captures exist: fresh identity/rest,
  exact proposed bytes, Lisp ownership, ACK/readback, uncertain-send journal and no automatic
  retry/rollback. `proposed_motor_response.bin` is a read-response-shaped review artifact,
  not a packet to send to the controller.
- Supervise each unit's normal cold boots, correct filtered direction, repeated starts from
  full rest, then accessory coexistence and intentional mode controls. Do not rerun Hall or
  pedal calibration. Resolve native ADC prerequisite differences before filter installation.

**VESC updates over Heltec are not supported by the present code.** Heltec OTA updates its
ESP32 application. `VescLink` exposes reads and temporary limit writes with `store=0`; it
has no persistent full-tune, Lisp-upload or VESC-firmware update path. Use the established USB
maintenance path for tune/filter work. No VESC firmware upgrade is needed for this plan.
A future BLE maintenance proxy would require separate ownership, framing/ACK/readback and
failure review; do not turn ordinary reconnect code into a persistent writer.

## Eamon/Hunter compatibility and remaining game work

Fetched upstream through **`59976df`**; integrated through **`a5a4c22`**. No new remote work
appeared during final preparation. Four later Eamon commits remain reviewed, not merged:
`c21baf8` Pi freeplay/laps/inventory/no-driving-scans, `15f731a` Pi fastboot,
`c4731bd` separate item-screen power handling, `59976df` separate item-screen OTA.
They do not by themselves implement no-Pi Core2 gameplay. Keep the paired M5 receive
callback/encryption and existing pit precedence when integrating future changes.

The next implementation boundary is [the player-mode brief](m5-player-mode.md): agree a
bounded host game package using Eamon's existing item/session rules, implement its publisher
and authenticated ESP-NOW transfer/atomic cache, then native inventory/game requests through
own Heltec. Test transfer/session correctness before any motor effects. Do not describe the
preview's synthetic JOIN/download/SHELL as actual RF support. Hunter's original graphics at
`315710e` through `5629924` remain the requested aesthetic reference.

## Validation and known limits

Run all offline suites before each push:

```sh
PYTHON=/Users/cofo/.platformio/penv/bin/python \
ARDUINOJSON_DIR=/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src \
  tools/run_tests.sh

PATH=/private/tmp/gokart-arduino/bin:$PATH \
ARDUINO_CONFIG_FILE=/private/tmp/gokart-arduino/arduino-cli.yaml \
  firmware/build.sh m5-espnow
```

Also build `m5-demo`, `m5`, `kart-m5-espnow-readonly` and `kart-m5-espnow` when those candidates
change. Paths above describe this Mac, not portable dependencies; a fresh machine follows
`firmware/README.md`. All **499 tests across eight suites passed, zero skipped**, and all five candidates compiled.
Exact image/source hashes are in the linked November 12 manifest. Native tests include ASan/UBSan. An independent subagent reviewed the
final display changes: maintenance BACK no longer leaks a mode request, splash duration starts
after initialization, and DEMO stays visible in error scenes. No unresolved code findings
remained in that scope. Physical LCD readability/touch, OTA, live GPS/fleet/course persistence,
RF coexistence and actual gameplay are separate acceptance tasks; none was tested overnight.

Suggested first message to Claude: “Read AGENTS.md and docs/CLAUDE_HANDOFF.md on
v1.5/m5-core2. Continue with the kart-3 display acceptance first, preserve all calibration,
pairing and active VESC settings, and record actual installed versus candidate versions.”
