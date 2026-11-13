# Kart 4 VESC: capture, review and tune write — 2026-11-13

Kart 4's controller was captured read-only, compared with kart 3, and then given kart 3's
operating tune by one persistent motor-configuration write that the owner approved after
reviewing the differences. **The reverse filter is not installed and no Heltec or Core2 was
involved.** Kart 4 is not commissioned by this record.

| Item | Value |
| --- | --- |
| Controller | firmware 6.02 (test 0), reports `75_300_R2`, `no_hw_limits` |
| UUID | `55004d000951343037353739` (not kart 3's, not a reserved controller) |
| VESC `controller_id` | 88 (unchanged; this is not the fleet ID) |
| Stored Lisp | none (`no_valid_blob`) before and after |
| Motor | R 12.7 mΩ, L 80.5 µH, flux 17.42 mWb; kart 3 has 13.6 mΩ, 81.8 µH, 17.50 mWb |

## What was done, in order

1. **Read-only capture** over USB (`before/`): all 189 motor and 187 app settings, telemetry at
   rest with fault 0, and the stored-Lisp read.
2. **Comparison with kart 3's reviewed reference**
   (`kart3/2026-11-11/brake-limit-persistent-01/coldboot-forward/raw`): 49 of 376 settings
   differed (`before/vs-kart3/`).
3. **Twelve-field package** (`prepared/`), the reviewed scope. It proposed ten changes and
   left ten ordinary operating differences. It was **never applied** and is kept as the first
   review.
4. **Owner decision:** also set five protection limits to kart 3's values (below). Package
   rebuilt with `prepare_fleet_kart.py --match-protection-limits` (`prepared-limits/`,
   proposed bytes sha256 `3445625d97c3dc0dbec7b2eaca9b94c9dd5fa9525ea9f4b648b04d57e0847946`).
5. **Read-only preflight** with the new `tools/vesc/apply_fleet_tune.py` (`tune-preflight/`):
   identity, byte-identical settings and stationary telemetry confirmed; nothing sent.
6. **Owner go-ahead, then one write** (`tune-applied/`): a single `SET_MCCONF`, acknowledged,
   followed by a complete read-back. All 376 settings matched the intended result byte for
   byte; no retry, no rollback.
7. **Independent re-capture** with `capture.py` (`after/`): exactly 15 settings differ from
   `before/`, the motor bytes equal the proposed bytes and all app bytes are unchanged.
8. **Power cycle by the owner, then re-capture** (`coldboot/`): every one of the 17 packaged
   fields still holds its proposed value. Only the six `foc_offsets_*` values differ; the
   controller re-measures those at each boot. Stored Lisp still none.
9. **Wheels-up pedal check** (`pedal-check/`): 75 s of read-only telemetry at 10 Hz. Two
   forward runs (peak 14476 ERPM, 46.8 A) and three reverse runs (peak −13056 ERPM), fault 0,
   pack 77.8–80.0 V, no direction change within a run. The owner reported it felt right.

## The 15 settings changed

| Setting | Before | After (kart 3's value) | Scope |
| --- | ---: | ---: | --- |
| `l_current_max` | 120 A | 140 A | reviewed tune |
| `l_current_min` | −10 A | −5 A | reviewed tune |
| `l_in_current_max` | 250 A | 100 A | reviewed tune |
| `l_min_erpm` / `l_max_erpm` | ∓100000 | ∓150000 | reviewed tune |
| `foc_fw_current_max` | 100 A | 95 A | reviewed tune |
| `foc_fw_duty_start` | 0.90 | 0.87 | reviewed tune |
| `foc_openloop_rpm` | 1500 | 700 | reviewed tune |
| `foc_sl_erpm` | 2500 | 4000 | reviewed tune |
| `m_motor_temp_sens_type` | 0 | 8 (disabled; no sensor wired) | reviewed tune |
| `l_in_current_min` | −200 A | −12 A | protection limit, owner decision |
| `l_abs_current_max` | 420 A | 220 A | protection limit, owner decision |
| `l_min_vin` | 12 V | 60 V | protection limit, owner decision |
| `l_max_vin` | 84 V | 90 V | protection limit, owner decision |
| `m_fault_stop_time_ms` | 50 | 500 | protection limit, owner decision |

`l_max_duty` (0.95) and `cc_ramp_step_max` (0.04) are in the reviewed scope and already matched.

## Left as kart 4 has them

- Ordinary operating differences the owner was shown and left: `l_battery_cut_end` 62 V (kart 3:
  60), `foc_observer_gain` 3.29 M (follows this motor's measurements), `s_pid_allow_braking` 1,
  `bms.limit_mode` 0 and `app_ppm_conf.ctrl_type` 3 (functions the kart does not use).
- Target-specific and deliberately preserved: Hall table, motor R/L/flux and current-loop
  gains, measurement offsets, `m_invert_direction` 1, `controller_id`, the pedal endpoints
  (ADC1 0.826–2.431 V, centre 1.628 V) and the second-input range (0.367–0.371 V).
- Drivetrain metadata: **14 poles, gear 2.769, wheel diameter 0.083 m** (kart 3: 20 / 2.769 /
  0.406 m). The Heltec turns mph into ERPM with these numbers, so kart 4's speed factor must be
  its own: about **0.507** (2.48 × 0.083 / 0.406) if the drivetrain matches kart 2's, which the
  owner states. With the default 2.48 the 15 mph cap would land near 74000 ERPM.

## Not done, not verified

- Reverse filter: prepared as files in the packages, **not installed**. There is no kart 4/5
  installer; `install_rx_filter.py` is pinned to kart 3.
- Heltec and Core2: nothing flashed or paired when this record was written.
- Load, road, thermal or endurance behaviour; charged-pack over-voltage behaviour; any speed cap.
- A saved-flash image: the cold-boot capture shows the values survive a restart, not a raw
  flash dump.
- Kart 5: needs its own capture, review and approval. Nothing here applies to it.

## Rollback

`before/raw/motor_configuration.bin` holds the exact pre-write motor settings. There is no
tested path for writing them back; it would need the same kind of reviewed single write.

## Evidence map

| Folder | Contents |
| --- | --- |
| `before/` | first capture, decode, Lisp read, comparison with kart 3 |
| `prepared/` | twelve-field package, superseded, never applied |
| `prepared-limits/` | the applied package: plan, both audits, proposed bytes, filter files |
| `tune-preflight/` | read-only preflight journal and capture |
| `tune-applied/` | write journal, captures before and after, the frame sent, field audit |
| `after/` | independent capture and comparisons with `before/` and kart 3 |
| `coldboot/` | capture after the power cycle, comparison with `after/`, Lisp read |
| `pedal-check/` | telemetry trace and its summary (traced with what is now `tools/vesc/telemetry_trace.py`) |
