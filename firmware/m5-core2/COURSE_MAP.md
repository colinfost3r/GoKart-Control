# Core2 course map without a Pi or SD card

This is a display-only implementation. It has offline tests and requires a new Core2 build;
**it has not been flashed or physically accepted by this change**. Heltec firmware, pairing,
LoRa protocol and VESC settings are unchanged. FIRE is visibly unavailable until an
authoritative item/session implementation is connected; touching it sends nothing.

The display starts on a north-up map that follows its own fresh position. The map shows
70 metres vertically. Distant peers do not shrink the view; only fresh markers inside it
are drawn. The own marker has a white ring. Course lines are clipped to the map area.
The upper-right DASH/MAP button toggles between the driving view and the telemetry/mode screen.
The Hunter-style renderer is shared with the [offline rehearsal](../../docs/m5-offline-rehearsal.md).
Hold the top status header for 1.8 seconds to open the existing OTA maintenance screen.

A valid GPS fix is still required to follow the kart. Without one, a stored course is shown
as an overview with “Own GPS unavailable”. With neither a course nor own fix, the display
says it is waiting; it never invents a position or follows a different kart. Without a course,
a valid own fix still produces the numbered marker and “GPS only”. No road image, external
server or base station is needed for this local display.

## Provision an outline over the Core2 USB port

The existing pit editor's `zones.track` is the source format. Export the intended real course:

```sh
python3 tools/m5/export_course.py --zones /absolute/path/to/zones.json \
  --name 'Course name' --out /tmp/course.json
python3 tools/m5/provision_course.py --course /tmp/course.json
```

The second command only validates and prints a summary. It opens no device. The repository's
`pit/server/map/zones.json` is a **shop demonstration**, not a surveyed Manresa Island course.
Do not install it under a misleading course name.

To install an explicitly chosen outline, use the Core2's USB port and its actual fleet ID:

```sh
python3 tools/m5/provision_course.py --course /tmp/course.json \
  --port /dev/cu.ACTUAL_CORE2_PORT --kart-id 3
```

The tool checks `m5_status`, display firmware/transport, course protocol1 and kart ID before
uploading. The paired Heltec must have identified this display's kart; unknown ID0 is refused.
This is not the Heltec port or the VESC port. Uploads are refused during display maintenance.
The tool does not change firmware, radio keys, Wi-Fi credentials, modes or motor settings.
It uses POSIX termios without DTR/RTS operations and disables hangup-on-close.

A validated course replaces the active outline immediately and is saved in its own
`m5course` NVS namespace as one bounded, versioned, CRC-protected blob. Commit reports success
only after readback matches. A malformed/incomplete/expired upload leaves the previous active
course intact. A failed commit/readback is **unknown**: stop, inspect `course status`, and do
not retry blindly. Software tests cover failed writes and lost readback; they are not a
physical power-interruption acceptance test of the NVS storage.

Internal storage takes precedence over the optional SD `/gokart/course.json`. SD is still
read only at boot; its valid outline is retained as a fallback. `course clear` deliberately
removes the internal outline and selects that already-loaded SD fallback, or GPS-only if
none exists. It does not touch pairing or maintenance configuration. A restart reloads SD.

## USB protocol and diagnostics

All course commands are accepted **only by the Core2 physical USB parser**:

```text
course status
course begin <JSON-byte-count> <8-hex-digit-CRC32>
course chunk <zero-based-byte-offset> <hex-encoded-bytes>
course commit
course abort
course clear
```

Limits: schema1, 2–128 distinct-position points, finite latitude/longitude in range, a
1–40-byte name without control characters, JSON≤8192 bytes, chunks≤128 bytes, and one
30-second upload window. Chunk offsets must advance exactly; no duplicate/retry queue exists.
The helper canonicalizes coordinates to1e-7 degrees and emits seven decimal places so the
board and host compute the same record CRC. The record holds at most1076 bytes; it contains
no secrets. Existing SD outlines retain their schema1 format. Course upload never travels
through ESP-NOW or the Heltec maintenance console.

`status` now reports `course_proto`, `course_source` (`internal`, `sd`, `none`),
`course_points`, `course_error`, `gps_reported_fix`, `gps_fresh`, `gps_has_position`,
`gps_position_age_ms`, `gps_sats`, `parse_errors` and `map_follow`. `course status` also gives
the course name, record CRC and upload progress. These separate missing course data from a
missing/stale/invalid own GPS fix. No motor temperature is inferred.

## Offline checks and bench acceptance

```sh
python3 -B firmware/m5-core2/tests/test_map_course.py
```

The tests exercise projection/clipping, stale GPS and clock wrap, no-SD own-position display,
distant-peer zoom independence, malformed courses, CRC corruption, bounded uploads, storage
write/readback failures, Python/C++ record compatibility, default-offline provisioning and
FIRE touch isolation. The existing mode tests remain applicable; FIRE does not call them.

Before deployment acceptance: preserve the installed image, compile all three Core2 targets,
then use a supervised display update. Verify own marker with no SD, the intended internal
course after reboot, malformed-upload preservation, outdoor following, clipping, DASH modes,
OTA access and reconnect without any automatic mode command. This change alone does not
establish GPS accuracy, range, full-fleet operation or game functionality.
