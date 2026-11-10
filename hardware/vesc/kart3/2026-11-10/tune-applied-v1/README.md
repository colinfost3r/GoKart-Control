# Kart 3 tune trial v1 — applied and runtime readback verified

At **2026-11-10 19:58:55 UTC (14:58:55 EST)** the user-requested tune trial was applied to
kart 3, UUID `37004e000951343037353739`, 6.02 / 75_300_R2. The owner confirmed wheels lifted,
pedals released and access to the cutoff. A complete pre-tune backup is on the owner's Desktop.

The utility sent exactly **one 488-byte SET_MCCONF (13) frame**, received the exact ACK and
read back all **189 motor + 187 application settings**. Exactly **12 motor settings / 23 bytes**
changed to the prepared proposal. All other motor bytes and the complete 494-byte application
payload are unchanged. No app write, motor actuation, Hall/pedal detection/recalibration, reset
or firmware update was sent. Both before/after samples show 82.1 V, 0 ERPM/current and fault 0.

This command stores motor configuration, unlike temporary Heltec profile writes. The matching
runtime readback is verified; saved persistence across a power cycle and driving performance
are **not** independently verified. No power-cycle or wheel-spin test was performed.

## Evidence

- [apply-manifest.json](apply-manifest.json): fresh identities, source/before/after hashes,
  durable intent, one attempt, ACK/readback status, no retry/rollback and timestamps.
- `before/` and `after/`: unchanged raw payloads and full capture manifests.
- [field-audit.json](field-audit.json): all 376 values compared with the pre-write state.
- `decoded-after/`: readable after-state settings and telemetry; motor temperature is explicitly
  invalid because the unwired sensor is now selected Disabled.
- `set_mcconf_frame.bin`: exact CRC-valid frame retained as evidence, **not a file to upload again**.
  ACK receipt is recorded by the strict utility journal; a separate raw ACK frame was not archived.
- [Prepared 12-field trial](../tune-trial-v1/README.md) and [original backup evidence](../usb-before-tune/README.md).

## Preserved

Hall mapping; pedal endpoints/inversions; motor R/L/flux, gains and observer calibration;
current/phase offsets; position calibration; phase filters; controller/CAN identity; poles,
gearing/wheel metadata; battery charge allowance -12 A; absolute-current threshold 220 A;
minimum VIN 60 V; speed-PID braking disabled; the complete ADC application including reverse
button configuration. The owner clarified throttle ADC1 / reverse TX; the likely RX/TX pin
mismatch is separate [wiring work](../../../../../docs/reverse-input.md), not repaired by this tune.

Do not rerun this application. The original prepared-before state intentionally no longer matches
the controller. Restore/refine only through a separately reviewed procedure after a fresh read.
The original Desktop backup folder remains unchanged:
`/Users/cofo/Desktop/GoKart Control - Kart 3 Backup - 2026-11-10/`.

## Tool provenance

Independent review covered byte preservation and the guarded sender, with 14 focused tests plus
all 54 VESC tests before this write. Two further fake-serial tests added afterward cover invalid
CRC ACK and incomplete readback; transmission/verification logic did not change. The final source
also contains the durable do-not-retry intent and original-capture output-path guards present in
this application journal. Final all-suite validation is recorded in the handoff.

- `tools/vesc/apply_tune.py`: SHA-256 `9d824fa2150c78b604897735e64ac07ca0a15680f5d8d17570d54645e3caac77`
- `tools/vesc/tune.py`: SHA-256 `594d10cdf37e1009137a8e2e7fabe09439a4f4627df34319fdb158e3d3d89737`
- `tools/vesc/capture.py`: SHA-256 `792cb52bf74883187372def81e6c6cd171558e5afe9dab7dd56247a3a84ccaa8`
- `tools/vesc/decode.py`: SHA-256 `01e8c220118bfb7bce96cb42145a476aad6220ab230ccf03d99234a27d2bdfde`
