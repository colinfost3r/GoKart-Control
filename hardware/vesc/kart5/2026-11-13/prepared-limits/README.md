# Kart 5 replication — OFFLINE PREPARATION ONLY

**Nothing applied. Not a complete tune match or commissioned vehicle.**

| Field | Target capture | Proposed |
| --- | ---: | ---: |
| l_current_max | 100.0 | 140.0 |
| l_current_min | -50.0 | -5.0 |
| l_in_current_max | 100.0 | 100.0 |
| l_min_erpm | -100000.0 | -150000.0 |
| l_max_erpm | 100000.0 | 150000.0 |
| l_max_duty | 0.99 | 0.95 |
| foc_fw_current_max | 100.0 | 95.0 |
| foc_fw_duty_start | 0.9 | 0.87 |
| foc_openloop_rpm | 800.0 | 700.0 |
| foc_sl_erpm | 4000.0 | 4000.0 |
| cc_ramp_step_max | 0.04 | 0.04 |
| m_motor_temp_sens_type | 0 | 8 |
| l_in_current_min | -12.0 | -12.0 |
| l_abs_current_max | 300.0 | 220.0 |
| l_min_vin | 60.0 | 60.0 |
| l_max_vin | 90.0 | 90.0 |
| m_fault_stop_time_ms | 500 | 500 |

## Remaining source differences

| Configuration / field | Source | Preserved target | Review category |
| --- | ---: | ---: | --- |
| motor_configuration / foc_current_kp | 0.08179999887943268 | 0.08320000022649765 | target_specific_preserved |
| motor_configuration / foc_current_ki | 13.640000343322754 | 11.539999961853027 | target_specific_preserved |
| motor_configuration / foc_motor_l | 8.181000157492235e-05 | 8.317999891005456e-05 | target_specific_preserved |
| motor_configuration / foc_motor_ld_lq_diff | 3.10200011881534e-05 | 3.0049999622860923e-05 | target_specific_preserved |
| motor_configuration / foc_motor_r | 0.01360000018030405 | 0.011500000022351742 | target_specific_preserved |
| motor_configuration / foc_motor_flux_linkage | 0.017501000314950943 | 0.017597999423742294 | target_specific_preserved |
| motor_configuration / foc_observer_gain | 3260000.0 | 3230000.0 | operating_difference |
| motor_configuration / foc_hall_table__1 | 150 | 179 | target_specific_preserved |
| motor_configuration / foc_hall_table__2 | 5 | 119 | target_specific_preserved |
| motor_configuration / foc_hall_table__3 | 175 | 149 | target_specific_preserved |
| motor_configuration / foc_hall_table__4 | 93 | 51 | target_specific_preserved |
| motor_configuration / foc_hall_table__5 | 127 | 16 | target_specific_preserved |
| motor_configuration / foc_hall_table__6 | 47 | 82 | target_specific_preserved |
| motor_configuration / foc_offsets_current__0 | 2045.822021484375 | 2038.5400390625 | target_specific_preserved |
| motor_configuration / foc_offsets_current__1 | 2041.615966796875 | 2039.9720458984375 | target_specific_preserved |
| motor_configuration / foc_offsets_current__2 | 2042.4139404296875 | 2042.7939453125 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__0 | -0.004 | 0.0007 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__1 | 0.0048 | -0.0062 | target_specific_preserved |
| motor_configuration / foc_offsets_voltage__2 | -0.0008 | 0.0055 | target_specific_preserved |
| motor_configuration / m_invert_direction | 0 | 1 | target_specific_preserved |
| motor_configuration / si_motor_poles | 20 | 14 | target_specific_preserved |
| app_configuration / controller_id | 19 | 52 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage_start | 0.69 | 0.81 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage_end | 2.67 | 2.66 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage_center | 1.68 | 1.74 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage2_start | 0.33 | 0.36 | target_specific_preserved |
| app_configuration / app_adc_conf.voltage2_end | 3.3 | 0.37 | target_specific_preserved |

## Boundaries

- This copies exactly twelve named operating settings, not the complete source tune. By explicit owner decision it also copies five protection limits: l_in_current_min, l_abs_current_max, l_min_vin, l_max_vin, m_fault_stop_time_ms.
- Every remaining motor/app difference is listed and requires review. Resolve ordinary operating-limit differences before commissioning; never silently copy calibration to make a full match.
- Target current scales are preserved and must be reviewed against source 1.0 / 1.0; battery regeneration is copied with the protection limits.
- Hall/motor parameters, controller measurement offsets, pedal endpoints, drivetrain metadata and all identities remain target-specific bytes. Kart ID is not the VESC controller_id.
- These dated runtime captures do not verify saved flash, present stationary state, hardware ratings or physical calibration. Complete backups and fresh matching readbacks are required before a separately reviewed write.
- Existing kart-3 apply_tune/install_rx_filter/RAM lifecycle helpers remain pinned to kart 3 and must not be used or have pins bypassed for this plan.
- Native ADC precedes Lisp startup; watchdog startup may skip Lisp; failed worker can hold direction. Keep pedal released until applied direction/live worker are verified. Repair the switch circuit independently.
- No serial, network, motor, configuration, flash or lifecycle action is available in this tool.
