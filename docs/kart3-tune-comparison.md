# Kart 3 tune alignment — awaiting complete USB capture

The owner requests checking every motor and app setting and aligning the shared tune with kart 2.
They confirm identical motor, battery/BMS, gearing and wheels. This document is a preparation record,
not an applied preset. The VESC USB cable failed on November 10; the owner will replace it.
No kart-3 controller tune change has been made.

## Evidence available

Kart 2 reference: immutable November 5 runtime capture, firmware 6.00 / 75_100_V2, UUID
`2c004c000951343037353739`. It is dated evidence, not a fresh reading of kart 2 or proof of saved flash.
Kart 3: current Heltec runtime observations, firmware 6.02 / 75_300_R2, UUID
`37004e000951343037353739`; full motor/app payloads have not yet been captured.

| Field | Kart 2 dated baseline | Kart 3 observed | Status |
| --- | ---: | ---: | --- |
| Motor current maximum | 140 A | 120 A | Different |
| Battery current maximum | 100 A | 90 A | Different |
| Maximum ERPM | 150000 | 100000 | Different |
| Maximum duty | 0.95 | 0.99 | Different |
| Configured motor poles | 14 | 20 | Different; physical correctness unresolved |
| Gear ratio | 2.7692308426 | about 2.769 | Full-precision comparison pending |
| Wheel diameter | 0.4059999883 m | about 0.406 m | Full-precision comparison pending |
| Maximum field-weakening current | 95 A | Unknown | Full capture required |
| Field-weakening start / ramp / Q factor | 0.87 / 0.2 s / 0.02 | Unknown | Full capture required |
| All other motor/app values | Available in baseline | Not yet fully read | Do not assume equal |

Eamon's latest `b543bea` handoff explicitly says the baseline drivetrain numbers are wrong by
about 2.5x and `speedcal=2.48` is a compensation. Do not copy known-bad drivetrain numbers or switch
calibration to 1.0 without checking the actual poles/gearing/rolling wheel diameter and GPS vs ERPM.
The user confirming matching assemblies does not establish which stored pole count is physically right.

## Complete comparison and change workflow

1. Identify the intended USB device and read its identity. Require kart 3's UUID above.
2. Use the read-only [capture/decoder](../tools/vesc/README.md) to retain complete CRC-verified
   firmware, telemetry, motor and app payloads, timestamps, signatures and hashes in a new directory.
   Verified 6.00/6.02 schema compatibility covers **189 motor + 187 app settings**. No firmware upgrade
   is needed for capture. No motor detection, throttle, brake, reset or setting write is part of capture.
3. Use `tools/vesc/compare.py <reference_raw> <candidate_raw> --out <new_directory>` to compare every
   named field, including equal fields, and label the baseline's capture date. Correct
   type-6 bitfields: zero means no options, not the first enum item. Keep historical JSON immutable.
4. Prepare a named-field change list covering shared current/power/ERPM/duty limits, field weakening,
   regen intent, throttle feel, safety/protection settings and correctly measured drivetrain metadata.
   Preserve individual motor R/L/flux, Hall mapping, ADC/current/voltage offsets, encoder calibration,
   pedal voltage endpoints/inversions, controller identity and actual CAN topology. Review every
   difference; same component models do not make per-unit measurements interchangeable.
5. With the owner present and the kart stationary/pedals released, apply only the reviewed changes,
   then read back all fields to show intended changes and any unexpected changes. Keep the original
   raw runtime export for rollback; do not label it a verified saved-flash image.
6. Reconcile the Heltec's per-controller ceiling after intentional tune changes. The new atomic cache
   must not silently restore an older ceiling over a deliberate retune. Verify full readback first,
   then commission M5/base controls and measure GPS/speed caps before driving acceptance.

The original motor-braking limit is 0 A, but battery regen allowance is -100 A and the FW Q factor is
nonzero; do not claim every regen path is disabled from a single setting. Motor temperature sensors
are unwired. The full dump also does not inventory installed Lisp scripts. Existing STOP reduces
current allowance to zero/coast; enabling a VESC braking script is a separate change.
