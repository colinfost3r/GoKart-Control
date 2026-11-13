# Host update plan: first course download, JOIN and FIRE with the M5 karts

Written 2026-11-13, revised that evening for Eamon's kart 0.3.6 and again for 0.3.7. A plan for Colin and Eamon to
agree on; nothing in it has been done.

## Why this is needed

Karts 3, 4 and 5 are ready on the bench: tune, reverse filter, paired Heltec and Core2, modes
and speed caps. None of the game has run on hardware, because an M5 kart gets its course from a
**host kart**: a Pi kart whose Heltec sends the course to each player's Core2. Until a host runs
software from this branch, the M5 karts cannot download a course, JOIN or FIRE, and their map
page has no course or zones. (The Core2 build of November 13 with built-in street lines shows
the shop's and Manresa's outlines without a host; that is context only.) The course package
is rules version 2, so a host on older software is refused.

## What changes on the host kart

Everything below comes from `v1.5/m5-core2`, which already contains
`eamon/firmware-lora-starter` through `008b458` (kart 0.3.7 and base 0.2.3: the pit can start a
freeplay game for the whole fleet; before that 0.3.6: shield blocks a hit, ROAM freeplay, pit
`fleet_rate`). One build for everyone: the host gets Eamon's newest work plus the
M5 player support, and the players get the same source.

| Part | Change | Size of the difference from Eamon's branch |
| --- | --- | --- |
| Host Heltec | `kart` application, frozen as `2026-11-13-upstream-037/kart.app.bin` (reports `kart-0.3.7`), written at `0x10000` only | `kart-heltec-v4.ino` +513 / −40 lines, plus the `M5Game` library and a small `VescLink` change |
| Host Pi | `kart/server` deployed with `kart/deploy.sh gokart-kart-N.local` | `kart_server.py` +124, `kartcore.py` +131, new `m5_course.py`, `static/app.js` +22 |
| Host Pi config | `"freeplay_speed": "eco"` or `"normal"` in `/opt/gokart-kart/server/config.json` | one setting; there is no screen control for it yet |
| Host Heltec settings | one course-only pairing per player Core2 (`tools/m5/pair_course.py`) | does not touch the kart's own pairing or the VESC |

**This is more than adding a feature to Eamon's kart.** Much of the Heltec difference is
supervisory code that also runs in the plain `kart` build, and `kartcore.py` keeps this
branch's rule that an item can only be used on fresh controller state. Eamon should read the
diff and run his own game on the updated kart before the M5 test starts:

```sh
git diff origin/eamon/firmware-lora-starter..origin/v1.5/m5-core2 -- \
  firmware/kart-heltec-v4 firmware/libraries/VescLink kart/server
```

Unchanged on the host: its VESC and tune, its own Core2 item screen pairing, the pit base and
repeaters, kart ID and Wi-Fi settings.

## Decisions before the day

1. **Which kart hosts.** Kart 1 or kart 2. It must have a GPS fix: a freeplay course is set by
   driving one lap.
2. **Eamon's go-ahead** for the firmware and server on that kart, after reading the diff above.
3. **Player Heltec firmware.** Recommended: move karts 3, 4 and 5 to
   `2026-11-13-upstream-037/kart-m5-espnow.app.bin` first (and their Core2s to that folder's
   `m5-espnow.app.bin`, which adds the built-in street lines and the pit-race screen). The course download needs the host
   Heltec and the player's Core2 on the same radio channel. With Wi-Fi off the host sits on
   channel 1, as do karts 4 and 5. **Kart 3 follows its Wi-Fi access point (channel 2)** and has
   no clean way to turn Wi-Fi off on its current build; the merged build adds `wifi clear`.
   That image is tested offline only, so each kart needs a short VESC-on mode check after it.
4. **Game speed:** `eco` or `normal`.
5. **The 86.4 V reading.** ROCKET and STAR lift a kart to the top mode, which has no speed cap.
   Kart 5's bus briefly read 86.4 V at the end of an uncapped run on a near-full pack
   ([record](../hardware/vesc/kart5/2026-11-13/filter/README.md)). Decide how to handle that
   before boosted driving on freshly charged packs: for example start below full charge, or
   keep the first sessions wheels-up.

A possible alternative to using Eamon's kart is a bench host: this branch's server on a Pi or
the Mac with a spare Heltec on the `kart` build. It is **unverified**, needs a spare Heltec and
would still need GPS to set a course. Worth a look only if Eamon's karts cannot be spared.

## Steps on the day

**A. Players, on the bench (Colin, about 10 minutes per kart).** For each of karts 3, 4, 5:
read back and keep the current Heltec application, write the merged `kart-m5-espnow` image at
`0x10000`, confirm kart ID, `writes:true`, UUID pin and speed factor are unchanged, hold ECO,
NORMAL and SPORT with the wheels up and check the read-backs (15163 / 25272 / 150000 ERPM). On
kart 3 also run `wifi clear` and confirm its pair moves to channel 1.

**B. Host, with Eamon at the kart.**
1. Read back and keep the host Heltec's current application; note the Pi's current commit.
2. Write `kart.app.bin` at `0x10000`. Confirm kart ID, VESC identity and `kart-0.3.7`.
3. `kart/deploy.sh gokart-kart-N.local`, set `freeplay_speed`, restart the service.
4. **Eamon runs his own checks** on that kart: Core2 item taps, a carried boost, pit STOP and
   START. Stop here if anything differs from before.

**C. Course pairing, once per player, both karts next to the Mac.**
1. `share status` on the host Heltec and on the player's Core2: note both MACs and the channel.
2. `pair_course.py --host-id H --kart-id N --host-mac … --core2-mac … --plan <private file>`.
3. Stop `gokart-kart` on the Pi, then rerun with `--apply` and both USB ports. On macOS the tool
   is expected to refuse after rebooting the boards; `pair_course_fallback.py` takes the same
   arguments. Neither `--apply` has run on hardware yet.
4. Restart the boards, restart `gokart-kart`, confirm `share status` lists the peer on both.

**D. Outdoors, karts stationary first.**
1. Host: freeplay on, drive one lap to set the course. `share status` on the host should report
   the package size.
2. Player: tap JOIN. Watch download progress, then the course line on the map.
3. Prove the download survives a Core2 restart, a cancel, an interrupted transfer and a new
   course replacing the old one.

**E. Game, wheels up before any driving.**
1. JOIN writes the game speed to the player's VESC and locks its mode buttons; confirm by
   read-back and by trying another mode.
2. One FIRE with a BOOST: one mode up for 7 seconds, then back, exactly one command outcome.
3. One hit between two karts (shell or lightning) with its acknowledgement.
4. Pit STOP and SLOW take precedence; a lost link does not replay anything.
5. Only then slow supervised driving.

## Rollback

- **Host Heltec:** write back the application read in step B1. Eamon's release image
  `firmware/releases/kart-heltec-v4-ble-0.3.7.merged.bin` is the fallback.
- **Host Pi:** `kart/deploy.sh` from a checkout of `eamon/firmware-lora-starter`; the Pi's
  `config.json` is kept by the deploy script.
- **Course pairing:** stays on the boards and is ignored by older firmware. The private plan
  files are the record.
- **Players:** write back the applications read in step A.

## What an M5 kart can and cannot join

Checked in the source on November 13, after the owner reported that a race "did not work" on
karts 3 to 5. Which of these was tried, and what was seen, is **not established**.

| Game | M5 kart today | What it needs |
| --- | --- | --- |
| Pit race (START RACE at the pit) | Takes part at the radio level: the Heltec holds the kart at the grid and releases it at GO, and the pit counts laps from its GPS. **The Core2 on karts 3 to 5 shows none of it**: no grid hold, countdown, position or finish. A kart that is not in the pit's entered list is sent STOP | The race screen written on November 13 evening (both boards of each kart, from `2026-11-13-upstream-037`; only kart 3's Core2 has it so far, and no race has been run with it). It shows the hold with a countdown, GO, position and finish; **no laps or lap times**. At the pit: the kart toggled as entered |
| Freeplay on a track, hosted by a Pi kart | Cannot join until the host runs this branch | This plan |
| Game started from the pit for the whole fleet (Eamon's kart 0.3.7, November 13) | **Does not join.** The pit's command is carried out by a kart's Pi, which an M5 kart does not have. On this branch's build its Heltec answers the command as refused, so the pit shows that the kart is not in the game; on the builds installed today it is acknowledged and ignored | The driver joins from the Core2 once the host runs this branch (track games only). Joining automatically on the pit's command is not written |
| ROAM freeplay (Eamon, November 13) | **Cannot join.** ROAM has no course, and an M5 kart joins by downloading one; the host refuses to publish and logs `m5_course_publish_refused` | New design work on the Core2 |

The radio link itself is not the problem: kart 5's Heltec, on its November 13 build
(`kart-0.3.3` base), was hearing the pit beacon and applied a pit START with a verified NORMAL
mode write while this was checked. Eamon's firmware changes from 0.3.3 to 0.3.7 are the pit game command, the item
screen's ESP-NOW channel, Wi-Fi handling and the shield; none changes the LoRa protocol.
One thing to watch: that Heltec counted 7,452 bad packets in 40,107 received (19%) on the
bench, cause not examined.

## What this does not cover

Wi-Fi and OTA settings on karts 4 and 5, GPS checks of the three speed factors, a removal tool
for the reverse filter, and the open review findings listed in the
[Claude handoff](CLAUDE_HANDOFF.md) (a late status line ending the game, the 6.5 s host timeout,
FIRE on a single tap).
