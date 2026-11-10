# Kart 3 motor tune trial — PREPARED ONLY

**No settings applied. This is a proposed trial prepared from the owner's tune-matching request, not a safety certification.**', '
A later COMM_SET_MCCONF (13) operation persists the complete motor configuration through conf_general_store_mc_configuration before applying it. This is NOT a temporary store=0 profile write. This tool does not send or construct a serial write frame, and a runtime export is not a verified saved-flash backup.

All 187 application settings and all nonallowlisted motor bytes remain unchanged. The reported reverse-switch issue is not changed by this trial.

| Motor field | Current snapshot | Proposed trial |
| --- | ---: | ---: |
| l_current_max | 120.0 | 140.0 |
| l_current_min | -50.0 | 0.0 |
| l_in_current_max | 90.0 | 100.0 |
| l_min_erpm | -100000.0 | -150000.0 |
| l_max_erpm | 100000.0 | 150000.0 |
| l_max_duty | 0.99 | 0.95 |
| foc_fw_current_max | 15.0 | 95.0 |
| foc_fw_duty_start | 0.9 | 0.87 |
| foc_openloop_rpm | 800.0 | 700.0 |
| foc_sl_erpm | 2000.0 | 4000.0 |
| cc_ramp_step_max | 0.02 | 0.04 |
| m_motor_temp_sens_type | 0 | 8 |

## Limits and preservation

- Proposed trial prepared from the owner's tune-matching request; the owner did not individually select these twelve values. In particular, 15 to 95 A field weakening is a 6.33x increase; historical use does not establish physical ratings or thermal headroom.
- All application bytes stay unchanged, including ADC endpoints, reverse/input selection, CAN identity and every other app setting. This trial does not diagnose or fix the reported reverse-switch issue (throttle on ADC1, reverse switch on TX).
- Retain Hall mapping, motor R/L/flux, gains, offsets, position calibration, hardware phase filters, drivetrain metadata, battery regen -12 A, speed-PID braking 0, absolute overcurrent 220 A and minimum VIN 60 V.
- Changing the unwired motor-temperature sensor selection to Disabled does not create motor-temperature protection. A zero motor-braking allowance does not prove every regenerative path is disabled.
- The baseline drivetrain metadata is known-questionable and uses a Heltec 2.48 compensation. No poles/gearing/wheel/speedcal change is part of this trial.
- cc_ramp_step_max is described for DC/BLDC; both captured motors use FOC. Copying it is not evidence of improved FOC acceleration.
- The before snapshot remains dated runtime evidence. Preparing files does not establish present stationary state, current settings, saved-flash backup or successful application.

## Before any application

- Separate reviewed application procedure; no apply/device option is implemented here.
- Verify intended USB device and exact fresh target UUID, hardware and firmware, with owner present, wheels lifted, pedals released and physical cutoff available.
- Read all four fresh payloads immediately before writing; require complete motor/app bytes exactly equal to expected_before and stationary zero-current, zero-ERPM, fault-free telemetry. Reject any mismatch, do not regenerate silently.
- If subsequently implemented and reviewed: at most one persistent full MCCONF write, no retry after timeout/partial send/missing ACK, no reset, motor detection or motor command; never write APPCONF.
- Require exact write ACK and a new complete four-payload readback; all 376 fields and preserved raw bytes must match. Record timestamped before/after manifests and classify missing ACK/readback or unexpected changes as ambiguous rather than success.

The full 376-field audit, exact byte spans and expected hashes are in `trial.json`. `proposed_motor_response.bin` is a response-shaped analysis artifact, not a serial write frame. `before/` and `reference/` contain unchanged copies of the original dated input evidence.
