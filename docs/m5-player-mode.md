# Core2 native player and host course sharing

November 12, 2026: implemented in source and offline-tested on `v1.5/m5-core2`.
**Not installed or RF/motor accepted.** The earlier browser rehearsal is synthetic.
See [current handoff](CLAUDE_HANDOFF.md) and [native renderer fixtures](previews/core2-native-player/index.html).

## Ownership

Core2 renders the map, stores a downloaded course, evaluates local item/zone entry and manages
inventory and deliberate JOIN/LEAVE/FIRE. Heltec owns GPS, LoRa, exclusive VESC BLE and all
existing supervisory guards. Wired driving inputs remain VESC-owned. No Pi/SD/cable is added
to the player. Eamon's host Pi authors the course and publishes through its existing USB owner
to its host Heltec. Core2 has no host or course-editing function.

## Implemented path

1. Host Pi runs the updated `kart/server` (including `m5_course.py`) and a running freeplay
   host session. Its Heltec runs this branch's `kart` build and has course peers provisioned.
2. Pi exports the course, start/finish, boost/mud/item zones and up to 64 nearby OSM line
   segments. USB publication is ACK-paced. Host pause/end withdraws the publication; a new
   session/explicit republish gets a new random instance. No second serial process is opened.
3. A paired nearby Core2 sees an invitation. JOIN downloads from host Heltec over ESP-NOW,
   validates the complete package and writes/readbacks an inactive NVS slot before committing
   its selector. A bad download preserves the previous course. No SD or flash erase is needed.
4. The explicit JOIN gesture then requests that host session through the Core2's own encrypted
   Heltec link. Playing begins only on the returned session/result. A failed/unavailable JOIN
   requires another deliberate press; a cached map never automatically joins.
5. Fresh GPS selects boxes and the nearest same-session shell target within 25 m. FIRE sends
   one typed, token-bound request to own Heltec. Heltec independently rechecks identity,
   freshness, session/generation, STOP/GRID, pending writes, baseline and target range.
6. Heltec uses Eamon's existing attack/ACK and bounded temporary BOOST/SLOW paths. No saved
   tune, throttle command, firmware update or generic USB console string is accepted here.

The real map draws cached context, course, S/F and zones beneath fresh kart markers. It follows
own GPS in a north-up 70 m view. DASH/MAP toggles and the invite button consume whole touches.
Small GPS MPH/pack volts and compact FIRE retain Hunter's cyan/amber design. Credits appear
for five seconds at startup. Host loss, generation change, own Heltec reboot/link loss and OTA
cancel local game intent/inventory, with no control replay or driving-state restoration.

## Package, trust and compatibility

- Binary `GKG1`, rules v1, little-endian WGS84 e7 coordinates, bounded counts and CRC32.
  Maximum 3,684 bytes: 128 track points, 16 zones, 64 background segments. The host's routes
  up to 200 points use Eamon's Douglas–Peucker at a fixed 1 m tolerance; if still over128,
  publication refuses with an error instead of silently increasing distortion.
- Circle/polygon boost/mud/item zones and one segment lapline are supported. Unknown rules,
  zones, invalid geometry, oversize data, wrong host and bad CRC are refused.
- `GCS1` ESP-NOW uses 192-byte data chunks, fresh 64-bit download challenge, host boot/digest
  binding, bounded timeout/retries and per-peer HMAC-SHA256 truncated to128 bits. Keys are
  separate from the encrypted own-kart pairing. Course peers cannot send control frames.
  Both radios must already share a channel. The course service does not hop away from own Heltec.
- Course-only pairing uses `share pair ID MAC KEY` over USB, namespace `coursepeer`; it never
  replaces the existing control peer/callback. `share status` emits `share_radio` plus `share`.
- LoRa telemetry stays 46/47/54 bytes and commands stay14. New optional `GK_MSG_COURSE=5`
  carries a 14-byte header+package digest+host boot. Once per2s a publishing host substitutes
  this for one scheduled telemetry transmission; no extra slot or longer airtime is added.
  At2Hz host telemetry averages1.5Hz, at1Hz it averages0.5Hz. Other karts keep their rate.
  Legacy base/repeaters ignore type5. For relayed course-generation coverage, update the
  repeater too; direct host-player LoRa is enough for the first test. The pit need not change
  to keep existing telemetry/control. New COURSE handling does not add LoRa authentication;
  it retains the existing fleet radio trust model.
- Generation freshness expires after6.5s. Rolling sequence/retired boot checks suppress
  reordered/duplicate identities. JOIN/FIRE binds package digest **and** host boot, received
  through the authenticated local link. Gameplay thus continues outside ESP-NOW download
  range while fresh host LoRa remains available. Identity loss ends the local game, not driving.
- Package stores are in Core2 `m5game`, two blobs plus atomic selector. Loading is read-only;
  NVS exhaustion/readback failure prevents activation. Physical power-loss/space acceptance
  still needs hardware. Pairing, OTA secrets and vehicle NVS are separate and preserved.

## Native rules and deliberate limits

The roll weights match Eamon's current multiplayer table: boost22, shell24, lightning12,
rocket8, boost3 6, star6, shield8, magnet6, empty8 percent. Shell and lightning occupy the
separate attack slot; three other carried slots use oldest-first FIRE. Shell uses nearest fresh
same-session peer within25m; lightning uses existing all-peer attack semantics. BOOST is7s at
75%, ROCKET10s at100%, BOOST3 has three7s charges, STAR8s at100% plus immunity, MAGNET20s
doubles circular item pickup range. SHIELD is explicitly armed with FIRE and blocks one
incoming hit or mud application. Existing controller ceilings and pit restrictions win.

This is a light native player, not full Pi game parity:

- Fixed-duration boosts do **not** stack speculative remaining time. Refused/unknown commands
  cannot lengthen a later boost. A transmitted item is consumed even if refused/unknown, with
  no automatic retry; a busy local radio that never sends retains the item.
- Shared boxes are the published starting snapshot, with per-player entry/cooldown. Pi-local
  randomized box respawns are not broadcast continuously. A full native inventory drops a
  new carried item instead of automatically applying it. Inventory does not survive reconnect,
  course change or reboot. Hotlap/race ranking/global pickup arbitration are outside this version.
- S/F counts/times local crossings; it is not pit-authoritative race ranking. No photographic
  map tiles or Google Maps. OSM context is limited to geography already present in the host
  repository; an uncharted location can have course/zones but no surrounding line work.
- One fresh paired host invitation is selected at a time; there is no multi-host browser.
- FIRE acceptance means the local Heltec accepted an attack/effect request. It does not prove
  the remote kart was slowed; inspect LoRa attack ACKs and actual VESC readback during acceptance.

## Deployment and first test

Build application targets `m5-espnow` (Core2), `kart-m5-espnow` (commissioned player Heltec),
and `kart` (host Heltec), plus deploy updated host Pi server files. Generic `core2-items` is a
different Pi-dependent product. Preserve each device's NVS and record application hashes.
Do not overwrite Eamon's kart1/2 firmware while he is using it; coordinate the host deployment.

1. While stationary, keep existing own-kart pairing. Read `share status` on host Heltec and
   Core2 to obtain Wi-Fi station MACs/channel; confirm kart IDs with normal `status`.
2. Generate a private course-only plan (default opens no device):

   ```sh
   python3 tools/m5/pair_course.py --host-id 2 --kart-id 3 \
     --host-mac HOST_WIFI_MAC --core2-mac CORE2_WIFI_MAC \
     --plan firmware/build/bench-private/course-2-3.json
   ```

   Stop the host Pi's serial service while USB provisioning from a computer. Rerun the same
   command with `--apply --host-port /dev/cu.HOST --core2-port /dev/cu.CORE2`. It verifies both
   identities and channel before writes, records secrets0600, and does not reboot either board.
   Restart accessories while stationary; restore the host Pi's sole serial ownership. Each new
   player needs its own pairwise key. Use the original private plan for recovery, never Git.
3. Host a course. Updated Pi publishes automatically once host/package/peer service is ready.
   Optional local retry: `POST /api/m5/course/publish` under existing command access controls.
   `share status` on host reports package bytes; Core2 `status` emits `m5_game` progress/digest.
4. First prove download, cache across a Core2 restart, cancel, wrong channel, interrupted
   transfer and new-course replacement. No motor test is implied by a complete download.
5. With operator/wheels lifted/pedal released/cutoff, verify VESC identity and fresh mode
   state, explicit JOIN, GPS pickup, one FIRE, exactly one command outcome, pit precedence
   and loss/recovery without replay. Use a second participating kart for shell/lightning ACKs.
6. Accept kart3 first. Only then provision4/5 with separate IDs/pairings and target-specific
   VESC calibration/tune preparation. USB remains the supported VESC tune/Lisp maintenance path.

Offline coverage: Python exporter/publisher and actual host lifecycle; native package transfer,
retry/corruption/cache and live player state under ASan/UBSan; production `.ino` dispatch,
fresh-generation/STOP/SLOW/duplicate guards; existing full protocol/UI/transport suites.
Physical ESP-NOW/LoRa transfer, LCD/touch/NVS power-loss behavior and motor effects remain untested.
