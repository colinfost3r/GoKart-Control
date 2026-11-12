# GoKart Control — Claude handoff, November 12, 2026

**Start here. This supersedes the earlier display-only handoff.** The owner objected that real
host downloads and item firing were unfinished. Those paths are now implemented and reviewed
in the native player candidate. Offline validation does not establish hardware acceptance.

**Update, November 12 afternoon: both kart 3 accessories now run the candidate.** The Core2 and
Heltec applications were written over USB with the VESC off; identity, VESC pins, pairing and
Wi-Fi/OTA settings were retained and the pair re-linked. Nothing was driven and nothing was
written to a VESC by the update. The owner confirmed the new map screen appears. With the VESC
then powered, the Heltec reconnected to the pinned controller, ECO/NORMAL/SPORT from the Core2
were written and verified at the November 10 values, and the wheel ran forward and reverse
with fault 0 throughout; the owner confirmed pedal feel matched November 11. Still open: pit
STOP/SLOW/BOOST, a sustained soak, a VESC cold boot, GPS, and everything that needs the host
(course download, JOIN, FIRE). See
[the install record](../hardware/m5/2026-11-12-kart3-player-update/README.md).

## Project and Git

- Canonical project: `~/Projects/50 Day/GoKart Control/`.
- Active worktree: `~/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5`.
- Branch `v1.5/m5-core2`; remote `git@github.com:colinfost3r/GoKart-Control.git`.
- [Draft PR5](https://github.com/colinfost3r/GoKart-Control/pull/5).
- Read `AGENTS.md`, this document and [native player guide](m5-player-mode.md). Confirm the
  Git root/status, fetch before work and before push. The canonical checkout includes separate
  CAD work; do not reset/switch it or overwrite another collaborator. No force push.
- Ongoing tested commits/pushes are owner-authorized. Keep credentials, pairing keys and full
  flash backups private. All persistent work belongs under Projects, not Documents/Codex.

```sh
cd "$HOME/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5"
git rev-parse --show-toplevel
git status --short --branch
git fetch origin
```

The candidate manifest is [m5-player-2026-11-12.json](validation/m5-player-2026-11-12.json).
Application binaries are frozen locally under ignored `firmware/build/bench-candidates/2026-11-12-player/`;
they are not Git deliverables. Rebuild on a fresh machine and record the bytes actually uploaded.
The older `2026-11-12/` bundle/manifest belongs to the display-only checkpoint `a21ed7c`.

## What changed and what remains

| Feature | Current state |
| --- | --- |
| Full 320×240 own-follow map; tiny GPS MPH + Heltec-relayed VESC pack volts | Implemented, not installed |
| Hunter-style DASH/MAP, one FIRE, page/notification controls, 5s startup credits | Implemented; no permanent header/scale/credits |
| Host Pi export and ACK-paced upload to its Heltec | Implemented; updated host software required |
| Course-only authenticated ESP-NOW transfer, complete validation and two-slot NVS cache | Implemented; separate host↔Core2 pairing required |
| Real JOIN/LEAVE, local boxes/inventory, typed single-use FIRE through own Heltec | Implemented; physical radio/effect acceptance pending |
| Course/zone/S/F rendering and bounded OSM background from host repository | Implemented; not aerial imagery or an invented Manresa survey |
| Host generation beyond ESP-NOW range | Optional short LoRa type5; host/player firmware must be updated |
| VESC tune/filter, −5 A and own-kart pairing | Existing kart3 checkpoint unchanged |
| Kart4/5 tune/filter replication | Offline preparation exists; per-target capture/apply acceptance still needed |

The native player uses Eamon's item roll weights, session/attack semantics and existing Heltec
BOOST/SLOW paths. Light-player limits are deliberate: starting box snapshot with local cooldowns,
three carried slots plus an attack slot, explicit shield arming, fixed-duration non-stacking boosts,
no reconnect inventory restoration, no global pickup arbitration or authoritative race ranking.
See [exact behavior/limits](m5-player-mode.md#native-rules-and-deliberate-limits).

Core2 owns player UI/logic; Heltec retains exclusive VESC BLE, GPS, LoRa and supervisory guards.
Wired throttle/reverse remain VESC-owned. Link loss/reboot/maintenance never restores a driving
profile, replays an item or writes persistent VESC settings. Existing mode/pit guards remain.

Eamon source through **c21baf8** is now integrated by three-way source comparison: timed freeplay
laps, 5-box default, Pi inventory persistence and no Wi-Fi reconnect scans while driving. One new
upstream test was updated to supply fresh controller state after proving a stale item use is refused;
our existing freshness guard was retained.

Later on November 12, Eamon's branch was merged through **`c39df6a`** (merge `5af0e6a`) so PR5 no
longer conflicts: Pi fastboot, separate `core2-items` 0.2.2–0.3.2 (key power, pit-AP OTA, kart
pinning), `set_wifi.py`, and his release images/notes. The merge changed no M5 dashboard, player
Heltec, host `kart` or Pi server source; the candidate binaries and their manifest stay valid.
Never substitute `core2-items` for this dashboard. Two things to know:

- Eamon's released `kart-heltec-v4-ble-0.3.3.merged.bin` and this branch's `kart` build both
  report `kart-0.3.3` but are different firmware. Identify an installed image by hash, not version.
- The manifest's build-input hash for `firmware/core2-items/core2-items.ino` predates the merge.
  None of the eight candidate targets compile that file.

## Next session: coordinated kart3 and host acceptance

1. Identify physical USB/OTA endpoints and current app hashes; preserve NVS/rollback evidence.
   Karts1/2 remain Eamon's. Coordinate the host update with him; do not overwrite an active test.
   Kart3 first, then4/5. Establish operator, stationary kart, wheels lifted, pedal released and
   cutoff before any powered vehicle test. Start display programming with VESC off.
2. Build/select the matching **Core2 `m5-espnow`**, player **`kart-m5-espnow`**, and host **`kart`**
   applications. Deploy the updated host `kart/server` tree including `m5_course.py`. Preserve
   the existing private pairing/Wi-Fi/identity NVS; application-only updates, no whole-flash erase.
   `m5-demo` is optional no-output rehearsal, has no OTA and needs USB to return to live firmware.
3. Read `share status` to get host/Core2 station MACs/channel. Configure separate course-only
   trust using [pair_course.py procedure](m5-player-mode.md#deployment-and-first-test). It checks
   board MAC/role/ID/channel and saves a0600 private plan; never prints secrets or reboots boards.
   Stop the Pi serial owner while provisioning the host from another computer, then restore it.
   The player's own Heltec must be running so Core2 can identify kart3. Channel6 was the last
   local pairing checkpoint; verify the host uses the same channel rather than guessing.
4. Existing installed Core2 opens OTA by holding its old top status bar1.8s. The candidate uses
   the upper-right DASH/MAP button held1.8s (or USB `ota on`). First press toggles page;
   continuing hold opens updates. Use `tools/m5/ota_core2.py`, password file0600 and official
   espota from ESP32 Arduino3.3.8. Core2 hostname is `gokart-display-3.local`; Heltec is `gokart-3.local`.
   An upload ACK alone is not proof of reboot, correct identity, retained pairing or live link.
5. Verify native pages, touch, maintenance BACK, GPS/voltage staleness and mode hold isolation.
   Host a real course and inspect publication bytes/progress. On Core2 JOIN, prove actual
   download, complete validation/cache, confirmed session, cancellation, interrupted transfer,
   reboot cache and course replacement. Diagnostics: `status` emits `m5_game`; `share status`
   emits `share_radio`/`share`. An empty background may mean the host has no geographic extract.
6. Only after transfer/session passes, supervise native pickup/FIRE. Confirm exactly one
   request, own Heltec result, remote attack ACK for shell/lightning, and actual VESC readback
   for an effect. Also verify STOP/SLOW precedence, no replay after loss/OTA and smooth wired
   driving coexistence. Do not infer a motor test from a simulated scene, idle log or earlier press.
7. Archive per-device installed hashes and observations. Only then repeat accepted setup for4/5.

LoRa compatibility: existing telemetry/commands are unchanged. Publishing substitutes one short
COURSE packet per2s for host telemetry; host telemetry averages1.5Hz at rate2,0.5Hz at rate1.
Legacy base/repeaters ignore type5; updated repeater is required only for relay-dependent course
identity coverage. The first test can use direct host/player LoRa with no base. This is freshness,
not cryptographic LoRa replay protection. Course download and own-kart commands are authenticated.

## Installed on kart 3 — candidate applications since November 12

| Installed target | SHA-256 | Reports |
| --- | --- | --- |
| Heltec `kart-m5-espnow` | `d43662645457f51283010d655cc2f60d5740adafc015adc59910e70fd136cab9` | `kart-0.3.3`, built Nov 12 08:55:51 |
| Core2 `m5-espnow` | `894a1a34537b5894110ddb120b2419f18b0fad8432b0e7acac775306ce58d3ac` | `m5-v1.5`, answers `m5_game` |

The previous `4a582f0` pair (Heltec `11e556e8…21f2`, Core2 `996c4387…9b0a`) was read back from
flash before the update and is kept privately for rollback; see the
[install record](../hardware/m5/2026-11-12-kart3-player-update/README.md). The November 11
observations below were made on that previous pair; on the candidate, identity, the three mode
readbacks and wheels-up forward/reverse were repeated on November 12, cold-boot behaviour was not.

- Core2 v1.3 / K010-V13, Heltec WiFi LoRa 32 V4.3 + L76K. Encrypted local pair; channel 6 on
  November 11, channel 2 after this update because the Heltec follows the Wi-Fi access point.
  Existing private NVS contains pairing and Wi-Fi/OTA credentials.
- Opening either USB port with DTR/RTS cleared reboots that board; the driver default does not.
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

## Validation and artifacts

**Final offline validation: 511 tests across eight suites passed, zero skipped; eight firmware targets compiled.**

The [candidate manifest](validation/m5-player-2026-11-12.json) records exact source/application
hashes, final tests, independent review and limitations. Run all suites before each push:

```sh
PYTHON=/Users/cofo/.platformio/penv/bin/python \
ARDUINOJSON_DIR=$HOME/.local/share/gokart-arduino/user/libraries/ArduinoJson/src \
  tools/run_tests.sh
PATH=$HOME/.local/share/gokart-arduino/bin:$PATH \
ARDUINO_CONFIG_FILE=$HOME/.local/share/gokart-arduino/arduino-cli.yaml \
  firmware/build.sh m5-espnow
```

Other affected targets: `kart-m5-espnow`, `kart-m5-espnow-readonly`, `kart`, `m5`, `m5-demo`,
`base`, `repeater`. Native ASan/UBSan coverage includes host-export→chunk-transfer/retry→cache→
JOIN→GPS pickup→FIRE, wrong/expired generation, loss/reboot, and production Heltec command
handling. Existing touch, mode, transport, pit and VESC tooling checks remain in the suite.
[Native renderer fixtures](previews/core2-native-player/index.html) use actual production UI
with synthetic inputs; [older interactive rehearsal](previews/core2-player-rehearsal/index.html)
is entirely simulated. Neither establishes hardware RF, GPS, storage power-loss or motor acceptance.

Review fixed stale host publication, boot/generation binding and rejected-boost duration state.
Final source and documentation reviews found no additional functional showstopper; the physical acceptance gates above
remain. No unattended hardware task, upload, VESC write or motor command is queued.

Suggested Claude opening: “Read AGENTS.md and docs/CLAUDE_HANDOFF.md on v1.5/m5-core2.
Coordinate the host update, then accept actual course download and native FIRE on kart3.
Preserve calibration/pairing, distinguish installed from candidate, and record real observations.”
