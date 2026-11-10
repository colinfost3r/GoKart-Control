# Independent kart 3 capture assessment

Validated 376 settings: 326 equal; 50 different (40 motor, 10 app).

Classification: 7 shared-tune candidates, 30 per-unit/hardware/identity differences, 13 protective or uncertain differences. All current values retained pending review; no write values approved.

- Kart 3 fresh capture identity matches expected UUID 37004e000951343037353739, 6.02, 75_300_R2; firmware name is no_hw_limits. This name does not prove current/voltage capability.
- Telemetry at capture: 82.1 V, ERPM 0, motor/battery current 0 A, fault 0, ESC filtered temperature 19.1 C. Raw motor temperature -95.4 C is invalid because sensor is unwired despite NTC configuration.
- Kart 3 supports/enables phase filters; baseline hardware does not. Preserve this hardware-specific difference.
- Hall tables, motor electrical values/current-loop tuning, ADC/phase offsets and pedal endpoints differ; do not clone these to match a tune.
- Kart 3 currently permits -50 A motor braking and -12 A battery regen versus baseline 0 A/-100 A. These are allowances, not proof of braking during this snapshot. Confirm disabled-regen intent before change.
- Historical field weakening is 95 A versus kart 3 15 A. Increasing it 6.33x is not justified solely by identical motor model, especially with no wired motor-temperature sensor.
- Baseline drivetrain metadata is known wrong by approximately 2.5x with Heltec speedcal 2.48 compensating. Pole counts differ 14/20; wheel diameter equality does not validate it. Do not copy or reset calibration without physical measurements.
- All ADC positive/negative ramp values already match. cc_ramp_step_max differs but is described for DC/BLDC, whereas both motors are FOC; do not claim it will improve FOC acceleration.

## shared_tune_candidate

| Field | Dated reference | Fresh kart 3 | Assessment |
| --- | ---: | ---: | --- |
| l_current_max | 140.0 | 120.0 | Shared torque/current-envelope candidate only. 120 to 140 A would increase configured motor current; verify controller/motor thermal and current headroom. No wired motor-temperature measurement exists. |
| l_in_current_max | 100.0 | 90.0 | Shared battery-current-envelope candidate only. 90 to 100 A would increase battery current; verify battery/BMS, wiring, connector and fuse limits independently of motor current. |
| l_min_erpm | -150000.0 | -100000.0 | Shared signed speed-envelope candidate only. -100000 to -150000 extends the negative-ERPM allowance as well; confirm reverse behavior and physically measured speed conversion before a change. |
| l_max_erpm | 150000.0 | 100000.0 | Shared speed-envelope candidate only. 100000 to 150000 extends electrical speed allowance; road-speed meaning is unresolved while pole/gearing calibration differs. |
| l_max_duty | 0.95 | 0.99 | Shared duty-envelope candidate only. 0.99 to 0.95 reduces the duty ceiling and also affects field-weakening onset; review together with ERPM and field-weakening limits. |
| foc_fw_current_max | 95.0 | 15.0 | Shared field-weakening candidate only, with especially large uncertainty: 15 to 95 A is a 6.33x increase. The old value is not proven safe for this motor/controller; no motor-temperature sensor is wired. Not an approved write value. |
| foc_fw_duty_start | 0.87 | 0.9 | Shared field-weakening onset candidate only. 0.90 to 0.87 starts at a lower fraction of maximum duty; review together with maximum duty/current and actual speed/thermal behavior. |

## per_unit_calibration_or_identity

| Field | Dated reference | Fresh kart 3 | Assessment |
| --- | ---: | ---: | --- |
| foc_current_kp | 0.08353837579488754 | 0.08179999887943268 | Retain local current-loop tuning tied to this motor/controller electrical parameters; identical motor model does not justify copying gains. |
| foc_current_ki | 18.026309967041016 | 13.640000343322754 | Retain local current-loop tuning tied to this motor/controller electrical parameters; identical motor model does not justify copying gains. |
| foc_motor_l | 8.353838347829878e-05 | 8.181000157492235e-05 | Retain this unit motor inductance value; do not replace measured/tuned motor electrical parameters with another unit export. |
| foc_motor_ld_lq_diff | 3.433670644881204e-05 | 3.10200011881534e-05 | Retain this unit d/q inductance difference; motor model equality is not a calibration measurement. |
| foc_motor_r | 0.018026310950517654 | 0.01360000018030405 | Retain this unit motor resistance value; temperature, winding and connection differences matter. |
| foc_motor_flux_linkage | 0.017599789425730705 | 0.017501000314950943 | Retain this unit flux-linkage calibration; do not clone another unit motor detection result. |
| foc_observer_gain | 3228383.0 | 3260000.0 | Retain local observer tuning associated with local motor electrical parameters. |
| foc_hall_table__1 | 15 | 150 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_hall_table__2 | 81 | 5 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_hall_table__3 | 48 | 175 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_hall_table__4 | 149 | 93 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_hall_table__5 | 183 | 127 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_hall_table__6 | 115 | 47 | Retain this unit Hall/phase relationship. The six Hall entries differ substantially; copying another motor/phase wiring calibration can produce incorrect commutation. |
| foc_temp_comp_base_temp | 0.0 | 25.0 | Retain the reference temperature associated with local motor resistance. Temperature compensation is disabled on both captures, so this difference is presently inactive. |
| foc_offsets_current__0 | 2039.4830322265625 | 2045.0849609375 | Retain this controller current-sensor ADC offset; it is per-unit calibration, not shared tune. |
| foc_offsets_current__1 | 2041.508056640625 | 2041.3380126953125 | Retain this controller current-sensor ADC offset; it is per-unit calibration, not shared tune. |
| foc_offsets_current__2 | 2048.761962890625 | 2041.3060302734375 | Retain this controller current-sensor ADC offset; it is per-unit calibration, not shared tune. |
| foc_offsets_voltage__0 | -0.007 | -0.0041 | Retain this controller phase-voltage offset; it is per-unit calibration, not shared tune. |
| foc_offsets_voltage__1 | 0.0042 | 0.0043 | Retain this controller phase-voltage offset; it is per-unit calibration, not shared tune. |
| foc_offsets_voltage__2 | 0.0027 | -0.0002 | Retain this controller phase-voltage offset; it is per-unit calibration, not shared tune. |
| foc_phase_filter_enable | 0 | 1 | Retain hardware-specific phase-filter setting: kart 3 identity reports has_phase_filters=1 and enabled=1; baseline reports support=0 and enabled=0. Different hardware capabilities explain this difference. |
| p_pid_offset | 0.0 | 27.0 | Retain the local position-controller angle offset; do not clone zero/alignment calibration from the other controller. |
| si_motor_poles | 14 | 20 | Physical drivetrain calibration remains unresolved: 20 versus historical 14. Same motor model does not prove which stored value is correct; measure/verify, do not copy the known-questionable baseline. |
| si_gear_ratio | 2.769230842590332 | 2.7690000534057617 | Physical drivetrain metadata remains unresolved: 2.7690000534 versus historical 2.7692308426. Verify actual tooth counts/ratio; do not copy merely to remove this numeric difference. |
| controller_id | 69 | 19 | Retain this controller CAN identity (19); baseline identity 69 belongs to another controller. Confirm network uniqueness separately. |
| app_adc_conf.voltage_start | 0.837 | 0.69 | Retain this kart pedal/ADC endpoint calibration. Copying another pedal voltage range can alter zero/full-scale behavior; physical pedal measurements are required before changing it. |
| app_adc_conf.voltage_end | 2.385 | 2.67 | Retain this kart pedal/ADC endpoint calibration. Copying another pedal voltage range can alter zero/full-scale behavior; physical pedal measurements are required before changing it. |
| app_adc_conf.voltage_center | 1.663 | 1.68 | Retain this kart pedal/ADC endpoint calibration. Copying another pedal voltage range can alter zero/full-scale behavior; physical pedal measurements are required before changing it. |
| app_adc_conf.voltage2_start | 1.501 | 0.33 | Retain this kart pedal/ADC endpoint calibration. Copying another pedal voltage range can alter zero/full-scale behavior; physical pedal measurements are required before changing it. |
| app_adc_conf.voltage2_end | 1.515 | 3.3 | Retain this kart pedal/ADC endpoint calibration. Copying another pedal voltage range can alter zero/full-scale behavior; physical pedal measurements are required before changing it. |

## protective_or_uncertain

| Field | Dated reference | Fresh kart 3 | Assessment |
| --- | ---: | ---: | --- |
| l_current_min | 0.0 | -50.0 | Braking-policy difference: kart 3 permits -50 A motor braking while the dated baseline is 0 A. Owner intended motor regen off; confirm the intended disabled-braking configuration. Allowance does not prove braking is occurring. |
| l_in_current_min | -100.0 | -12.0 | Protective battery charge-current limit: -12 to -100 A would permit much more battery regen. Do not copy without battery/BMS charge-current evidence and explicit braking-policy review. |
| l_abs_current_max | 240.0 | 220.0 | Absolute overcurrent fault threshold: 220 to 240 A relaxes a protection threshold, not just a drive-current setting. Do not raise it as a generic cure for cutoff. |
| l_min_vin | 12.0 | 60.0 | Undervoltage fault threshold: 60 to 12 V would greatly lower this fault boundary. Both battery-reduction thresholds separately remain 68/60 V. Preserve until controller/pack protection intent is reviewed. |
| foc_openloop_rpm | 700.0 | 800.0 | Startup/commutation threshold, not a simple top-speed limit. Review with local motor/load behavior; no need to copy to obtain the desired normal speed envelope. |
| foc_sl_erpm | 4000.0 | 2000.0 | Hall-to-sensorless transition threshold differs (2000 versus 4000 ERPM). Review with local commutation behavior and Hall calibration before changing. |
| s_pid_allow_braking | 1 | 0 | Speed-controller braking policy: copying baseline 1 would enable braking where kart 3 currently has 0. Preserve until braking/control mode intent is confirmed. |
| cc_ramp_step_max | 0.04 | 0.02 | The pinned schema describes this ramp parameter for DC/BLDC current control; both captured motors use FOC. Do not claim changing 0.02 to 0.04 will improve FOC acceleration. |
| m_motor_temp_sens_type | 8 | 0 | Known wiring mismatch: kart 3 configured NTC 10K but owner confirms no motor-temperature sensor; raw telemetry -95.4 C is invalid. Review sensor-disable correction rather than treating the configured thermal thresholds as real motor protection. |
| can_status_msgs_r1 | 15 | 0 | CAN reporting/topology difference: kart 3 sends none versus historical Status 1-4 mask. Confirm actual CAN topology/consumers before enabling messages; no automatic clone. |
| app_to_use | 5 | 2 | Input/transport topology differs (ADC versus ADC and UART). Preserve working wired inputs; verify whether UART application is needed by this physical controller/transport before enabling another app. |
| app_ppm_conf.ctrl_type | 3 | 0 | Unused-app behavior differs (Off versus Current No Reverse With Brake) while active app is ADC. Do not enable latent PPM motor/brake behavior just to match the baseline. |
| imu_conf.filter | 0 | 1 | Hardware/application-specific onboard accelerometer/gyro filter. Relevance to this kart is unverified; retain rather than copying an unrelated filter setting. |

The JSON lists every one of the 326 equal fields as equal_retain and flags material equal protections/metadata.
