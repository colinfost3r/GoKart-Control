# VESC inspection and explicit tune trial

`capture.py` captures runtime state read-only; `decode.py` and `compare.py` work offline.
These inspection tools cannot write configuration, command motor current/speed, reboot or
flash firmware. Only IDs 0, 4, 14 and 17 remain allowed by `capture.py`.

`tune.py` separately prepares the fixed 12-field kart-3 trial offline. `apply_tune.py` is an
explicitly opted-in **persistent motor-configuration writer** for that reviewed trial; see
[guarded application](#guarded-kart-3-tune-trial). It defaults to offline validation and never
writes application settings, commands motor current/speed, resets, detects or flashes firmware.

## Read stored Lisp code without executing it

`read_lisp.py` separately permits only identity (0) and stored-code read (130), requires an
explicit expected controller UUID and supports only the pinned 6.02 layout. It never evaluates,
starts, stops, erases or writes Lisp, and does not expand `capture.py`'s original allowlist.
Use a new output directory and inspect `manifest.json` before treating a capture as complete.

```sh
python3 -B tools/vesc/read_lisp.py --port /dev/cu.usbmodemACTUAL_PORT \
  --expected-uuid 37004e000951343037353739 --out /absolute/path/to/new/lisp-backup
```

The binary contains the valid stored code/import blob exposed by firmware, excluding its eight-byte
size/CRC/flags header. Autostart flags and current execution state are unknown; this is not a raw
flash backup. `no_valid_blob` is not proof of blank flash. CRC-checked replies, hashes, partial data
and failure metadata are preserved. Size/identity are checked again, but same-size concurrent
changes cannot be excluded: close other clients and do not edit code while reading.
[Next supervised reverse-input session](../../firmware/vesc-lisp/reverse-input/README.md).

## Fixed reverse-input observation

`rx_probe.py` is a separate kart-3-only helper. It pins UUID `37004e000951343037353739` and firmware 6.02, permits identity (0), Lisp stats (134) and only fixed REPL (138) requests. `--inspect` sends `:ctxs`; `--snapshot` directly reads RX/TX/ADC/RPM/fault once; monitor mode sends the SHA-pinned bounded input-only expression. REPL can initialize the interpreter or pause/GC/resume evaluation, so capture stored code and inspect ownership first. No reset, flash, input override or motor command is available.

```sh
python3 -B tools/vesc/rx_probe.py --port /dev/cu.usbmodemACTUAL_PORT \
  --inspect --out /absolute/path/to/new/context-capture
# One fixed direct snapshot (balanced LispBM {float} replies supported):
python3 -B tools/vesc/rx_probe.py --port /dev/cu.usbmodemACTUAL_PORT \
  --snapshot --out /absolute/path/to/new/pin-snapshot
# Only after fresh configuration, stored-code and context review:
python3 -B tools/vesc/rx_probe.py --port /dev/cu.usbmodemACTUAL_PORT \
  --ownership-reviewed --out /absolute/path/to/new/rx-monitor
```

Pause the competing VESC Bluetooth client for reliable USB Lisp prints: 6.02 routes asynchronous output to the most recent interface. After a missing completion marker, inspect context state and resolve transport visibility; do not automatically resend. The sender stops after an uncertain/partial write, captures for a bounded time/byte budget and retains failure evidence. Context output is only a snapshot, not proof of future ownership or absence of native overrides.

[Hardware observation and limitations](../../hardware/vesc/kart3/2026-11-11/reverse-diagnostic-02-held-state/README.md); [session procedure](../../firmware/vesc-lisp/reverse-input/README.md).

## Capture

Use Python 3.9+ on macOS/Linux. Close VESC Tool or other serial clients. Have the
owner power and connect the intended controller. Confirm the explicit serial port;
the Mac port used on November 5 was `/dev/cu.usbmodem3041`, which may change.

```sh
python3 -B tools/vesc/capture.py --port /dev/cu.usbmodem3041 --out /tmp/gokart-new-capture
python3 -B tools/vesc/decode.py /tmp/gokart-new-capture --out /tmp/gokart-new-decoded
```

Both output directories must be new. On Linux use the actual `/dev/ttyACM…` or
other identified VESC device. Device permissions are required; do not broadly
change system serial permissions as a workaround. Capture performs no automatic
scanning/probing of unrelated devices and stops after identity if firmware is
not 6.00 or 6.02, or the identity layout is incomplete/unrecognized. Read requests use USB serial at 115200 and never send keepalive/control
commands. The controller remains in charge of existing driver inputs.

A partial or incompatible capture retains a manifest with `capture_complete: false`
and an error; inspect it before trusting the directory. Completion requires all four
CRC-valid replies, both configuration signatures and full payload lengths, and the
verified identity/telemetry layouts. The manifest records UTC times, payload hashes,
identity and schema-validation results. Reads are sequential runtime observations,
not an atomic snapshot or proof of saved flash contents. The raw `.bin` files contain response payloads
(command byte plus data), not entire USB frames. Frames were CRC-checked on receipt.

## Offline decode and verification

```sh
python3 -B tools/vesc/decode.py hardware/vesc/baseline-kart/2026-11-05/raw --out /tmp/gokart-baseline-decoded
python3 -B -m unittest discover -s tests -v
```

The decoder verifies schema CRC32C signatures and exact lengths before accepting
motor/application values. The pinned 6.00 schemas also decode 6.02: official
`release_6_02` motor and app serialization definitions were compared field by field
and have identical order, types, transport encodings, scales and labels. Motor
signature `2e43a161` covers 189 fields; app signature `1d003a2c` covers 187. The
6.02 firmware source confirms the same 74-byte telemetry and complete identity
layouts. [Provenance](../../third_party/vesc_tool/README.md) pins exact source commits.
Decoded configuration records retain `schema_version: "6.00"` and add the actual
`firmware_version`; compatibility never means the two controllers have the same tune.

Enum fields use `enum_labels`. Bitfields use `bitfield_labels` lists, where `[]` means
no enabled bits; raw integers remain in `values`, with unnamed bits reported in
`bitfield_unknown_bits`. Earlier immutable baseline JSON mistakenly labeled zero
bitfields as enum option zero. Re-decode its raw files for comparisons; do not edit
the historical evidence. The November 5 runtime capture is dated evidence and does
not establish kart 2's current settings.

Other firmware versions/layouts fail explicitly rather than guessing offsets. Tests
use the real 6.00 baseline and real November 10 kart-3 6.02 capture, clearly synthetic
identity fixtures, corrupt/fragmented packets, and mocked CLI serial calls. They
never access hardware or claim a 6.02 hardware measurement.

These exports are not flash images, not a proven saved-configuration backup,
and not a ready-to-import tuning preset. GET_VALUES reads reset some averaging
accumulators in ordinary VESC operation. No load/fault-history trace is collected.

The initial baseline used a small one-off read script with the same four
allowlisted queries. The maintained capture CLI was prepared afterward and tested
offline. On November 10 the maintained CLI captured kart 3 over USB, with four CRC-valid
replies and all 376 settings decoded on actual 6.02 hardware. See the
[kart 3 evidence](../../hardware/vesc/kart3/2026-11-10/usb-before-tune/README.md).
The tests themselves remain offline; they never operate a controller.


## Compare every captured setting offline

Compare complete captures against an explicit, dated reference. This example uses the actual
November 10 kart 3 capture; choose a new output directory:

```sh
python3 -B tools/vesc/compare.py \
  hardware/vesc/baseline-kart/2026-11-05/raw \
  hardware/vesc/kart3/2026-11-10/usb-before-tune/raw \
  --out /tmp/gokart-settings-comparison
```

The new output directory contains `comparison.json` and `comparison.md`. Both
record **all 189 motor and 187 application fields**, including equal values, with
exact decoded-value equality (no tolerance or omitted fields). Enum/bitfield
meanings accompany their raw values. Controller UUID, firmware, hardware, source
paths, dated query timestamps and their basis, payload/manifest SHA-256 hashes and
runtime scope stay attached to each side. Full identity and telemetry
decodes are retained in JSON, separately from the 376-setting equality counts.

Inputs must be complete, hash-consistent runtime captures with capture-time CRC
claims for the four allowed reads. Both known 6.00/6.02 schemas, exact payload
lengths and complete field sets must validate. An incomplete manifest, missing or
ambiguous manifest, altered payload, unsupported firmware/layout, bad signature,
truncated/trailing bytes or field-set mismatch aborts before creating a report.
The tool looks for `manifest.json` in the raw directory; for the original `raw/`
layout only, it also accepts the parent-directory manifest. If necessary, specify
`--reference-manifest /exact/path/manifest.json` and/or `--candidate-manifest ...`.
Existing output paths are refused. Keep reports outside immutable capture folders.

This tool opens **no device or network connection**, issues no VESC commands, and
has no apply/copy option. Differences are observations, not a change plan or a
recommendation to import the reference. The November 5 baseline is dated runtime
evidence, not a current kart 2 export. Preserve per-unit motor/controller
calibration, pedal endpoints and identities unless separately measured.

Eamon's November 10 handoff reports that kart 2's drivetrain metadata is wrong by
about 2.5x, with a **2.48 Heltec speed-calibration factor** compensating for it.
Do not blindly copy `si_motor_poles`, `si_gear_ratio` or `si_wheel_diameter`, or set
`speedcal 1.0` without physical measurement and speed validation. The Heltec's
speedcal setting is not contained in these VESC configuration captures. Matching
hardware models does not establish that the captured calibration is correct.

Comparison tests use the immutable 6.00 evidence and clearly synthetic 6.02 data
under temporary directories. They do not create project evidence or claim a fresh
kart 3 capture. Run them with the other VESC checks:

```sh
python3 -B -m unittest discover -s tests -v
```


## Guarded kart 3 tune trial

The fixed trial copies only the 12 fields in `tune.TRIAL_FIELDS` from the pinned dated reference
into the current kart-3 motor payload. Every other motor byte and all app bytes are preserved.
The actual [November 10 application](../../hardware/vesc/kart3/2026-11-10/tune-applied-v1/README.md)
is complete; **do not rerun it**. A mismatched current configuration rejects the old plan.

Prepare and review offline (new output directory):

```sh
python3 -B tools/vesc/tune.py hardware/vesc/baseline-kart/2026-11-05/raw \
  /path/to/new/kart3/raw --out /path/to/new/trial
python3 -B tools/vesc/apply_tune.py /path/to/new/trial
```

For a separately authorized, reviewed hardware session, `--preflight-only --port <actual-port>
--out <new-evidence-directory>` performs reads only. Mutation requires **both** `--apply` and
`--acknowledge-persistent-write`, plus explicit port and new evidence directory. Do not copy-paste
these options as a recovery attempt after an uncertain result. The full MCCONF command (13) stores
configuration; it is not the Heltec's temporary `store=0` profile command.

Before writing, the utility independently rebuilds the candidate, checks schemas/file hashes,
reads fresh identity plus all motor/app bytes, and reads stationary/fault-free telemetry last.
It requires the exact prepared before state and checks a 750 ms telemetry/10 s capture deadline.
There is at most one configuration-frame send. Missing/malformed ACK, partial/unknown send or
unexpected readback remains uncertain: never automatic retry or rollback. Partial sends prohibit
additional bytes; after a known complete send, a read-only recovery capture may clarify state.

Success requires the exact ACK and an exact all-376-field/raw-byte readback. Evidence includes
before/after manifests, frame hash, one-write count and field audit. Runtime verification does not
independently prove flash persistence; the tool never power-cycles or drives the motor. Restore
from the Desktop/raw reference is separate reviewed work, not an automatic whole-config import.
