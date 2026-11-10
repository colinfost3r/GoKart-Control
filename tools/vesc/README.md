# Read-only VESC inspection

These tools capture current runtime state and decode it offline. They cannot
write VESC configuration, command motor current/speed, reboot or flash firmware.
Only command IDs 0, 4, 14 and 17 are allowed by `capture.py`.

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
use the real 6.00 baseline, clearly synthetic 6.02 identity fixtures with compatible
configuration bytes, corrupt/fragmented packets, and mocked CLI serial calls. They
never access hardware or claim a 6.02 hardware measurement.

These exports are not flash images, not a proven saved-configuration backup,
and not a ready-to-import tuning preset. GET_VALUES reads reset some averaging
accumulators in ordinary VESC operation. No load/fault-history trace is collected.

The initial baseline used a small one-off read script with the same four
allowlisted queries. The maintained capture CLI was prepared afterward and tested
offline; it has not itself been run against hardware yet. The maintained decoder
has been run against the actual captured baseline.


## Compare every captured setting offline

After obtaining a **real, complete new capture**, compare its raw directory with an
explicit reference. For example, replace `/path/to/fresh-kart3/raw` with that actual
capture path; it does not exist yet and must not be substituted with synthetic data:

```sh
python3 -B tools/vesc/compare.py \
  hardware/vesc/baseline-kart/2026-11-05/raw \
  /path/to/fresh-kart3/raw \
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
