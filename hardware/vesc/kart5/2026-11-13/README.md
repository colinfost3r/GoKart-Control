# Kart 5 VESC: capture, review and tune write — 2026-11-13

Kart 5's controller was captured read-only, compared with kart 3, and then given kart 3's
operating tune by one persistent motor-configuration write that the owner approved after
reviewing the differences. **The tool recorded that write as uncertain; read this record before
relying on its journal alone.** No Heltec or Core2 was involved in the tune write. Later the
same day the reverse-input filter was installed ([record](filter/README.md)) and the boards
were commissioned ([record](../../../m5/2026-11-13-kart5-first-install/README.md)). The nine
steps below predate both.

| Item | Value |
| --- | --- |
| Controller | firmware 6.02 (test 0), reports `75_300_R2`, `no_hw_limits` |
| UUID | `3d0020000951343037353739` (not kart 3's, kart 4's or a reserved controller) |
| VESC `controller_id` | 52 (unchanged; this is not the fleet ID) |
| Stored Lisp | none (`no_valid_blob`) before and after |
| Motor | R 11.5 mΩ, L 83.2 µH, flux 17.60 mWb; kart 3 has 13.6 mΩ, 81.8 µH, 17.50 mWb |

## What was done, in order

1. **Read-only capture** over USB (`before/`): all 189 motor and 187 app settings, telemetry at
   rest with fault 0, pack 83.0 V, and the stored-Lisp read.
2. **Comparison with kart 3's reviewed reference**: 37 of 376 settings differed
   (`before/vs-kart3/`).
3. **Twelve-field package** (`prepared/`): nine changes, one ordinary operating difference left
   (`l_abs_current_max` 300 A against 220 A). Never applied.
4. **Owner decision:** include the protection limits, as on kart 4. On kart 5 four of the five
   already matched kart 3, so this adds only the absolute current trip. Package
   `prepared-limits/`, proposed bytes sha256
   `ee7f7b088c1702de4ee974d4d19cf354dfe8eb85d160ae4ba6802b8754c2140a`.
5. **Read-only preflight** (`tune-preflight/`): identity, byte-identical settings and stationary
   telemetry confirmed; nothing sent.
6. **Owner go-ahead, then one write** (`tune-applied/`): a single `SET_MCCONF`, acknowledged.
   The tool's byte-for-byte read-back then **failed on one byte**, so its journal ends
   `write_uncertain_do_not_retry`. Nothing was retried or rolled back.
7. **What that byte is.** The tool's own read-back and an independent capture (`after/`) agree:
   exactly one byte differs from the intended result, in `foc_offsets_voltage__0`, which read
   0.0006 where 0.0007 was sent. That is one of the controller's own voltage measurement
   offsets, not a tune field. All 17 packaged fields hold their proposed values, and the
   firmware and all 187 app settings are byte-identical to before. Why the offset moved one
   count is **not established** (re-measurement by the controller, or rounding when the value is
   written back). Kart 4's write read back exactly.
8. **Power cycle by the owner, then re-capture** (`coldboot/`): every packaged field still holds
   its proposed value. Five `foc_offsets_*` values differ from `after/`; the controller
   re-measures them at each boot. App settings unchanged, stored Lisp still none.
9. **Wheels-up pedal check** (`pedal-check/`): 51 s of read-only telemetry at 10 Hz. Two forward
   runs (peak 11783 ERPM, 30.6 A) and one reverse run (peak −11158 ERPM), fault 0, pack
   81.2–83.2 V, no direction change within a run. The owner reported it felt right. Three short
   runs; this says little about reverse reliability.

## The 10 settings changed

| Setting | Before | After (kart 3's value) | Scope |
| --- | ---: | ---: | --- |
| `l_current_max` | 100 A | 140 A | reviewed tune |
| `l_current_min` | −50 A | −5 A | reviewed tune |
| `l_min_erpm` / `l_max_erpm` | ∓100000 | ∓150000 | reviewed tune |
| `l_max_duty` | 0.99 | 0.95 | reviewed tune |
| `foc_fw_current_max` | 100 A | 95 A | reviewed tune |
| `foc_fw_duty_start` | 0.90 | 0.87 | reviewed tune |
| `foc_openloop_rpm` | 800 | 700 | reviewed tune |
| `m_motor_temp_sens_type` | 0 | 8 (disabled; no sensor wired) | reviewed tune |
| `l_abs_current_max` | 300 A | 220 A | protection limit, owner decision |

Already equal and so unchanged: `l_in_current_max` 100 A, `foc_sl_erpm` 4000,
`cc_ramp_step_max` 0.04, and the protection limits `l_in_current_min` −12 A, `l_min_vin` 60 V,
`l_max_vin` 90 V and `m_fault_stop_time_ms` 500. The motor-braking change from −50 A to −5 A
is the one a driver feels: the kart now coasts on lift-off, as kart 3 does.

## Left as kart 5 has them

- The one remaining operating difference, `foc_observer_gain` 3.23 M, follows this motor's own
  measurements.
- Target-specific and deliberately preserved: Hall table, motor R/L/flux and current-loop
  gains, measurement offsets, `m_invert_direction` 1, `controller_id`, and the pedal endpoints
  (ADC1 0.81–2.66 V, centre 1.74 V).
- Drivetrain metadata: **14 poles, gear 2.769, wheel diameter 0.406 m**, the same numbers as
  kart 2, where the Heltec's default 2.48 speed factor was measured. Kart 5 therefore keeps
  2.48 (if its drivetrain matches kart 2's, which the owner states).

## Not done, not verified

- Reverse filter and boards: not present when the tune was written; see the two later records
  linked above.
- Load, road, thermal or endurance behaviour; any speed cap.
- A saved-flash image: the cold-boot capture shows the values survive a restart, not a raw
  flash dump.
- The cause of the one-count offset change after the write.

## Rollback

`before/raw/motor_configuration.bin` holds the exact pre-write motor settings. There is no
tested path for writing them back.

## Evidence map

| Folder | Contents |
| --- | --- |
| `before/` | first capture, decode, Lisp read, comparison with kart 3 |
| `prepared/` | twelve-field package, never applied |
| `prepared-limits/` | the applied package: plan, both audits, proposed bytes, filter files |
| `tune-preflight/` | read-only preflight journal and capture |
| `tune-applied/` | write journal ending in the uncertain status, captures before and after, the frame sent |
| `after/` | independent capture and comparison with `before/` |
| `coldboot/` | capture after the power cycle, comparison with `after/`, Lisp read |
| `pedal-check/` | telemetry trace and its summary |
| `filter/` | reverse-filter observations, install journal, status checks and pedal check |
