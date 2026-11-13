# Kart 4 replication — OFFLINE PREPARATION ONLY

**Nothing applied. Not a complete tune match or commissioned vehicle.**

| Field | Target capture | Proposed |
| --- | ---: | ---: |
| l_current_max | 120.0 | 140.0 |
| l_current_min | -10.0 | -5.0 |
| l_in_current_max | 250.0 | 100.0 |
| l_min_erpm | -100000.0 | -150000.0 |
| l_max_erpm | 100000.0 | 150000.0 |
| l_max_duty | 0.95 | 0.95 |
| foc_fw_current_max | 100.0 | 95.0 |
| foc_fw_duty_start | 0.9 | 0.87 |
| foc_openloop_rpm | 1500.0 | 700.0 |
| foc_sl_erpm | 2500.0 | 4000.0 |
| cc_ramp_step_max | 0.04 | 0.04 |
| m_motor_temp_sens_type | 0 | 8 |

## Remaining source differences

| Configuration / field | Source | Preserved target | Review category |
| --- | ---: | ---: | --- |
| motor_configuration / l_in_current_min | -12.0 | -200.0 | operating_difference |
| motor_configuration / l_abs_current_max | 220.0 | 420.0 | operating_difference |
| motor_configuration / l_min_vin | 60.0 | 12.0 | operating_difference |
| motor_configuration / l_max_vin | 90.0 | 84.0 | operating_difference |
| motor_configuration / l_battery_cut_end | 60.0 | 62.0 | operating_difference |
| motor_configuration / foc_current_kp | 0.08179999887943268 | 0.08049999922513962 | target_specific_preserved |
| motor_configuration / foc_current_ki | 13.640000343322754 | 12.710000038146973 | target_specific_preserved |
| motor_configuration / foc_motor_l | 8.181000157492235e-05 | 8.053000055951998e-05 | target_specific_preserved |
| motor_configuration / foc_motor_ld_lq_diff | 3.10200011881534e-05 | 2.5839999580057338e-05 | target_specific_preserved |
| motor_configuration / foc_motor_r | 0.01360000018030405 | 0.01269999984651804 | target_specific_preserved |
| motor_configuration / foc_motor_flux_linkage | 0.017501000314950943 | 0.017424000427126884 | target_specific_preserved |
| motor_configuration / foc_observer_gain | 3260000.0 | 3290000.0 | operating_difference |
| motor_configuration / foc_hall_table__1 | 150 | 48 | target_specific_preserved |
| motor_configuration / foc_hall_table__2 | 5 | 179 | target_specific_preserved |
| motor_configuration / foc_hall_table__3 | 175 | 16 | target_specific_preserved |
| motor_configuration / foc_hall_table__4 | 93 | 118 | target_specific_preserved |
| motor_configuration / foc_hall_table__5 | 127 | 85 | target_specific_preserved |
| motor_configuration / foc_hall_table__6 | 47 | 147 | target_specific_preserved |
| motor_configuration / foc_offsets_current__0 | 2045.822021484375 | 2052.300048828125 | target_specific_preserved |
| motor_configuration / foc_offsets_current__1 | 2041.615966796875 | 2048.0390625 | target_specific_preserved |
| motor_configuration / foc_offsets_current__2 | 2042.4139404296875 | 2052.0791015625 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__0 | -0.004 | 0.0029 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__1 | 0.0048 | 0.0072 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__2 | -0.0008 | -0.0102 | target_specific_preserved |
| motor_configuration / s_pid_allow_braking | 0 | 1 | operating_difference |
| motor_configuration / p_pid_offset | 27.0 | 0.0 | target_specific_preserved |
| motor_configuration / m_fault_stop_time_ms | 500 | 50 | operating_difference |
| motor_configuration / m_invert_direction | 0 | 1 | target_specific_preserved |
| motor_configuration / si_motor_poles | 20 | 14 | target_specific_preserved |
| motor_configuration / si_wheel_diameter | 0.4059999883174896 | 0.08299999684095383 | target_specific_preserved |
| motor_configuration / si_battery_ah | 20.0 | 6.0 | target_specific_preserved |
| motor_configuration / bms.limit_mode | 3 | 0 | operating_difference |
| app_configuration / controller_id | 19 | 88 | target_specific_preserved |
| app_configuration / app_ppm_conf.ctrl_type | 0 | 3 | operating_difference |
| app_configuration / app_adc_conf.voltage_start | 0.69 | 0.826 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage_end | 2.67 | 2.431 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage_center | 1.68 | 1.628 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage2_start | 0.33 | 0.367 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage2_end | 3.3 | 0.371 | target_specific_preserved |

## Boundaries

- This copies exactly twelve named operating settings, not the complete source tune.
- Every remaining motor/app difference is listed and requires review. Resolve ordinary operating-limit differences before commissioning; never silently copy calibration to make a full match.
- In particular, target battery-regeneration l_in_current_min and current scales are preserved and must be reviewed against source -12 A / 1.0 / 1.0.
- Hall/motor parameters, controller measurement offsets, pedal endpoints, drivetrain metadata and all identities remain target-specific bytes. Kart ID is not the VESC controller_id.
- These dated runtime captures do not verify saved flash, present stationary state, hardware ratings or physical calibration. Complete backups and fresh matching readbacks are required before a separately reviewed write.
- Existing kart-3 apply_tune/install_rx_filter/RAM lifecycle helpers remain pinned to kart 3 and must not be used or have pins bypassed for this plan.
- Native ADC precedes Lisp startup; watchdog startup may skip Lisp; failed worker can hold direction. Keep pedal released until applied direction/live worker are verified. Repair the switch circuit independently.
- No serial, network, motor, configuration, flash or lifecycle action is available in this tool.
