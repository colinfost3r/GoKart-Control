# Kart 3 reverse diagnostic — November 11, 2026

**Measured result:** the completed 30-second observation recorded **13,415 RX samples, zero transitions, RX high throughout**. The owner confirms selecting reverse during that recording. No electrical voltage has yet been supplied. The result does not establish bounce or a tune fault; verify the physical RX connection, switch contact path and signal ground before enabling a filter.

## Controller and setup

- Owner freshly confirmed driven wheels lifted, pedal released, physical cutoff accessible.
- USB: `/dev/cu.usbmodem3041`, ChibiOS/RT virtual COM port, VID:PID `0483:5740`, serial `304`.
- UUID `37004e000951343037353739`, firmware **6.02 / 75_300_R2 / no_hw_limits**.
- Owner-confirmed physical model: **Flipsky 75100 Pro V2.0**. Firmware pin mapping does not independently verify loom labels.
- Existing wiring reported unchanged: throttle ADC1, maintained switch RX→VESC signal GND, approximately 10 kΩ RX→VESC 3.3 V; illumination unused.
- Native configuration: ADC (`app_to_use=2`), Current Reverse Button (`ctrl_type=3`), buttons bitfield 0, servo output 0; ADC calibration 0.69–2.67 V, deadband 0.15.
- Initial telemetry: 82.0 V, 0 ERPM, 0 motor/battery current, fault 0. Active current scale 0.75 and symmetric ERPM caps ≈36102 match the NORMAL limits. No profile was requested here.

## Captures and observations

| Evidence | Result |
| --- | --- |
| [`raw`](raw/manifest.json), [`decoded`](decoded/identity.json) | Identity, telemetry, 189 motor fields and 187 app fields; CRCs and both schemas verified. Runtime export, not a raw-flash backup. |
| [`lisp-backup`](lisp-backup/manifest.json) | READ_CODE 130 returned no valid nonempty blob. This does not prove blank flash or expose autostart/runtime state. |
| [`lisp-stats-preflight`](lisp-stats-preflight/manifest.json) | Identity 0 / stats 134 / identity 0; identities verified, stats silent. Stock 6.02 is silent without an evaluator; absence alone is not proof. |
| [`lisp-contexts-before`](lisp-contexts-before/manifest.json) | Fixed `:ctxs`: all three running/blocked/sleeping headings, no context entries. REPL initializes Lisp if needed; no stored code was started. |
| [`rx-monitor-01`](rx-monitor-01/manifest.json) | Fixed monitor sent once; 35-second USB capture got no monitor text or completion. Result unknown, not evidence of switch behavior. Owner reports starting forward and selecting reverse twice. |
| [`lisp-contexts-after-01`](lisp-contexts-after-01/manifest.json) | All context categories empty, so no monitor context remained. No reset/resend was used to clear it. |
| [`rx-monitor-02-heltec-off`](rx-monitor-02-heltec-off/manifest.json) | Owner powered off Heltec. New deliberate observation returned 29 periodic records and `(done 0 13415)`, followed by the same verified controller identity. |
| [`raw-after-monitor`](raw-after-monitor/manifest.json), [`decoded-after-monitor`](decoded-after-monitor/telemetry.json) | **All 376 settings exactly equal to this session's pre-monitor capture.** 81.9 V, 0 ERPM, 0 motor/battery current, fault 0; tachometer counts unchanged. |

The successful monitor reported RX=1 in every periodic record and zero cumulative edges across all 13,415 samples. Pedal decoded value ranged **0.089921–0.090987**; ERPM was effectively zero and all sampled faults were 0. The nominal 2 ms loop is not a guaranteed sampling deadline and cannot exclude glitches between samples. Motor temperature is unavailable because its sensor is disabled/not wired; unused thermal-channel values are not accepted sensor readings.

## Why the first pass lacked output

Pinned 6.02 [`commands.c`](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/commands.c) routes asynchronous Lisp prints through the most recent command interface. Heltec BLE polling can therefore divert output started over USB. Output returned after Heltec power was removed; this is consistent with that routing behavior. No BLE-side capture proves where the first pass's prints went, and its result remains unknown. Do not automatically resend after a missing completion marker: inspect contexts first and resolve the competing connection.

## Firmware mapping and pedal guard

Stock 6.02 maps Lisp `pin-rx` and this native ADC reverse mode to **PB11**. The permanent NRF/BLE UART RX is **PC11**, a separate input. GPIO read only reads the pad; the monitor never configures GPIO or detaches/overrides inputs. Lisp initialization restores ADC1/ADC2 analog modes, not RX. This supports checking the physical contact/connector/ground path next; it does not prove a damaged RX input.

`get-adc-decoded 0` returns the value **before** the native deadband. The observed ≈9% released-pedal reading is below the unchanged 15% deadband and corresponds to zero native throttle demand. The staged filter's provisional ≤1% guard is unsuitable for this observed rest level and would refuse activation. **Do not change calibration/tune to satisfy that script.** Keep the candidate uninstalled until the input issue and a measured release guard are resolved.

References: [GPIO mapping](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif_vesc_extensions.c#L4106-L4115), [ADC reverse and pre-deadband level](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c), [hardware definitions](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/hwconf/trampa/75_300/hw_75_300_core.h).

## Remaining physical check

Meter on DC volts, black on **VESC signal GND**, red on **RX**, with reverse held and pedal released. A working closed contact should pull RX near 0 V. A reading staying near 3.3 V directs investigation to the contact/connector/ground path. A reading near 0 V while firmware still reads high requires confirming the actual pin and hardware mapping before drawing conclusions. The owner has been asked for this measurement; **no voltage measurement has been recorded yet**.

No configuration, motor, ADC override/detach, flash, calibration, detection or reset command was sent. The filter was neither loaded nor activated. Heltec is off at the owner's last confirmation; VESC remains powered for the electrical check. Reconnecting accessories is separate from resolving the reverse input.

## Host validation

The fixed sender passed 18 focused offline cases and independent review. Its portable project copy changes only import-path resolution. The complete project test script passed **389 tests across seven suites, zero skipped**; the saved baseline decoded with both schema signatures and all 376 fields verified. These checks validate host software, not the unmeasured RX voltage or an uninstalled filter.
