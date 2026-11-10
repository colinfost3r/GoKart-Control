# Tools

| Path | What it is | Needs |
| --- | --- | --- |
| [`run_tests.sh`](run_tests.sh) | Runs every offline test suite, prints a summary table | Python 3.9+, pyserial |
| [`bench/e2e_bench.py`](bench/e2e_bench.py) | Live check of the whole chain: pit server -> T-Beam -> LoRa -> kart Heltec -> kart Pi | The pit Pi, a powered kart |
| [`m5/ota_core2.py`](m5/ota_core2.py) | Password-protected Core2 application update with exact image SHA-256 and bounded uploader process | `m5-espnow` maintenance enabled, private credentials JSON, official ESP32 3.3.8 `espota.py` |
| [`vesc/`](vesc/README.md) | Read-only VESC capture (allowlisted command ids 0, 4, 14, 17) and offline decoder | A VESC on USB for capture; nothing for decode |

The SD card kits and deploy scripts live with their component (`pit/sdcard`, `kart/sdcard`,
`firmware/build.sh`); they are summarised at the end of this file.

## run_tests.sh

```sh
tools/run_tests.sh                  # every suite
tools/run_tests.sh pit kart-core    # suites whose name starts with these words
tools/run_tests.sh -v               # print each suite's output, not only failures
```

| Suite | Command (from the repo root) | Typical time |
| --- | --- | --- |
| `vesc-tools` | `python3 -I -m unittest discover -s tests -p test_*.py` | < 1 s |
| `pit-core` | `python3 -I pit/tests/test_core.py` | < 1 s |
| `pit-e2e` | `python3 -I pit/tests/test_e2e.py` (starts the simulator + server on free ports) | ~90 s |
| `kart-core` | `python3 -I kart/tests/test_core.py` | < 1 s |
| `kart-mapsync` | `python3 -I kart/tests/test_mapsync.py` | ~5 s |
| `kart-e2e` | `python3 -I kart/tests/test_e2e.py` | ~65 s |
| `firmware` | `python3 -I -m unittest discover -s firmware/tests` (only if that folder exists) | |

It runs from the repo root whatever directory you call it from, uses `python3 -I` (no
user site-packages, no script-directory imports), and prints a table of result, test count,
skipped count and time per suite. Exit status 1 if any suite fails, times out, or a name
filter matches nothing. Failing suites print their last 40 lines; full logs go to a temporary
folder printed at the end.

Environment: `PYTHON=python3.11` picks another interpreter; `SUITE_TIMEOUT=600` (seconds, per
suite) kills a hung suite together with any simulator or server it started.

No hardware and no network access are needed. Run it before every push (see
[CONTRIBUTING.md](../CONTRIBUTING.md)).

## bench/e2e_bench.py (live bench)

Run it **on the pit Pi**: the pit server trusts localhost, so no login is needed. `pit/deploy.sh`
does not copy `tools/`, so copy it over:

```sh
scp tools/bench/e2e_bench.py pit@gokart-pit.local:/tmp/
ssh pit@gokart-pit.local python3 /tmp/e2e_bench.py --kart 2
```

Options: `--kart N` (default 2), `--pit URL` (default `http://127.0.0.1:8080`), `--kart-url URL`
(default `http://gokart-kart-N.local:8081`, falling back to the hostname and a couple of fixed
LAN addresses when `.local` does not resolve from the pit), `--allow-writes`.

It prints one PASS / FAIL / SKIP line per check and a total; exit status 1 on any FAIL. Checks:
pit T-Beam link, radio `stat` fresh, beacon counter moving, kart online with loss under 5 %,
repeater heard (skipped if none), ping applied, kart Pi API reachable and hearing its Heltec,
5 Hz GPS line and quality fields, zones version synced to the kart, race command outcome and the
kart display seeing countdown + GO, then slow / boost / stop / start.

**VESC writes.** slow / boost / stop / start are sent only when the kart's VESC is not linked
(they must come back `no_vesc`) or with `--allow-writes`. The race check is not gated: it always
sends `race 3`, which on a kart with a linked VESC holds the current scale at 0 for about 3 s and
then restores it. Run it with the drive wheels off the ground or the VESC unlinked.

Last recorded run: 16 checks pass on kart 2, 2026-11-06 (commit cc5c406).

## Core2 OTA

`m5/ota_core2.py` updates only the Core2 display application. It does not provision Wi-Fi,
pair ESP-NOW, modify the Heltec, or issue VESC commands. Use the `m5-espnow` build and enable
its explicit ten-minute maintenance window first. Hold the top status bar for 1.8 seconds,
then tap ENABLE UPDATES, or use Core2 USB `ota on`; wait for `ota status` with `ready:true`.
Maintenance is off on every boot. No SD card is involved. See the [Core2 setup guide](../firmware/m5-core2/README.md#core2-maintenance-and-ota)
for USB provisioning and [bring-up checks](../firmware/m5-core2/BRINGUP.md#core2-ota-check).

From the repository root:

```sh
python3 tools/m5/ota_core2.py \
  --host gokart-display-3.local \
  --image firmware/build/m5-core2-m5-espnow/m5-core2.ino.bin \
  --credentials firmware/build/bench-private/core2-ota-private.json \
  --espota /path/to/esp32/3.3.8/tools/espota.py
```

All four arguments are required; replace example file paths with the actual files. The
credentials JSON must belong to the current user, have no group/other access (`chmod 600`),
and contain `ota_password` matching the Core2's saved configuration. Keep it in an ignored
private directory, never Git. The helper is standard-library Python; it imports the official
local uploader in a child process and sends the password through stdin instead of argv or the
environment. Raw uploader output and credentials are not printed.

The image must be a Core2/ESP32 **application** `.bin`, not a Heltec/S3, bootloader or merged
image. A private immutable snapshot is hashed, and the exact SHA-256/byte count is printed
before upload. Authentication is required with the current SHA256 protocol; an unauthenticated
target or legacy downgrade is refused. Success requires the official uploader's explicit
acknowledgement, not just its exit code. `--timeout` accepts 1–120 seconds and defaults to 120;
a deadline or interruption terminates the worker. Verify device state before retrying an
uncertain transfer. USB recovery and post-reboot telemetry checks remain separate.

Core2 follows the AP channel while maintenance is active, so ESP-NOW telemetry can pause;
normal discovery resumes after disabling updates or reboot. Driver mode requests are blocked
throughout maintenance. An OTA acknowledgement is not proof of an observed reboot or restored
telemetry; those hardware checks remain pending until recorded in HANDOFF.

Offline regression tests use a fake uploader and never open sockets or serial ports:

```sh
python3 -I firmware/tests/test_m5_ota.py
```

## The three deploy kits

| Kit | Target | First install | Updates |
| --- | --- | --- | --- |
| [`pit/sdcard`](../pit/sdcard/README.md) | Raspberry Pi 4 pit station | `cp secrets.env.example secrets.env`, fill it, `FLASH_CONFIRM=/dev/diskN ./flash.sh /dev/diskN`; first boot (cloud-init) runs `install.sh`, ~10 min | `pit/deploy.sh [host] [--install]` from the Mac (rsync to `/opt/gokart-pit`, keeps the Pi's config, logs, imagery and edited zones) |
| [`kart/sdcard`](../kart/README.md#sd-card-kit-sdcard) | Raspberry Pi 3 B on each kart | same, with `KART_ID` set in `secrets.env`; ~6-15 min | `kart/deploy.sh gokart-kart-N.local [--install]` (keeps config, logs, map cache) |
| [`firmware/build.sh`](../firmware/README.md) | Heltec V4.3 (kart), T-Beam S3 (base, repeater) | `./build.sh kart upload /dev/cu.usbmodemXXXX` (or `base`, `repeater`), or the prebuilt image in `firmware/releases/` with esptool | `./build.sh kart ota gokart-N.local`, or `espota.py -i <ip> -p 3232` |

Both SD kits write Raspberry Pi OS Trixie Lite 2026-10-06 arm64 (`GOKART_IMG` overrides the
image path), refuse the internal disk and any non-removable, virtual or read-only disk, need the
disk id typed or `FLASH_CONFIRM` set to it, and verify the image hash and seed files. Their
`secrets.env` and `build/` folders hold Wi-Fi and login passwords: both are gitignored; delete
`build/` after flashing.
