# Kart 3 motor-braking minimum: persistent save, 2026-11-11

The owner requested saving the successful temporary −5 A setting, followed by a
Heltec coexistence test. At 18:51:47–18:51:50 UTC one guarded `SET_MCCONF` (13)
changed **only `l_current_min`: 0 → −5 A**. The controller acknowledged the save;
full runtime readback matched exactly, preserving all other 375 motor/app fields.
The reverse filter remained active/forward, pedal released, stationary and fault-free.

**Current status: −5 A active; cold-boot persistence and Heltec coexistence pending.**
Command 13 acknowledges after attempting storage, without reporting flash-store
success. A runtime readback alone does not establish persistence. Do not resend
this one-shot helper or restore the old setting automatically.

- `pre-save-check/`: independent read-only confirmation that the temporary trial
  had returned to 0 A before this permanent change.
- `apply/before/` and `apply/after/`: validated complete 376-field captures.
- `apply/field-audit.json`: exact one-field difference.
- `apply/manifest.json`: identity, freshness/stationary guards and ACK/readback results.
- `host-tools/`: exact reviewed one-use helper and dependency; these are session
  evidence, not a fleet installer. The helper is hard-pinned to kart 3 and its predecessor.

Firmware 6.02, hardware string `75_300_R2`, build `no_hw_limits`, UUID
`37004e000951343037353739`; physical unit is owner-identified Flipsky 75100 Pro V2.0.
No firmware upgrade, app-setting write, Hall/pedal calibration, motor command or reset
was sent. Battery regenerative-current limit remains −12 A. The −5 A setting is a
motor-phase braking allowance; it is not a command to brake continuously.

The full motor setter briefly locks/releases motor output during flash storage; this
was performed stationary with the previously confirmed lifted wheels/cutoff setup.
Pinned firmware source: `f7c2b34e1cff2234cae98be3abf0cd50e249558f`.
The writer passed framing/guard/partial-write tests and an independent review;
its final 750 ms freshness gate includes the pedal/filter snapshot.

See [temporary trial](../brake-limit-trial-01/README.md) and
[internal-target diagnosis](../pedal-response-03/README.md).
