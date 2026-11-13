# VESC runtime settings comparison

376 fields: 326 equal, 50 different. No settings applied or recommended.

Generated: 2026-11-10T19:33:18.401155+00:00

- This is an offline comparison of dated, sequential runtime reads, not current live state, an atomic snapshot, a saved-flash backup, or a tuning/import preset.
- Equal/different means exact decoded value equality; no tolerance, preferred value, copy decision or automatic change recommendation is applied.
- The November 5, 2026 baseline is historical runtime evidence; it does not establish kart 2's current tune. The candidate capture is dated separately below; refresh both reads before applying a tune.
- The project handoff dated November 10 reports kart 2 drivetrain values wrong by about 2.5x and a Heltec speed-calibration factor of 2.48 compensating for them. Do not blindly copy si_motor_poles, si_gear_ratio or si_wheel_diameter, or set speedcal to 1.0 without physical measurement and speed validation. Heltec speedcal is not in these VESC captures.
- Matching motor/battery/BMS/gearing/wheel models does not make controller/motor calibration, pedal endpoints, identities or protection settings interchangeable.
- Motor-temperature sensors on these karts are not wired; a raw motor-temperature value is not a valid measured motor temperature. ESC temperature is separate.
- Payload hashes are checked against the supplied manifests. Transport CRC verification is a capture-time manifest claim; raw payload files omit transport frames.

## Captured controllers

| Item | Reference | Candidate |
| --- | --- | --- |
| uuid | 2c004c000951343037353739 | 37004e000951343037353739 |
| firmware | 6.00 | 6.02 |
| hardware | 75_100_V2 | 75_300_R2 |
| firmware_name | no_hw_limits | no_hw_limits |

### Reference provenance

- Raw directory: /Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/hardware/vesc/baseline-kart/2026-11-05/raw
- Manifest: /Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/hardware/vesc/baseline-kart/2026-11-05/manifest.json
- Manifest SHA-256: 0e29a23e14ded6842c6056fd54db8a9a668239bad6152a2be500d91aca293e8a
- Scope: current_runtime_not_verified_saved_flash
- Transport: usb_serial
- Manifest controller assignment: baseline-kart; race kart number unassigned
- Recorded procedure: Initial allowlisted read-only script; maintained CLI added afterward. No writes, motor commands, reset, flash or CAN scan.

| Payload | Captured at | Timestamp basis | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| firmware | 2026-11-05T13:13:30.294726-05:00 | capture_file_mtime | 46 | 067690f5db0ba20ec2d73dfac1f7aeb72eafe4d55549c4f5eadad40e65902e69 |
| telemetry | 2026-11-05T13:13:54.810309-05:00 | capture_file_mtime | 74 | 0dc228aa475e4f9fa2bf8760d99a0f704078b7a8a851363c396e8cfbbc4aaf4a |
| motor_configuration | 2026-11-05T13:13:54.914650-05:00 | capture_file_mtime | 482 | 80ca33b7e5e5b0bfc08d039337f20c1ecf7f04b8726e35e87d938d40af33f0b0 |
| app_configuration | 2026-11-05T13:13:55.021212-05:00 | capture_file_mtime | 494 | df26cba6b5e919cab3b9601deb5845e6ab24a2d53da86728d81147aa84877d05 |

### Candidate provenance

- Raw directory: /Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/hardware/vesc/kart3/2026-11-10/usb-before-tune/raw
- Manifest: /Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/hardware/vesc/kart3/2026-11-10/usb-before-tune/raw/manifest.json
- Manifest SHA-256: 9e7115f3e2b17398a25f0799a65ea4f5af3fe21a343cdf83632fe7d666cca25a
- Scope: current_runtime_not_verified_saved_flash
- Transport: usb_serial
- Manifest controller assignment: not recorded
- Recorded procedure: not recorded

| Payload | Captured at | Timestamp basis | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| firmware | 2026-11-10T19:28:31.614295+00:00 | capture_query_clock | 46 | 750a84dbec2e8ee6507d87142a99d09a58475bd8413891f819db8fa71107aab5 |
| telemetry | 2026-11-10T19:28:31.718220+00:00 | capture_query_clock | 74 | 7d22300dca66942969b8c34356038c974d1b6e2fa7be4bca5e370aed69bde588 |
| motor_configuration | 2026-11-10T19:28:31.825308+00:00 | capture_query_clock | 482 | 57cef3f6d0d726a477a785f6d2db73c1878871e9aa23f4c9c061cd99c7603b65 |
| app_configuration | 2026-11-10T19:28:31.927520+00:00 | capture_query_clock | 494 | 2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d |

## Motor Configuration

Signature `2e43a161`; 189 fields, 149 equal, 40 different.

| Field | Reference | Candidate | Result |
| --- | --- | --- | --- |
| pwm_mode | 1 (Synchronous) | 1 (Synchronous) | equal |
| comm_mode | 0 (Integrate) | 0 (Integrate) | equal |
| motor_type | 2 (FOC) | 2 (FOC) | equal |
| sensor_mode | 0 (Sensorless) | 0 (Sensorless) | equal |
| l_current_max | 140.0 | 120.0 | different |
| l_current_min | 0.0 | -50.0 | different |
| l_in_current_max | 100.0 | 90.0 | different |
| l_in_current_min | -100.0 | -12.0 | different |
| l_abs_current_max | 240.0 | 220.0 | different |
| l_min_erpm | -150000.0 | -100000.0 | different |
| l_max_erpm | 150000.0 | 100000.0 | different |
| l_erpm_start | 0.8 | 0.8 | equal |
| l_max_erpm_fbrake | 300.0 | 300.0 | equal |
| l_max_erpm_fbrake_cc | 1500.0 | 1500.0 | equal |
| l_min_vin | 12.0 | 60.0 | different |
| l_max_vin | 90.0 | 90.0 | equal |
| l_battery_cut_start | 68.0 | 68.0 | equal |
| l_battery_cut_end | 60.0 | 60.0 | equal |
| l_slow_abs_current | 0 | 0 | equal |
| l_temp_fet_start | 85.0 | 85.0 | equal |
| l_temp_fet_end | 100.0 | 100.0 | equal |
| l_temp_motor_start | 85.0 | 85.0 | equal |
| l_temp_motor_end | 100.0 | 100.0 | equal |
| l_temp_accel_dec | 0.15 | 0.15 | equal |
| l_min_duty | 0.005 | 0.005 | equal |
| l_max_duty | 0.95 | 0.99 | different |
| l_watt_max | 1500000.0 | 1500000.0 | equal |
| l_watt_min | -1500000.0 | -1500000.0 | equal |
| l_current_max_scale | 1.0 | 1.0 | equal |
| l_current_min_scale | 1.0 | 1.0 | equal |
| l_duty_start | 1.0 | 1.0 | equal |
| sl_min_erpm | 150.0 | 150.0 | equal |
| sl_min_erpm_cycle_int_limit | 1100.0 | 1100.0 | equal |
| sl_max_fullbreak_current_dir_change | 10.0 | 10.0 | equal |
| sl_cycle_int_limit | 62.0 | 62.0 | equal |
| sl_phase_advance_at_br | 0.8 | 0.8 | equal |
| sl_cycle_int_rpm_br | 80000.0 | 80000.0 | equal |
| sl_bemf_coupling_k | 600.0 | 600.0 | equal |
| hall_table__0 | -1 | -1 | equal |
| hall_table__1 | 1 | 1 | equal |
| hall_table__2 | 3 | 3 | equal |
| hall_table__3 | 2 | 2 | equal |
| hall_table__4 | 5 | 5 | equal |
| hall_table__5 | 6 | 6 | equal |
| hall_table__6 | 4 | 4 | equal |
| hall_table__7 | -1 | -1 | equal |
| hall_sl_erpm | 2000.0 | 2000.0 | equal |
| foc_current_kp | 0.08353837579488754 | 0.08179999887943268 | different |
| foc_current_ki | 18.026309967041016 | 13.640000343322754 | different |
| foc_f_zv | 30000.0 | 30000.0 | equal |
| foc_dt_us | 0.11999999731779099 | 0.11999999731779099 | equal |
| foc_encoder_inverted | 0 | 0 | equal |
| foc_encoder_offset | 180.0 | 180.0 | equal |
| foc_encoder_ratio | 7.0 | 7.0 | equal |
| foc_sensor_mode | 2 (Hall Sensors) | 2 (Hall Sensors) | equal |
| foc_pll_kp | 2000.0 | 2000.0 | equal |
| foc_pll_ki | 30000.0 | 30000.0 | equal |
| foc_motor_l | 8.353838347829878e-05 | 8.181000157492235e-05 | different |
| foc_motor_ld_lq_diff | 3.433670644881204e-05 | 3.10200011881534e-05 | different |
| foc_motor_r | 0.018026310950517654 | 0.01360000018030405 | different |
| foc_motor_flux_linkage | 0.017599789425730705 | 0.017501000314950943 | different |
| foc_observer_gain | 3228383.0 | 3260000.0 | different |
| foc_observer_gain_slow | 0.05000000074505806 | 0.05000000074505806 | equal |
| foc_observer_offset | -1.0 | -1.0 | equal |
| foc_duty_dowmramp_kp | 50.0 | 50.0 | equal |
| foc_duty_dowmramp_ki | 1000.0 | 1000.0 | equal |
| foc_start_curr_dec | 1.0 | 1.0 | equal |
| foc_start_curr_dec_rpm | 2500.0 | 2500.0 | equal |
| foc_openloop_rpm | 700.0 | 800.0 | different |
| foc_openloop_rpm_low | 0.0 | 0.0 | equal |
| foc_d_gain_scale_start | 0.9 | 0.9 | equal |
| foc_d_gain_scale_max_mod | 0.2 | 0.2 | equal |
| foc_sl_openloop_hyst | 0.1 | 0.1 | equal |
| foc_sl_openloop_time_lock | 0.0 | 0.0 | equal |
| foc_sl_openloop_time_ramp | 0.1 | 0.1 | equal |
| foc_sl_openloop_time | 0.05 | 0.05 | equal |
| foc_sl_openloop_boost_q | 0.0 | 0.0 | equal |
| foc_sl_openloop_max_q | -1.0 | -1.0 | equal |
| foc_hall_table__0 | 255 | 255 | equal |
| foc_hall_table__1 | 15 | 150 | different |
| foc_hall_table__2 | 81 | 5 | different |
| foc_hall_table__3 | 48 | 175 | different |
| foc_hall_table__4 | 149 | 93 | different |
| foc_hall_table__5 | 183 | 127 | different |
| foc_hall_table__6 | 115 | 47 | different |
| foc_hall_table__7 | 255 | 255 | equal |
| foc_hall_interp_erpm | 500.0 | 500.0 | equal |
| foc_sl_erpm | 4000.0 | 2000.0 | different |
| foc_sample_v0_v7 | 0 | 0 | equal |
| foc_sample_high_current | 0 | 0 | equal |
| foc_sat_comp_mode | 2 (Lambda) | 2 (Lambda) | equal |
| foc_sat_comp | 0.0 | 0.0 | equal |
| foc_temp_comp | 0 | 0 | equal |
| foc_temp_comp_base_temp | 0.0 | 25.0 | different |
| foc_current_filter_const | 0.1 | 0.1 | equal |
| foc_cc_decoupling | 0 (FOC_CC_DECOUPLING_DISABLED) | 0 (FOC_CC_DECOUPLING_DISABLED) | equal |
| foc_observer_type | 3 (FOC_OBSERVER_MXLEMMING_LAMBDA_COMP) | 3 (FOC_OBSERVER_MXLEMMING_LAMBDA_COMP) | equal |
| foc_hfi_voltage_start | 20.0 | 20.0 | equal |
| foc_hfi_voltage_run | 4.0 | 4.0 | equal |
| foc_hfi_voltage_max | 6.0 | 6.0 | equal |
| foc_hfi_gain | 0.3 | 0.3 | equal |
| foc_hfi_hyst | 0.0 | 0.0 | equal |
| foc_sl_erpm_hfi | 3000.0 | 3000.0 | equal |
| foc_hfi_start_samples | 5 | 5 | equal |
| foc_hfi_obs_ovr_sec | 0.0010000000474974513 | 0.0010000000474974513 | equal |
| foc_hfi_samples | 1 (16) | 1 (16) | equal |
| foc_offsets_cal_on_boot | 1 | 1 | equal |
| foc_offsets_current__0 | 2039.4830322265625 | 2045.0849609375 | different |
| foc_offsets_current__1 | 2041.508056640625 | 2041.3380126953125 | different |
| foc_offsets_current__2 | 2048.761962890625 | 2041.3060302734375 | different |
| foc_offsets_voltage__0 | -0.007 | -0.0041 | different |
| foc_offsets_voltage__1 | 0.0042 | 0.0043 | different |
| foc_offsets_voltage__2 | 0.0027 | -0.0002 | different |
| foc_offsets_voltage_undriven__0 | 0.0 | 0.0 | equal |
| foc_offsets_voltage_undriven__1 | 0.0 | 0.0 | equal |
| foc_offsets_voltage_undriven__2 | 0.0 | 0.0 | equal |
| foc_phase_filter_enable | 0 | 1 | different |
| foc_phase_filter_disable_fault | 1 | 1 | equal |
| foc_phase_filter_max_erpm | 4000.0 | 4000.0 | equal |
| foc_mtpa_mode | 0 (Disabled) | 0 (Disabled) | equal |
| foc_fw_current_max | 95.0 | 15.0 | different |
| foc_fw_duty_start | 0.87 | 0.9 | different |
| foc_fw_ramp_time | 0.2 | 0.2 | equal |
| foc_fw_q_current_factor | 0.02 | 0.02 | equal |
| foc_speed_soure | 1 (Observer) | 1 (Observer) | equal |
| gpd_buffer_notify_left | 200 | 200 | equal |
| gpd_buffer_interpol | 0 | 0 | equal |
| gpd_current_filter_const | 0.1 | 0.1 | equal |
| gpd_current_kp | 0.029999999329447746 | 0.029999999329447746 | equal |
| gpd_current_ki | 50.0 | 50.0 | equal |
| sp_pid_loop_rate | 5 (1000 Hz) | 5 (1000 Hz) | equal |
| s_pid_kp | 0.004000000189989805 | 0.004000000189989805 | equal |
| s_pid_ki | 0.004000000189989805 | 0.004000000189989805 | equal |
| s_pid_kd | 9.999999747378752e-05 | 9.999999747378752e-05 | equal |
| s_pid_kd_filter | 0.2 | 0.2 | equal |
| s_pid_min_erpm | 900.0 | 900.0 | equal |
| s_pid_allow_braking | 1 | 0 | different |
| s_pid_ramp_erpms_s | 25000.0 | 25000.0 | equal |
| p_pid_kp | 0.02500000037252903 | 0.02500000037252903 | equal |
| p_pid_ki | 0.0 | 0.0 | equal |
| p_pid_kd | 0.0 | 0.0 | equal |
| p_pid_kd_proc | 0.0003499999875202775 | 0.0003499999875202775 | equal |
| p_pid_kd_filter | 0.2 | 0.2 | equal |
| p_pid_ang_div | 1.0 | 1.0 | equal |
| p_pid_gain_dec_angle | 0.0 | 0.0 | equal |
| p_pid_offset | 0.0 | 27.0 | different |
| cc_startup_boost_duty | 0.01 | 0.01 | equal |
| cc_min_current | 0.05000000074505806 | 0.05000000074505806 | equal |
| cc_gain | 0.004600000102072954 | 0.004600000102072954 | equal |
| cc_ramp_step_max | 0.04 | 0.02 | different |
| m_fault_stop_time_ms | 500 | 500 | equal |
| m_duty_ramp_step | 0.02 | 0.02 | equal |
| m_current_backoff_gain | 0.5 | 0.5 | equal |
| m_encoder_counts | 8192 | 8192 | equal |
| m_encoder_sin_amp | 1.0 | 1.0 | equal |
| m_encoder_cos_amp | 1.0 | 1.0 | equal |
| m_encoder_sin_offset | 1.65 | 1.65 | equal |
| m_encoder_cos_offset | 1.65 | 1.65 | equal |
| m_encoder_sincos_filter_constant | 0.5 | 0.5 | equal |
| m_encoder_sincos_phase_correction | 0.0 | 0.0 | equal |
| m_sensor_port_mode | 0 (Hall Sensors) | 0 (Hall Sensors) | equal |
| m_invert_direction | 0 | 0 | equal |
| m_drv8301_oc_mode | 0 (Current Limit) | 0 (Current Limit) | equal |
| m_drv8301_oc_adj | 16 | 16 | equal |
| m_bldc_f_sw_min | 3000.0 | 3000.0 | equal |
| m_bldc_f_sw_max | 35000.0 | 35000.0 | equal |
| m_dc_f_sw | 25000.0 | 25000.0 | equal |
| m_ntc_motor_beta | 3380.0 | 3380.0 | equal |
| m_out_aux_mode | 0 (Off) | 0 (Off) | equal |
| m_motor_temp_sens_type | 8 (Disabled) | 0 (NTC 10K at 25°C) | different |
| m_ptc_motor_coeff | 0.6100000143051147 | 0.6100000143051147 | equal |
| m_ntcx_ptcx_res | 10000.0 | 10000.0 | equal |
| m_ntcx_ptcx_temp_base | 25.0 | 25.0 | equal |
| m_hall_extra_samples | 1 | 1 | equal |
| m_batt_filter_const | 45 | 45 | equal |
| si_motor_poles | 14 | 20 | different |
| si_gear_ratio | 2.769230842590332 | 2.7690000534057617 | different |
| si_wheel_diameter | 0.4059999883174896 | 0.4059999883174896 | equal |
| si_battery_type | 0 (BATTERY_TYPE_LIION_3_0__4_2) | 0 (BATTERY_TYPE_LIION_3_0__4_2) | equal |
| si_battery_cells | 20 | 20 | equal |
| si_battery_ah | 20.0 | 20.0 | equal |
| si_motor_nl_current | 1.0 | 1.0 | equal |
| bms.type | 1 (VESC BMS) | 1 (VESC BMS) | equal |
| bms.limit_mode | 3; bits: ["Overtemp", "SOC"] | 3; bits: ["Overtemp", "SOC"] | equal |
| bms.t_limit_start | 45.0 | 45.0 | equal |
| bms.t_limit_end | 65.0 | 65.0 | equal |
| bms.soc_limit_start | 0.05 | 0.05 | equal |
| bms.soc_limit_end | 0.0 | 0.0 | equal |
| bms.fwd_can_mode | 0 (Disabled) | 0 (Disabled) | equal |

## App Configuration

Signature `1d003a2c`; 187 fields, 177 equal, 10 different.

| Field | Reference | Candidate | Result |
| --- | --- | --- | --- |
| controller_id | 69 | 19 | different |
| timeout_msec | 1000 | 1000 | equal |
| timeout_brake_current | 0.0 | 0.0 | equal |
| can_status_rate_1 | 50 | 50 | equal |
| can_status_rate_2 | 5 | 5 | equal |
| can_status_msgs_r1 | 15; bits: ["Status 1", "Status 2", "Status 3", "Status 4"] | 0; bits: [] | different |
| can_status_msgs_r2 | 0; bits: [] | 0; bits: [] | equal |
| can_baud_rate | 2 (CAN_BAUD_500K) | 2 (CAN_BAUD_500K) | equal |
| pairing_done | 0 | 0 | equal |
| permanent_uart_enabled | 1 | 1 | equal |
| shutdown_mode | 7 (OFF_AFTER_30M) | 7 (OFF_AFTER_30M) | equal |
| can_mode | 0 (VESC) | 0 (VESC) | equal |
| uavcan_esc_index | 0 | 0 | equal |
| uavcan_raw_mode | 0 (Current Control) | 0 (Current Control) | equal |
| uavcan_raw_rpm_max | 50000.0 | 50000.0 | equal |
| uavcan_status_current_mode | 0 (Motor Current) | 0 (Motor Current) | equal |
| servo_out_enable | 0 | 0 | equal |
| kill_sw_mode | 0 (Disabled) | 0 (Disabled) | equal |
| app_to_use | 5 (ADC and UART) | 2 (ADC) | different |
| app_ppm_conf.ctrl_type | 3 (Current No Reverse With Brake) | 0 (Off) | different |
| app_ppm_conf.pid_max_erpm | 15000.0 | 15000.0 | equal |
| app_ppm_conf.hyst | 0.15000000596046448 | 0.15000000596046448 | equal |
| app_ppm_conf.pulse_start | 1.0 | 1.0 | equal |
| app_ppm_conf.pulse_end | 2.0 | 2.0 | equal |
| app_ppm_conf.pulse_center | 1.5 | 1.5 | equal |
| app_ppm_conf.median_filter | 1 | 1 | equal |
| app_ppm_conf.safe_start | 1 (Regular) | 1 (Regular) | equal |
| app_ppm_conf.throttle_exp | 0.0 | 0.0 | equal |
| app_ppm_conf.throttle_exp_brake | 0.0 | 0.0 | equal |
| app_ppm_conf.throttle_exp_mode | 2 (Polynomial) | 2 (Polynomial) | equal |
| app_ppm_conf.ramp_time_pos | 0.4000000059604645 | 0.4000000059604645 | equal |
| app_ppm_conf.ramp_time_neg | 0.20000000298023224 | 0.20000000298023224 | equal |
| app_ppm_conf.multi_esc | 1 | 1 | equal |
| app_ppm_conf.tc | 0 | 0 | equal |
| app_ppm_conf.tc_max_diff | 3000.0 | 3000.0 | equal |
| app_ppm_conf.max_erpm_for_dir | 4000.0 | 4000.0 | equal |
| app_ppm_conf.smart_rev_max_duty | 0.07000000029802322 | 0.07000000029802322 | equal |
| app_ppm_conf.smart_rev_ramp_time | 3.0 | 3.0 | equal |
| app_adc_conf.ctrl_type | 3 (Current Reverse Button) | 3 (Current Reverse Button) | equal |
| app_adc_conf.hyst | 0.15000000596046448 | 0.15000000596046448 | equal |
| app_adc_conf.voltage_start | 0.837 | 0.69 | different |
| app_adc_conf.voltage_end | 2.385 | 2.67 | different |
| app_adc_conf.voltage_min | 0.0 | 0.0 | equal |
| app_adc_conf.voltage_max | 3.5 | 3.5 | equal |
| app_adc_conf.voltage_center | 1.663 | 1.68 | different |
| app_adc_conf.voltage2_start | 1.501 | 0.33 | different |
| app_adc_conf.voltage2_end | 1.515 | 3.3 | different |
| app_adc_conf.use_filter | 1 | 1 | equal |
| app_adc_conf.safe_start | 1 (Regular) | 1 (Regular) | equal |
| app_adc_conf.buttons | 0; bits: [] | 0; bits: [] | equal |
| app_adc_conf.voltage_inverted | 0 | 0 | equal |
| app_adc_conf.voltage2_inverted | 0 | 0 | equal |
| app_adc_conf.throttle_exp | 0.0 | 0.0 | equal |
| app_adc_conf.throttle_exp_brake | 0.0 | 0.0 | equal |
| app_adc_conf.throttle_exp_mode | 2 (Polynomial) | 2 (Polynomial) | equal |
| app_adc_conf.ramp_time_pos | 0.30000001192092896 | 0.30000001192092896 | equal |
| app_adc_conf.ramp_time_neg | 0.10000000149011612 | 0.10000000149011612 | equal |
| app_adc_conf.multi_esc | 1 | 1 | equal |
| app_adc_conf.tc | 0 | 0 | equal |
| app_adc_conf.tc_max_diff | 3000.0 | 3000.0 | equal |
| app_adc_conf.update_rate_hz | 500 | 500 | equal |
| app_uart_baudrate | 115200 | 115200 | equal |
| app_chuk_conf.ctrl_type | 0 (Off) | 0 (Off) | equal |
| app_chuk_conf.hyst | 0.15000000596046448 | 0.15000000596046448 | equal |
| app_chuk_conf.ramp_time_pos | 0.4000000059604645 | 0.4000000059604645 | equal |
| app_chuk_conf.ramp_time_neg | 0.20000000298023224 | 0.20000000298023224 | equal |
| app_chuk_conf.stick_erpm_per_s_in_cc | 3000.0 | 3000.0 | equal |
| app_chuk_conf.throttle_exp | 0.0 | 0.0 | equal |
| app_chuk_conf.throttle_exp_brake | 0.0 | 0.0 | equal |
| app_chuk_conf.throttle_exp_mode | 2 (Polynomial) | 2 (Polynomial) | equal |
| app_chuk_conf.multi_esc | 1 | 1 | equal |
| app_chuk_conf.tc | 0 | 0 | equal |
| app_chuk_conf.tc_max_diff | 3000.0 | 3000.0 | equal |
| app_chuk_conf.use_smart_rev | 1 | 1 | equal |
| app_chuk_conf.smart_rev_max_duty | 0.07000000029802322 | 0.07000000029802322 | equal |
| app_chuk_conf.smart_rev_ramp_time | 3.0 | 3.0 | equal |
| app_nrf_conf.speed | 1 (1 MBit/s) | 1 (1 MBit/s) | equal |
| app_nrf_conf.power | 3 (0 dBm) | 3 (0 dBm) | equal |
| app_nrf_conf.crc_type | 1 (1 Byte) | 1 (1 Byte) | equal |
| app_nrf_conf.retry_delay | 0 (250 µS) | 0 (250 µS) | equal |
| app_nrf_conf.retries | 3 | 3 | equal |
| app_nrf_conf.channel | 76 | 76 | equal |
| app_nrf_conf.address__0 | 198 | 198 | equal |
| app_nrf_conf.address__1 | 199 | 199 | equal |
| app_nrf_conf.address__2 | 0 | 0 | equal |
| app_nrf_conf.send_crc_ack | 1 | 1 | equal |
| app_balance_conf.pid_mode | 0 (BALANCE_PID_MODE_ANGLE) | 0 (BALANCE_PID_MODE_ANGLE) | equal |
| app_balance_conf.kp | 0.0 | 0.0 | equal |
| app_balance_conf.ki | 0.0 | 0.0 | equal |
| app_balance_conf.kd | 0.0 | 0.0 | equal |
| app_balance_conf.kp2 | 0.0 | 0.0 | equal |
| app_balance_conf.ki2 | 0.0 | 0.0 | equal |
| app_balance_conf.kd2 | 0.0 | 0.0 | equal |
| app_balance_conf.hertz | 1000 | 1000 | equal |
| app_balance_conf.loop_time_filter | 0 | 0 | equal |
| app_balance_conf.fault_pitch | 20.0 | 20.0 | equal |
| app_balance_conf.fault_roll | 45.0 | 45.0 | equal |
| app_balance_conf.fault_duty | 0.8999999761581421 | 0.8999999761581421 | equal |
| app_balance_conf.fault_adc1 | 0.0 | 0.0 | equal |
| app_balance_conf.fault_adc2 | 0.0 | 0.0 | equal |
| app_balance_conf.fault_delay_pitch | 0 | 0 | equal |
| app_balance_conf.fault_delay_roll | 0 | 0 | equal |
| app_balance_conf.fault_delay_duty | 0 | 0 | equal |
| app_balance_conf.fault_delay_switch_half | 0 | 0 | equal |
| app_balance_conf.fault_delay_switch_full | 0 | 0 | equal |
| app_balance_conf.fault_adc_half_erpm | 1000 | 1000 | equal |
| app_balance_conf.fault_is_dual_switch | 0 | 0 | equal |
| app_balance_conf.tiltback_duty_angle | 10.0 | 10.0 | equal |
| app_balance_conf.tiltback_duty_speed | 3.0 | 3.0 | equal |
| app_balance_conf.tiltback_duty | 0.75 | 0.75 | equal |
| app_balance_conf.tiltback_hv_angle | 10.0 | 10.0 | equal |
| app_balance_conf.tiltback_hv_speed | 3.0 | 3.0 | equal |
| app_balance_conf.tiltback_hv | 200.0 | 200.0 | equal |
| app_balance_conf.tiltback_lv_angle | 10.0 | 10.0 | equal |
| app_balance_conf.tiltback_lv_speed | 3.0 | 3.0 | equal |
| app_balance_conf.tiltback_lv | 0.0 | 0.0 | equal |
| app_balance_conf.tiltback_return_speed | 2.0 | 2.0 | equal |
| app_balance_conf.tiltback_constant | 0.0 | 0.0 | equal |
| app_balance_conf.tiltback_constant_erpm | 500 | 500 | equal |
| app_balance_conf.tiltback_variable | 0.0 | 0.0 | equal |
| app_balance_conf.tiltback_variable_max | 0.0 | 0.0 | equal |
| app_balance_conf.noseangling_speed | 3.0 | 3.0 | equal |
| app_balance_conf.startup_pitch_tolerance | 20.0 | 20.0 | equal |
| app_balance_conf.startup_roll_tolerance | 8.0 | 8.0 | equal |
| app_balance_conf.startup_speed | 30.0 | 30.0 | equal |
| app_balance_conf.deadzone | 0.0 | 0.0 | equal |
| app_balance_conf.multi_esc | 0 | 0 | equal |
| app_balance_conf.yaw_kp | 0.0 | 0.0 | equal |
| app_balance_conf.yaw_ki | 0.0 | 0.0 | equal |
| app_balance_conf.yaw_kd | 0.0 | 0.0 | equal |
| app_balance_conf.roll_steer_kp | 0.0 | 0.0 | equal |
| app_balance_conf.roll_steer_erpm_kp | 0.0 | 0.0 | equal |
| app_balance_conf.brake_current | 0.0 | 0.0 | equal |
| app_balance_conf.brake_timeout | 10 | 10 | equal |
| app_balance_conf.yaw_current_clamp | 0.0 | 0.0 | equal |
| app_balance_conf.ki_limit | 0.0 | 0.0 | equal |
| app_balance_conf.kd_pt1_lowpass_frequency | 0 | 0 | equal |
| app_balance_conf.kd_pt1_highpass_frequency | 0 | 0 | equal |
| app_balance_conf.booster_angle | 8.0 | 8.0 | equal |
| app_balance_conf.booster_ramp | 1.0 | 1.0 | equal |
| app_balance_conf.booster_current | 0.0 | 0.0 | equal |
| app_balance_conf.torquetilt_start_current | 10.0 | 10.0 | equal |
| app_balance_conf.torquetilt_angle_limit | 5.0 | 5.0 | equal |
| app_balance_conf.torquetilt_on_speed | 5.0 | 5.0 | equal |
| app_balance_conf.torquetilt_off_speed | 3.0 | 3.0 | equal |
| app_balance_conf.torquetilt_strength | 0.0 | 0.0 | equal |
| app_balance_conf.torquetilt_filter | 2.0 | 2.0 | equal |
| app_balance_conf.turntilt_strength | 0.0 | 0.0 | equal |
| app_balance_conf.turntilt_angle_limit | 5.0 | 5.0 | equal |
| app_balance_conf.turntilt_start_angle | 1.0 | 1.0 | equal |
| app_balance_conf.turntilt_start_erpm | 100 | 100 | equal |
| app_balance_conf.turntilt_speed | 5.0 | 5.0 | equal |
| app_balance_conf.turntilt_erpm_boost | 20 | 20 | equal |
| app_balance_conf.turntilt_erpm_boost_end | 20000 | 20000 | equal |
| app_pas_conf.ctrl_type | 0 (Off) | 0 (Off) | equal |
| app_pas_conf.sensor_type | 0 (Quadrature) | 0 (Quadrature) | equal |
| app_pas_conf.current_scaling | 0.1 | 0.1 | equal |
| app_pas_conf.pedal_rpm_start | 10.0 | 10.0 | equal |
| app_pas_conf.pedal_rpm_end | 180.0 | 180.0 | equal |
| app_pas_conf.invert_pedal_direction | 0 | 0 | equal |
| app_pas_conf.magnets | 24 | 24 | equal |
| app_pas_conf.use_filter | 1 | 1 | equal |
| app_pas_conf.ramp_time_pos | 0.6 | 0.6 | equal |
| app_pas_conf.ramp_time_neg | 0.3 | 0.3 | equal |
| app_pas_conf.update_rate_hz | 500 | 500 | equal |
| imu_conf.type | 1 (IMU_TYPE_INTERNAL) | 1 (IMU_TYPE_INTERNAL) | equal |
| imu_conf.mode | 0 (AHRS_MODE_MADGWICK) | 0 (AHRS_MODE_MADGWICK) | equal |
| imu_conf.filter | 0 (IMU_FILTER_LOW) | 1 (IMU_FILTER_MEDIUM) | different |
| imu_conf.accel_lowpass_filter_x | 0.0 | 0.0 | equal |
| imu_conf.accel_lowpass_filter_y | 0.0 | 0.0 | equal |
| imu_conf.accel_lowpass_filter_z | 0.0 | 0.0 | equal |
| imu_conf.gyro_lowpass_filter | 0.0 | 0.0 | equal |
| imu_conf.sample_rate_hz | 200 | 200 | equal |
| imu_conf.use_magnetometer | 1 | 1 | equal |
| imu_conf.accel_confidence_decay | 1.0 | 1.0 | equal |
| imu_conf.mahony_kp | 0.30000001192092896 | 0.30000001192092896 | equal |
| imu_conf.mahony_ki | 0.0 | 0.0 | equal |
| imu_conf.madgwick_beta | 0.10000000149011612 | 0.10000000149011612 | equal |
| imu_conf.rot_roll | 0.0 | 0.0 | equal |
| imu_conf.rot_pitch | 0.0 | 0.0 | equal |
| imu_conf.rot_yaw | 0.0 | 0.0 | equal |
| imu_conf.accel_offsets__0 | 0.0 | 0.0 | equal |
| imu_conf.accel_offsets__1 | 0.0 | 0.0 | equal |
| imu_conf.accel_offsets__2 | 0.0 | 0.0 | equal |
| imu_conf.gyro_offsets__0 | 0.0 | 0.0 | equal |
| imu_conf.gyro_offsets__1 | 0.0 | 0.0 | equal |
| imu_conf.gyro_offsets__2 | 0.0 | 0.0 | equal |

Full identity and telemetry payload decodes are retained in `comparison.json`; telemetry is not included in the 376-setting equality count.
