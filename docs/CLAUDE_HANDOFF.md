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

**Update, November 13: kart 3 now runs the game-rules candidate** (`2026-11-13-game-rules`).
Both applications were written over USB with the VESC off, after reading back and keeping the
November 12 pair. With the VESC then powered: identity and limits read cleanly, ECO/NORMAL/SPORT
were written and verified at the November 10 values, the wheel ran forward and reverse with
fault 0, and the owner reported the pedal felt right. A ten-minute soak with the VESC on then
ran with no reset, fault or link drop; the Heltec's heap low-water mark settled at 37.4 kB. The
host is **not** updated, so nothing that needs it (course download, JOIN, the game-speed lock,
FIRE, the boost changes) has run on hardware. Kart 3's Heltec speed factor was also changed from
2.48 to **1.736** (owner decision): the new ECO and NORMAL caps were written from the Core2, read
back, and the wheel levelled off under them with the wheels up. It is provisional until a GPS
check on the road. See
[the November 13 install record](../hardware/m5/2026-11-13-kart3-game-rules-update/README.md).

**Update, November 13 evening: built-in street lines for the Core2 map, built but not
installed.** The owner found the map page black on the bench. That was by design: the live
build drew nothing without a GPS fix or a course, and street context only arrived inside a
host's course package. The repository's street data also stopped short of Manresa Island. The
Core2 source now carries OpenStreetMap outlines for both sites (shop: 600 m square, 3,045
lines; Manresa: 1.5 km square, 1,541 lines, from a new extract fetched that day), draws them
under the live map, and with no fix and no course shows an overview of the last site the kart
was seen at, with “WAITING FOR GPS” and no kart marker. Images are frozen as
`firmware/build/bench-candidates/2026-11-13-site-map/`
([manifest](validation/m5-site-map-2026-11-13.json)); only the three Core2 targets changed,
so the Heltec images stay as they are. **Not flashed anywhere yet.** Offline only: frame time
on a real Core2, colours in sunlight and registration against a real GPS track are unverified.
Manresa's interior is thinly mapped (three service roads, under 30 outlines, the shoreline).
Details: [built-in street lines](../firmware/m5-core2/COURSE_MAP.md#built-in-street-lines),
[Manresa map notes](../pit/server/map/MANRESA-MAP.md).

## Game rules of November 12, on kart 3 since November 13

A review of the FIRE path found three things the owner asked to change. They are implemented,
tested offline and installed on kart 3 (both boards). **The host kart is not updated**, and old
and new firmware cannot play together, so none of the new behaviour has been exercised yet.

| Review finding | State in source |
| --- | --- |
| A boost stayed on the controller if its end could not be written (VESC link down, stale read, Heltec restart) | Fixed: finished once, lower-only, including after a Heltec restart |
| BOOST was an absolute 75% scale: no effect in NORMAL, less power in SPORT | Fixed: a boost is a step up from the mode in force |
| A later BOOST overwrote a running ROCKET | Fixed: a running boost is never weakened or shortened |
| Kart 3 speed caps used kart 2's 2.48 factor with 20 stored poles (caps about 43% high if the motors match) | **Provisional fix, November 13:** `speedcal 1.736` (= 2.48 × 14/20) is stored on kart 3's Heltec, giving kart 2's caps. ECO 0.50 / 15163 and NORMAL 0.75 / 25272 ERPM were written from the Core2 and read back; wheels-up peaks fell from 19800 / 31074 to 14799 / 23556 ERPM. Still to do: confirm by GPS on the road (full pedal in ECO should settle at 15 mph). After any `speedcal` change the VESC keeps the old cap, and the Heltec shows the actual mode as unknown, until a mode is selected |
| One late status line (over 700 ms) ends the Core2 game and clears items | Open |
| 6.5 s without the host's LoRa course packet ends the game | Open (by design; margin is thin) |
| FIRE triggers on a single tap | Open |
| A boost pad entered while a request is pending is spent without effect | Open |

New rules, all owner decisions of November 12 and described in
[the player guide](m5-player-mode.md#native-rules-and-deliberate-limits):

- The host picks the game speed with the kart Pi setting `freeplay_speed` (`eco` or `normal`).
  It is carried in the course package (rules v2), so old and new firmware cannot play together.
- JOIN writes that mode to the player's VESC and locks the Core2 mode buttons to it.
- BOOST is one mode up; ROCKET and STAR are the top mode.
- The "reconnect is read-only" rule has one recorded exception for a missed boost end; see
  `AGENTS.md`.

Still to put on hardware: flash the host Heltec (`kart`) and deploy `kart/server` to the host
Pi from the same commit as kart 3's boards. The host Pi has no screen control for the game
speed yet; it is set in `config.json`.

All eight firmware targets compile from this source. The application images are frozen in
ignored `firmware/build/bench-candidates/2026-11-13-game-rules/`; their hashes and the test
result are in [the manifest](validation/m5-game-rules-2026-11-13.json). Flash from those frozen
files, not from a fresh build (a rebuild embeds different paths and hashes differently). The
host `kart` image for this source is `kart.app.bin` in that folder.

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

The current candidate manifest is
[m5-game-rules-2026-11-13.json](validation/m5-game-rules-2026-11-13.json); the one it replaced on
kart 3 is [m5-player-2026-11-12.json](validation/m5-player-2026-11-12.json). Application binaries
are frozen locally under ignored `firmware/build/bench-candidates/2026-11-13-game-rules/` and
`2026-11-12-player/`; they are not Git deliverables. Rebuild on a fresh machine and record the
bytes actually uploaded.
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

On November 13 his branch was merged again, through **`cb7011c`** (merge `1cabf76`): `core2-items`
0.3.3/0.3.5 and server/pit UI work (rejoin grace after a host reboot, race field, shell targeting).
It touches none of the eight M5 targets. It does change `kart/server`, which the host update
deploys; all 545 tests pass on the merged tree.

Later the same day it was merged once more, through **`0506e57`**: Bluetooth dash speakers and
music, and his Pi server now also steps a carried boost one mode above the requested mode (the
same rule as the native player's BOOST). No firmware changed. Two conflicts: `kart_server.py`
keeps both his `music` setting and our `freeplay_speed` choice, and his new boost test was given
fresh controller state because our freshness guard on `use_item` is retained. 546 tests pass.

A third merge that day, through **`139c810`** (merge `29be4dd`), **does change the Heltec
firmware**: upstream kart 0.3.4/0.3.5 (no Wi-Fi for an empty or sentinel SSID, no driver
reconnect loop, `wifi clear`, and a fixed ESP-NOW channel 1 whenever Wi-Fi is off). His channel
rule was folded into `serviceEspnowChannel()`, which both display variants share. 586 tests
pass and all eight targets compile. The new images are frozen in
`firmware/build/bench-candidates/2026-11-13-upstream-035/`
([manifest](validation/m5-upstream-035-2026-11-13.json)) and **are not on any kart**: karts 3
and 4 still run `2026-11-13-game-rules`. Only the three Heltec kart images differ; the Core2,
base and repeater images are byte-identical, so a later update touches Heltecs only. They
report `kart-0.3.5`, which finally distinguishes them from the installed `kart-0.3.3` builds.

A fourth merge that evening, through **`6e4c788`**, brings upstream kart **0.3.6** (a carried
SHIELD blocks one multiplayer hit), ROAM freeplay, the pit's `fleet_rate` setting and review
fixes to race placing. Three conflicts. In the Heltec sketch his shield-aware `inv` parsing
sits inside our paired-M5 guard, and `invTakeShield()` has a stub returning false in paired-M5
builds, where the Pi inventory does not exist; the M5 player's own shield is unchanged. In
`kart_server.py` his shield spend and TRACK/ROAM modes are kept together with our immediate
zone refresh. 628 tests pass. One image set for hosts and players is frozen in
`firmware/build/bench-candidates/2026-11-13-upstream-036/`
([manifest](validation/m5-upstream-036-2026-11-13.json)): the three Heltec kart images are new
and report `kart-0.3.6`; the Core2 images are the street-line files of `2026-11-13-site-map`
and base and repeater those of `2026-11-13-upstream-035`, byte for byte. **Nothing in it is
on any kart.** It supersedes `2026-11-13-upstream-035` as the build to install.

**A race "did not work" on karts 3 to 5 (owner, November 13).** What was tried and what was
seen is not established. The owner suspected the firmware versions could not talk to each
other; the source and kart 5's own counters say otherwise. The LoRa protocol is unchanged
between the installed `kart-0.3.3` base and 0.3.6, and kart 5's Heltec was hearing the pit
beacon and applied a pit START with a verified NORMAL write while it was checked. What an M5
kart actually lacks is in [the host update plan](host-update-plan.md#what-an-m5-kart-can-and-cannot-join):
the Core2 has **no race screen** (grid hold, countdown, position, laps), a kart not entered at
the pit is sent STOP, track freeplay needs the host update, and **ROAM freeplay cannot be
joined at all** because it has no course to download. Kart 5's Heltec also counted 19% bad
LoRa packets on the bench (7,452 of 40,107), cause not examined.

**Pit-race screen written that evening, not installed.** The owner then said both kinds had
been tried: a pit race and a kart-hosted game. For the pit race the Heltec now tells the
paired Core2 about a grid hold (`race_hold`, `race_go_ms`) and about a GO that released the
kart (`race_went_ms`), and the Core2 shows GRID HOLD with a countdown, GO, and a RACE or
FINISHED chip with the position from the pit beacon. It is display only: no command, mode or
VESC path changed, a stopped kart is never told GO, and the Core2 never shows GO from its own
clock. It has no laps or lap times. 632 tests pass. Images are frozen as
`firmware/build/bench-candidates/2026-11-13-race-screen/`
([manifest](validation/m5-race-screen-2026-11-13.json)): all three Heltec kart images and all
three Core2 images are new, so **both boards of each kart are flashed together**. It
supersedes `2026-11-13-upstream-036`, which was never installed. A bench check after flashing:
with the wheels up, `race 5` on the Heltec's USB console starts a five-second grid hold. The
kart-hosted game is unchanged by this: it still needs the host update, and ROAM still cannot
be joined.

**Kart 3's Core2 has the race-screen build, installed over the air that evening; no Heltec
has it.** The owner asked for an over-the-air update. Three uploads stopped at the tool's
two-minute deadline with the Core2 unchanged; the link was measured at 3 to 8 kB/s, so
`tools/m5/ota_core2.py` now accepts `--timeout` up to 480 s, and the fourth upload was
acknowledged after about three minutes. No USB was connected, so **nothing was checked on a
console**; the owner then reported that the screen looks right, and that is the only check. Two consequences to carry:
kart 3's Core2 now **boots from `app1` (`0x650000`)**, so a later USB update must not simply
write `0x10000`; and with kart 3's Heltec still on the game-rules build the Core2 shows race
position and finish but no countdown or GO. Karts 4 and 5 cannot be updated over the air at
all (nothing provisioned), and kart 3's Heltec asks for an update password that is not held
in any private file. See
[the record](../hardware/m5/2026-11-13-kart3-core2-ota-race-screen/README.md).

**A fifth merge late that evening, through `008b458`: upstream kart 0.3.7 and base 0.2.3.** The
pit can now start or end a freeplay game for the whole fleet with one command (`GK_CMD_GAME`,
id 9), which each kart's Heltec passes to its Pi. A paired M5 kart has no Pi, so on this
branch its Heltec build **refuses** that command and changes nothing, rather than
acknowledging a game it did not join (harness scenario `pit-game`). One conflict, in the
releases note. 635 tests pass. Images are frozen as
`firmware/build/bench-candidates/2026-11-13-upstream-037/`
([manifest](validation/m5-upstream-037-2026-11-13.json)): the three Heltec kart images and the
base image are new (`kart-0.3.7`, `base-0.2.3`); the Core2 and repeater images are the
`2026-11-13-race-screen` files, byte for byte, so kart 3's Core2 already matches. **This is the
set to flash; no Heltec has it yet.** M5 karts still cannot take part in a pit-started game:
the driver would join from the Core2 once the host runs this branch, track games only.

For the host test, mind the channel: Eamon's karts now sit on channel 1 with Wi-Fi off, and
the course download needs the host Heltec and the player's Core2 on one channel. Kart 3's pair
follows its Wi-Fi access point (channel 2 on November 12 and 13), so it will probably need
Wi-Fi off for play (`wifi clear` exists from 0.3.4 on); kart 4 has no Wi-Fi and is on channel 1.

## Next session: coordinated kart3 and host acceptance

**The current plan for the host update is [host-update-plan.md](host-update-plan.md)** (written
November 13, after karts 4 and 5 were brought up). It supersedes the ordering below where they
differ; the detail below is still the reference for each step.

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
   board MAC/role/ID/channel and saves a0600 private plan; it never prints secrets. On macOS it
   reboots both boards when it opens the ports and is then expected to refuse; the provisional
   `tools/m5/pair_course_fallback.py` (same arguments and plan) handles that. Neither tool's
   `--apply` has run on hardware yet.
   Stop the Pi serial owner while provisioning the host from another computer, then restore it.
   The player's own Heltec must be running so Core2 can identify kart3. Kart 3's pair was on
   channel 2 on November 12 and 13 (it follows the Wi-Fi access point); verify the host uses the
   same channel rather than guessing.
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

## Installed on kart 3 — game-rules applications since November 13

| Installed target | SHA-256 | Reports |
| --- | --- | --- |
| Heltec `kart-m5-espnow` | `84e1da0ea79dbd576df5e4adc9bce04e8673aa305441943c29ea86d5bc7b4486` | `kart-0.3.3`, built Nov 12 19:42:53 |
| Core2 `m5-espnow` | `0d904a89671272c08f794e848047e28341e6d232968723afdc3c017054e1a169` | `m5-v1.5`, answers `m5_game` |

Both report the same version strings as the pair they replaced; tell them apart by hash or by
the Heltec's build time. The November 12 pair (Heltec `d4366264…cab9`, Core2 `894a1a34…d3ac`)
was read back from flash before this update and is the rollback; see the
[November 13 install record](../hardware/m5/2026-11-13-kart3-game-rules-update/README.md) and
[the November 12 one](../hardware/m5/2026-11-12-kart3-player-update/README.md). The November 11
observations below were made on the older `4a582f0` pair; identity, the three mode readbacks and
wheels-up forward/reverse were repeated on November 12 and again on November 13 after a VESC
power-up. A power-cycled VESC comes up on its stored limits (scale 1.00, 150000 ERPM) and the
Heltec adopts that as SPORT without writing; the kart stays in SPORT until a mode is chosen.

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
- **Tune writer exists since November 13:** `tools/vesc/apply_fleet_tune.py` writes a prepared
  package once, bound to the kart ID, the stated UUID and the controller's own UUID, with
  ACK, exact read-back and no retry. Each write needs the owner's explicit go-ahead for that
  kart. `apply_tune.py` and `install_rx_filter.py` stay kart3-pinned; do not bypass their pins.
- **Kart 4's VESC has the tune (November 13):** 15 settings changed (the reviewed fields plus
  five protection limits the owner chose), read back, confirmed after a power cycle and a
  wheels-up pedal check. UUID `55004d000951343037353739`. Its stored drivetrain numbers are 14
  poles / 2.769 / 0.083 m, so its Heltec speed factor must be about 0.507, not 2.48 or kart 3's
  1.736. See [the record](../hardware/vesc/kart4/2026-11-13/README.md).
- **Kart 4's boards are installed (November 13):** Heltec `f8:5b:1b:a2:15:50`, Core2
  `3c:8a:1f:d7:51:40`, paired on channel 1, bound to VESC Bluetooth `ec:4b:65:41:40:51` by UUID.
  The read-only checkpoint and a ten-minute soak passed; the Heltec then got the write-capable
  `kart-m5-espnow` build and `speedcal 0.507`. A blank Heltec boots as kart 1 and transmits, so
  its ID was stored first with the new `firmware/provision-kart-id` helper; do the same for
  kart 5. ECO 15163, NORMAL 25272 and SPORT 150000 ERPM were then written from its Core2 and
  read back, wheels up, fault 0; it was left in SPORT. See
  [the install record](../hardware/m5/2026-11-13-kart4-first-install/README.md) for what is
  still open (reverse under the caps, GPS check of the factor, Wi-Fi/OTA, pit commands).
- **Kart 4 has the reverse filter (November 13):** installed with the new
  `tools/vesc/fleet_rx_filter.py` after its switch was observed in both positions, read back,
  and verified armed after a power cycle in forward and reverse, with a pedal check both ways.
  See [the record](../hardware/vesc/kart4/2026-11-13/filter/README.md). No tested removal tool
  exists for it.
- **Kart 5 is at the same point (November 13):** VESC UUID `3d0020000951343037353739` tuned
  (10 settings; its exact read-back failed on one controller-measured offset, was not retried,
  and was confirmed by independent capture and cold boot), boards installed (Heltec
  `a4:cb:8f:a0:20:34`, Core2 `3c:8a:1f:d7:53:44`, VESC Bluetooth `dd:d4:b8:ff:58:f6`, channel 1,
  default speed factor 2.48 because its VESC stores kart 2's numbers), modes read back at
  15163 / 25272 / 150000 ERPM, reverse filter installed and verified armed, ten-minute soak
  passed. Records: [VESC](../hardware/vesc/kart5/2026-11-13/README.md),
  [filter](../hardware/vesc/kart5/2026-11-13/filter/README.md),
  [boards](../hardware/m5/2026-11-13-kart5-first-install/README.md).
- **Open tune question for karts 3–5:** kart 5's bus read 86.4 V for two samples at the end of
  an uncapped wheels-up run with the pack at 83 V (no fault; `l_max_vin` 90 V). See the kart 5
  filter record. Nothing was changed. Until the owner and Eamon decide, avoid uncapped
  full-pedal runs on a freshly charged pack.
- **Still missing on karts 4 and 5:** Wi-Fi and OTA settings, a GPS check of each speed factor
  on the road, pit visibility and pit commands, link-loss checks, and a filter removal tool.
  `apply_fleet_tune.py` treats any read-back difference as uncertain, including a
  controller-measured offset moving by one count; that is safe but will recur.
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
The fallback pairing tool added 18 simulated-board tests afterwards, so the suite now reports 529.

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
