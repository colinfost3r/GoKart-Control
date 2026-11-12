# Core2 player mode and host course sharing

Owner decisions: November 11, 2026. **Design/implementation brief, not deployed firmware.**
This supersedes the earlier suggestion to put native map/inventory logic on the Heltec.
The current no-SD follow map is implemented but not installed; JOIN, native inventory,
FIRE and wireless host-course downloads remain to be implemented.

## Responsibility split

| Component | Responsibility |
| --- | --- |
| Core2 | Store the course; render the following line map and Hunter-style DASH/GAME pages; place markers from fresh Heltec GPS/fleet data; detect local course/item interactions; manage player inventory and user intent; request JOIN/LEAVE/FIRE. No hosting or course authoring. |
| Own Heltec | GPS, VESC BLE, LoRa fleet/session/attack transport, validation and arbitration of supervisory requests, verified results back to Core2. Remains the only accessory allowed to talk to the VESC. |
| Host Pi and host Heltec | Existing course authoring/game hosting, plus a new course publisher/export bridge. Host capability is required; the current upstream image does not provide this download service. |
| VESC | Wired pedal/reverse, motor loop and protections. Map rendering or UI failure must not alter driving. |

Core2 can own application/game state without owning motor control. Requested effects go
through typed, bounded, fresh authenticated messages to the Heltec's existing command policy.
Do not route display input to the unrestricted USB console or open a second VESC connection.
Use Eamon's item IDs, quantities/charges, targeting and session rules; port the relevant Pi
logic with equivalent tests instead of creating a separate incompatible item system.

## Proposed course download path

```text
Host creates/publishes course on its existing Pi
    -> host Heltec over USB (new bounded publishing bridge)
    -> joining Core2 over ESP-NOW while nearby (new course-only peer/service)
    -> validated local course cache; Core2 renders and runs player logic

Own Heltec <-> Core2: existing encrypted telemetry/request link remains
Kart-to-kart during play: existing Heltec LoRa session/position/attack protocol
```

The owner requests downloading the host's course after creation, rather than manually
preloading every player. For the first implementation, JOIN initiates synchronization;
READY is shown only after the intended course is complete, validated and saved, and session
join has been acknowledged. A cache hit requires matching host, course revision and digest.
No Core2 HOST, draw-track, create-course or edit-box controls are added.

Implementation constraints (proposed contract, not existing wire fields):

- Package geographic track points, supported boxes/zones, lap/start geometry and gameplay
  metadata actually required by the selected game; no aerial tiles. An outline alone is
  insufficient for matching host item locations. Preserve coordinates/units/IDs/rules from
  the source. A WGS84 course must not be replaced by the illustrative SoNo art/demo loop.
- Manifest binds publisher/host ID, game instance, schema, course ID/revision, byte count,
  content digest and required capabilities. Reject unsupported effect/rule types visibly;
  do not silently omit them and claim full compatibility. Define bounded package limits
  against real Eamon course exports before fixing the new schema/storage format.
- Use small numbered chunks, application acknowledgements, bounded retries and final
  digest/schema checks. Retrying course data is allowed; it must never replay a motor/game
  command. Stage separately and retain the old valid course until successful commit/readback.
  Existing USB outline schema1 is not a full game package; preserve its migration/fallback.
- Source authentication is separate from a checksum. Provision course-peer trust separately
  from each kart's private Core2/Heltec control keys; never publish keys or reuse another
  kart's control credentials. A course-only peer must not be able to send mode/FIRE commands.
- Extend one ESP-NOW dispatcher to distinguish the existing local peer from a course publisher;
  do not install a second callback that steals the paired display link. Host builds must
  also preserve Eamon's existing Pi/item-screen ESP-NOW service. Keep telemetry and
  control priority over bulk transfer, use bounded queues, initially serve one downloader at
  a time, and pause/abort downloads during maintenance or channel misalignment.
- All participating Wi-Fi/ESP-NOW radios must share the transfer channel. Reconcile host,
  own Heltec and Core2 channel configuration before transfer; do not hop away from the working
  local pair to download. ESP-NOW is a nearby provisioning path, not a LoRa-range promise.
- A host may be heard over LoRa while out of ESP-NOW reach: show HOST AVAILABLE / MOVE CLOSER
  or DOWNLOAD UNAVAILABLE, never READY. Once cached, map rendering does not need ongoing
  ESP-NOW contact with the host. Live gameplay still follows the LoRa session freshness rules.
- Do not switch an active course silently when the host edits it. Show UPDATE AVAILABLE and
  apply a deliberate stopped/staging rejoin flow. A download/reboot/reconnect alone neither
  joins a game nor changes modes. No queued FIRE or effect request is replayed after recovery.

## Two-page UI and notification

Both pages follow Hunter's original graphics at `315710e`, refined through `5629924`:
`kart/server/static/retro.css`, `display.js`, `instruments.js`, and `font-segments.css`.
The current upstream restyle rollback is not the requested aesthetic reference. Adapt the
segmented numerals, restrained cyan/amber palette, muted labels, clear state colors and
instrument organization to 320x240. Preserve the DSEG license if its glyphs are used.
Course geometry remains a simple line; SoNo artwork is not the Manresa route.

- DASH: existing telemetry, truthful unavailable/stale fields, verified mode controls.
- MAP/GAME: own-kart follow map, nearby players and one prominent item/FIRE control; keep
  game join/details in an overlay so they do not consume the driving map permanently.
- A dedicated edge button toggles DASH and MAP/GAME. Page changes send no mode/join/fire
  request and cancel in-progress control holds; one touch cannot activate both pages.
- Fresh joinable-host notification: a pulsing on-screen dot next to that button, a short
  invitation label and optional one-shot vibration. Opening it shows the host(s), course
  download state and an explicit JOIN action. Acknowledging/dismissing stops the repeated
  flash for that invitation; changed/new invitations can notify again. Clear stale invites.
- The stock Core2 v1.3 has power/reset hardware buttons and three front virtual touch
  buttons. The proposed first version uses the screen edge button/dot; it does not assume
  a dedicated physical side-button LED exists or repurpose reset/power. A front touch-button
  shortcut can be added after checking mounted access. Swipe is optional, not required.
- Existing LoRa `session == host ID` advertises a freeplay game. Do not confuse this with
  pit grid/countdown or report a scheduled race from that byte alone. Support explicit
  published-game metadata for richer race labels; leave current pit control precedence intact.
- Host presence does not imply a fresh GPS fix, usable course or accepted join. Show those
  states separately. Notification loss or leaving the map must not affect normal driving.

## Implementation and acceptance order

1. Port Hunter presentation and page/notification state; simulate available/expired hosts,
   missing GPS, download progress and touch conflicts without opening device ports.
2. Define the host export and versioned game package against Eamon's actual course/item data.
   Add publisher + authenticated ESP-NOW course transfer + Core2 persistence together.
3. Port player logic to Core2 and add typed session/inventory/effect requests/results across
   the own-Heltec link. Preserve full pit arbitration, dedupe, expiry and no reconnect replay.
4. Offline failure tests: truncated/corrupt/duplicate packages, wrong host/keys, revised course,
   power interruption, unsupported rules, channel mismatch, two invitations and no stale FIRE.
5. Supervised display-only test: real course, outdoor own/peer GPS, download then reboot/cache,
   page button/invite, host loss and telemetry latency during download. No motor effects.
6. Two-kart game acceptance with Eamon's updated host; only then separately commission real
   motor effects. Existing kart3 tune/filter/profile acceptance remains the baseline.

As inspected: our branch has Eamon through `a5a4c22`; upstream is `59976df`, with newer
inventory/timing and separate Pi-dependent Core2 power/OTA work. Review/integrate those
changes as part of implementation; this brief does not merge them or flash either accessory.

Technical references: [M5 Core2 v1.3 hardware](https://docs.m5stack.com/en/core/Core2_v1.3),
[ESP-NOW channel/peer/packet constraints](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32/api-reference/network/esp_now.html).
These describe hardware/API capabilities, not measured project range or transfer performance.
