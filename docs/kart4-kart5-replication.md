# Prepare karts 4 and 5 from the reviewed kart-3 setup

**IDs 4 and 5 are assigned to the two new M5/Heltec karts. IDs 1 and 2 remain
Eamon's test karts; kart 3 is the measured reference. Neither new kart is
commissioned by this guide.** Use the [M5 bring-up checklist](../firmware/m5-core2/BRINGUP.md)
for each physical display/supervisor pair.

The new `tools/vesc/prepare_fleet_kart.py` prepares a reviewable package offline.
It copies twelve named operating settings from a complete, validated kart-3
capture and retains every other target motor byte and all 187 target application
settings. It also adapts the reviewed reverse filter's startup UUID guard to that
target. **It has no apply, serial-port, flash, motor or lifecycle command.**

## What carries over, and what stays individual

| Copied operating field | Reviewed source value |
| --- | ---: |
| `l_current_max` | 140 A |
| `l_current_min` | −5 A |
| `l_in_current_max` | 100 A |
| `l_min_erpm` / `l_max_erpm` | −150000 / +150000 |
| `l_max_duty` | 0.95 |
| `foc_fw_current_max` | 95 A |
| `foc_fw_duty_start` | 0.87 |
| `foc_openloop_rpm` / `foc_sl_erpm` | 700 / 4000 |
| `cc_ramp_step_max` | 0.04 |
| `m_motor_temp_sens_type` | Disabled (8); motors currently have no wired temperature sensor |

This is the existing twelve-field trial scope with the November 11 motor-braking
correction, **not a full configuration clone**. `cc_ramp_step_max` is principally
a DC/BLDC parameter; copying it does not establish a FOC acceleration improvement.
The 95 A field-weakening value and current limits still require matching hardware,
battery/BMS and thermal review; a source kart working on a stand establishes no
fleet rating or endurance guarantee. The kart-3 trial also logged one 84.4 V bus
sample after pedal release without a reported fault; see the
[trial audit](../hardware/vesc/kart3/2026-11-11/brake-limit-trial-01/independent-audit/summary.json).
Validate charged-pack voltage/BMS behavior before fleet acceptance; the trace does
not establish the cause of that transient.

Preserve each target's Hall map, R/L/flux and controller gains, electrical measurement
offsets, motor orientation, pedal endpoints, drivetrain metadata, CAN/controller ID
and all application settings. Boot-time current/voltage offset calibration can
change runtime motor bytes after reboot; do not copy older offsets to force equality.

The plan includes two complete 376-field audits: target before/after and source versus
proposed target. Every remaining difference has `needs_review:true`. Calibration and
identity differences are labeled as target-specific; ordinary operating differences
are unresolved commissioning blockers. In particular, **battery-regeneration limit
`l_in_current_min` and current scales are not copied**. Review retained target values
against the source's −12 A and 1.0/1.0. Resolve differences explicitly before declaring
the operating tune equivalent; do not expand the copy list casually.

## Capture and prepare

1. Label the physical kart and confirm its VESC, Heltec and Core2 identities. Record
   actual VESC UUID and BLE MAC; never copy kart 3's pins or select the first nearby
   Bluetooth device. Confirm hardware matches the intended build.
2. With the kart stationary and its accessory VESC client disconnected, capture that
   controller's complete runtime configuration into a new evidence directory:

   ```sh
   python3 -B tools/vesc/capture.py --port /dev/cu.ACTUAL_VESC_PORT \
     --out hardware/vesc/kart4/YYYY-MM-DD/before/raw
   ```

   Verify `capture_complete:true`, UUID/build and all 189 motor + 187 app fields.
   Also back up existing stored Lisp with `read_lisp.py` and retain private board
   flash/NVS backups. Runtime captures are not independently verified saved-flash
   backups; `no_valid_blob` does not prove raw flash is blank.
3. Supply the reviewed full kart-3 capture taken after the −5 A correction, then run:

   ```sh
   python3 -B tools/vesc/prepare_fleet_kart.py \
     --source-kart3 /absolute/path/to/reviewed/kart3/raw \
     --target hardware/vesc/kart4/YYYY-MM-DD/before/raw \
     --kart-id 4 --target-uuid ACTUAL_24_HEX_DIGIT_UUID \
     --out hardware/vesc/kart4/YYYY-MM-DD/prepared
   ```

   The November 11 verified cold-boot reference is
   [brake-limit-persistent-01/coldboot-forward/raw](../hardware/vesc/kart3/2026-11-11/brake-limit-persistent-01/coldboot-forward/raw).
   Read the neighboring `verification.json` and consult [HANDOFF](../HANDOFF.md)
   for completed Heltec/Core2 ECO bench coexistence and outstanding broader acceptance.
   The later coexistence session ends in temporary ECO; keep the linked full-scale
   cold-boot source for this preparation tool. The
   tool never infers that acceptance from a folder name or a runtime capture alone.

   Use kart 5's own capture, UUID, ID and new output path for the second unit. The
   source is an explicit argument, not an automatically selected “latest” folder.
   Both captures must validate as firmware 6.02 release/test0, `75_300_R2`,
   `no_hw_limits`, with compatible schemas and captured rest/low-current/fault-free
   state. Other builds require a separate review; the tool does not reflash them.
   It rejects IDs other than 4/5, the known reserved UUIDs and a target UUID that
   disagrees with its captured firmware response. Cross-check both new plans to
   ensure they do not identify the same physical controller.

Outputs are `plan.json`, a readable review, unchanged input snapshots,
`proposed_motor_response.bin`, UUID-bound `rx-filter-autostart.lisp` and
`rx-filter-codeblob.bin`. The motor binary is a command-14 **response-shaped
artifact**, not a write frame. The Lisp blob is source + NUL + zero import count,
without a flash header. All artifacts are **prepared, not installed**.

## Before application and acceptance

The existing `apply_tune.py`, `install_rx_filter.py`, RAM loader and lifecycle tools
are specifically pinned to kart 3. **They cannot install these new packages. Do not
work around their identity/hash checks.**

**Tune (since 2026-11-13):** `tools/vesc/apply_fleet_tune.py` is the separate reviewed writer
for a package made by `prepare_fleet_kart.py`. It needs the kart ID and controller UUID stated
again on the command line, refuses kart 3 and the reserved controllers, rebuilds the package
independently, requires fresh controller bytes identical to the package's `before/` and
stationary fault-free telemetry, and for a write also requires `--apply`,
`--acknowledge-persistent-write` and the hash of the reviewed proposed bytes. It writes once,
requires the ACK and an exact 376-field read-back, and never retries or rolls back. Run it
offline first, then `--preflight-only`, and write only with the owner's explicit go-ahead for
that kart. Because offsets are re-measured at boot, capture, prepare and apply in one powered
session; after a power cycle the old package is refused and a new capture is needed.
[Kart 4's record](../hardware/vesc/kart4/2026-11-13/README.md) is the worked example.

**Protection limits:** `prepare_fleet_kart.py --match-protection-limits` also copies five
limits from kart 3 (`l_in_current_min` −12 A, `l_abs_current_max` 220 A, `l_min_vin` 60 V,
`l_max_vin` 90 V, `m_fault_stop_time_ms` 500). The owner chose this for kart 4 after seeing
its values (−200 A, 420 A, 12 V, 84 V, 50 ms). It is an explicit per-kart choice, off by
default; decide it for kart 5 from kart 5's own capture.

**Filter (since 2026-11-13):** `tools/vesc/fleet_rx_filter.py` works from the same package and
is bound to the kart the same way. Keep every other VESC client off the controller, the kart's
own Heltec included (hold it in its bootloader with `esptool --after no_reset chip_id`, restart
it with `--after hard_reset chip_id`), because 6.02 sends Lisp prints to the interface that
spoke last.

1. `plan` offline, then `observe` with the switch in forward and again in reverse: RX must read
   1 in forward and 0 in reverse, the released pedal at most 0.12, no stored code, no contexts.
2. With the owner's go-ahead for that kart, switch in forward, wheels up, pedal released:
   `install --apply --supervised --expect-blob-sha256 <hash>`. It requires the prepared tune on
   the controller (runtime ERPM limits may be tighter than the tune, never looser), rechecks
   forward/rest/pedal within 750 ms of the erase, writes body then header, and reads every byte
   back. It never starts the script.
3. The owner power-cycles the VESC. `status --expected-rx 1` must report the stored bytes
   intact and the worker armed in forward; after a switch change at rest, `--expected-rx 0`
   must report reverse. Then a supervised pedal check both ways.

It refuses to install over existing code, and **there is no tested removal tool**: removal is
by VESC Tool, at rest. Kart 3's in-memory trial stage is not repeated, because the filter core
is byte-identical; the observation covers what is specific to each kart.
[Kart 4's record](../hardware/vesc/kart4/2026-11-13/filter/README.md) is the worked example.

The filter requires native ADC application 2, Current Reverse Button type 3,
buttons 0, servo output off, safe-start on and deadband 0.15; unsupported application
settings cause preparation to refuse rather than silently change them. Check the
target's actual released-pedal decoded level against the filter's ≤0.12 guard.
Retain its physical pedal calibration. Resolve any existing Lisp/native overrides
before loading a new copy.

Commission each unit independently, wheels lifted, operator at the cutoff:

- Verify native pedal and forward/reverse behavior, then exact tune/filter readback.
  Check repeated starts from complete rest; distinguish coasting reapplications.
- Verify filter qualification and normal boots with both switch positions. Native ADC
  starts before Lisp; a watchdog boot can skip it. Keep the pedal released until an
  active worker and correct applied direction are verified. Worker failure can hold
  direction, and a prolonged wrong RX level can still qualify. Repair the harness
  separately; software filtering is not an electrical repair.
- Start Heltec commissioning read-only. A blank Heltec boots as kart 1 and transmits, so store
  the ID first with `firmware/provision-kart-id` (see the bring-up checklist), then install the
  read-only kart build. Assign ID 4 or 5, its unique BLE MAC/UUID pins,
  its own verified baseline and speed calibration; do not clone kart 3's NVS or
  speed-calibration factor. Pair only its Core2/Heltec with fresh private ESP-NOW keys.
  Use distinct `gokart-4/5` and `gokart-display-4/5` maintenance hostnames and private
  credentials. Fleet ID is not an instruction to overwrite VESC `controller_id`.
- After read-only telemetry/link recovery, separately commission M5 modes and pit
  controls. A base station is optional for own telemetry/direct peers; pit/race
  functions need it. Neither dashboard nor GPS peer map requires SD; a local course
  outline is optional. Preserve active VESC behavior across accessory/link loss.

Record each unit's source hashes, identities, exact differences, write/readback and
physical outcomes. Current preparation tests use explicitly synthetic fixtures;
they are not kart-4/5 hardware evidence.

```sh
python3 -I -B -m unittest discover -s tests -p test_vesc_prepare_fleet_kart.py -v
```
