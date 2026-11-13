# Kart 3 tune alignment — 12-setting trial applied and read back

The replacement USB cable worked on November 10. All **376 settings** were read from kart 3:
**326 equal and 50 different** from the dated kart 2 baseline (40 motor / 10 app differences).
The owner confirms identical motor, battery/BMS, gearing and wheels. The ESC hardware differs;
its calibration and capabilities must remain specific to the actual controller.

At **19:58:55 UTC on November 10**, the requested backed-up tune trial was applied with one
persistent motor-configuration write and exact acknowledgement. Readback verified all 376 fields:
**12 motor fields changed; 364 fields and every application byte stayed unchanged**. No Hall/pedal
recalibration, motor actuation command, reset, detection or firmware update occurred.
[Exact trial](../hardware/vesc/kart3/2026-11-10/tune-trial-v1/README.md),
[application/readback evidence](../hardware/vesc/kart3/2026-11-10/tune-applied-v1/README.md).

The review below describes the original pre-tune differences. Its proposed housekeeping corrections
(sensor Disabled and motor braking 0 A) are now included in that trial. The charge-current limit,
absolute-current/minimum-VIN protections, all per-unit calibration, physical drivetrain metadata and
all input/app settings remain unchanged. Runtime readback is verified; persistence across a power
cycle and physical driving behavior have not been tested. The original Desktop backup remains intact.

## Evidence

| Item | Kart 2 reference | Kart 3 candidate |
| --- | --- | --- |
| Capture | November 5, 2026 | November 10, 2026, 19:28:31 UTC |
| Firmware / hardware | 6.00 / 75_100_V2 | 6.02 / 75_300_R2 |
| UUID | 2c004c000951343037353739 | 37004e000951343037353739 |
| Scope | Dated runtime read, not current kart 2 state | Fresh USB runtime read, not saved-flash image |
| Schema | 189 motor + 187 app fields | Same signatures/order verified, all fields decoded |

- [Capture procedure, hashes and limitations](../hardware/vesc/kart3/2026-11-10/usb-before-tune/README.md).
- [All 376 exact comparisons](../hardware/vesc/kart3/2026-11-10/usb-before-tune/comparison-reviewed/comparison.md).
- [Review of every differing field](../hardware/vesc/kart3/2026-11-10/usb-before-tune/assessment.md).
- [Machine-readable assessment of every field](../hardware/vesc/kart3/2026-11-10/usb-before-tune/assessment.json).

Every field is accounted for: **326 equal/retain**, **7 shared-envelope candidates**,
**30 per-unit/hardware/identity differences to retain**, and **13 protection/application/uncertain
settings to review separately**. These classifications do not approve the old values as write targets.
Field meanings were checked against the pinned [VESC Tool schema](../third_party/vesc_tool/6.00/parameters_mcconf.xml).

## Shared driving-envelope candidates

| Setting | Kart 3 now | Dated kart 2 | What matching would change |
| --- | ---: | ---: | --- |
| Motor current max | 120 A | 140 A | Increase motor-current allowance |
| Battery current max | 90 A | 100 A | Increase battery-current allowance |
| Signed ERPM limits | -100000 / +100000 | -150000 / +150000 | Extend both directions' electrical-speed envelope |
| Maximum duty | 0.99 | 0.95 | Lower duty ceiling; review with field-weakening onset |
| Field-weakening current max | 15 A | 95 A | 6.33 times the configured allowance; requires deliberate tuning |
| Field-weakening start | 0.90 | 0.87 | Start at a lower fraction of maximum duty |

These are the seven named fields relevant to the shared envelope, not a ready-to-apply seven-field
preset. The dated baseline does not verify present motor/ESC/BMS thermal or electrical headroom.
The large field-weakening difference can contribute to a different upper-speed feel, but this
stationary capture cannot establish which limit is reached on track or diagnose a cutoff.

Both karts already have the same 0.2 s field-weakening ramp, 0.02 Q-current factor and 0.3/0.1 s
ADC throttle ramps. The different `cc_ramp_step_max` is documented for DC/BLDC, while these karts
use FOC; copying it is not an established fix for acceleration. Future tuning intent remains:
preserve useful field weakening for possible boost, test ERPM limits for ECO/NORMAL, keep strong
acceleration. Existing BOOST is a current-scale/speed-cap override, not field-weakening control.

## Specific mismatches and values to preserve

- **No motor-temperature sensor is wired.** Kart 3 nevertheless selects NTC 10K and returns -95.4 C.
  The supervised trial changed `m_motor_temp_sens_type` 0 → 8
  (Disabled), consistent with actual wiring and the historical baseline; readback verified.
  This does not create motor-temperature protection; ESC temperature remains separate.
- **Braking allowances differ.** Kart 3 has `l_current_min=-50 A`, baseline 0 A; owner intent was
  motor regen off. The supervised trial changed `l_current_min` → 0 A, readback verified.
  Battery regen limit remains -12 A rather than automatically expanding it to baseline
  -100 A. Keep speed-PID braking disabled (0); baseline has it enabled (1). These allowances and
  the nonzero FW Q factor mean no single field proves every possible regen path is off.
- **Preserve controller protections.** Do not lower minimum VIN from 60 V to 12 V or raise absolute
  overcurrent from 220 A to 240 A simply to match. Battery reduction thresholds already match at
  68/60 V; ESC temperature thresholds match at 85/100 C. Equal values still require component
  validation, and a fault history/load log is needed before attributing a cutoff to one limit.
- **Preserve calibration.** Hall tables, current/phase-voltage offsets, motor R/L/flux, current-loop
  gains, observer tuning and pedal endpoints differ. Same-model assemblies do not share measured
  calibration. Keep CAN ID 19, hardware-supported phase filters and working ADC input selection.
  ADC versus ADC+UART and CAN reporting should follow actual wiring/topology, not cosmetic parity.
- **Measure drivetrain metadata.** Stored poles are 20 versus historical 14; gear ratio differs
  slightly. Eamon reports the baseline speed metadata is wrong by about 2.5x and uses Heltec
  `speedcal=2.48` to compensate. Equal wheel diameter (0.406 m) is not measurement proof.
  Verify actual pole count, tooth counts and rolling circumference before changing VESC metadata
  or resetting `speedcal` to 1.0. Heltec speedcal is not contained in this USB dump.

## Further commissioning after the applied trial

1. Refresh kart 2's actual motor/app export if the goal is its tune **today**; the stored reference
   predates subsequent work. Preserve this kart 3 capture and read a fresh pre-write copy.
2. With the owner present, kart stationary and pedals released, review the exact named-field list.
   Separate sensor/braking intent corrections, shared speed/current limits and protection changes.
   Do not import the other controller's complete configuration or run motor detection to synchronize it.
3. Apply the reviewed subset using a separate controlled procedure, then read back all 376 fields.
   Check the exact intended changes and every supposedly preserved calibration/protection value.
   Saved persistence, if requested, requires a distinct verification; the runtime export is not proof.
4. Reconcile the Heltec's per-controller ceiling with the intentional tune; no cached old ceiling may
   overwrite a deliberate change. Commission fresh M5 and pit controls with wheels lifted and an
   observer, followed by link-loss/reconnect checks and measured speed/range validation.

The read-only capture tool remains restricted to IDs 0, 4, 14 and 17. This review does not inventory
installed Lisp scripts or enable the optional braking script. Remote STOP/coast does not establish
mechanical braking performance. The later Core2/Heltec mode commissioning enabled temporary supervisory writes; see the
[mode evidence](../hardware/m5/2026-11-10-kart3/mode-commissioning/README.md).
