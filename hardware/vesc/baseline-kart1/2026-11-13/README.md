# Kart 1 VESC (75_300_R2, fw 6.02, uuid 360052000951343037353739): VESC Tool XML exports, 2026-11-13

Read over Bluetooth with VESC Tool 6.06 ("limited mode"), saved by the owner. `*-before.xml` is the
controller as found; `kart1-motor.xml` / `kart1-app.xml` are after the owner matched it to kart 2
(Colin's capture in ../../baseline-kart/2026-11-05). Compare with `python3 scratch/diff` or any XML diff.

Why: kart 1 was "much slower" than kart 2 with identical motor and gearing. Telemetry showed kart 1
never exceeding 36.6 A motor / ~30k ERPM where kart 2 reached 94.6 A / 43.2k ERPM at the same duty
and voltage. The exports explained it:

| field | before | after (= kart 2 unless noted) |
| --- | --- | --- |
| foc_motor_r | 0.0025 Ω | 0.018 Ω |
| foc_current_ki / kp | 2.52 / 0.0836 | 18.03 / 0.0835 |
| foc_fw_duty_start | 0.90 | 0.87 |
| foc_openloop_rpm / foc_sl_erpm | 1500 / 1500 | 700 / 4000 |
| foc_hall_interp_erpm | 750 | 500 |
| foc_sat_comp_mode | 0 (off) | 2 (lambda) |
| l_current_min (brake) | -50 A | 0 |
| ADC voltage_start / end / center | 0.88 / 3.30 / 2.14 | 0.84 / 2.28 / 1.56 (measured on kart 1's pedal; kart 2: 0.837 / 2.385) |
| ADC hyst | 0 | 0.15 |
| app_to_use | 2 (ADC) | 5 (ADC and UART) |

Left alone: flux linkage 17.957 mWb (kart 2: 17.60, measured), hall table and m_invert_direction
(wiring-specific), the live ECO limits the Heltec applies (l_max_erpm 15163, current scale 0.5,
duty start 0.8: temporary, do not write them). controller_id changed 45 -> 105 during the app write
(unexplained; nothing addresses it over CAN).
