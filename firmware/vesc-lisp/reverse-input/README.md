# Kart 3 reverse-input check — staged for the next hardware session

**Latest isolation result:** [session 03](../../../hardware/vesc/kart3/2026-11-11/reverse-diagnostic-03-local-contact/README.md) passed both local input states
(closed 13,428 samples, open 13,364; zero transitions). With the long reverse-switch branch
still disconnected, the operator confirmed smooth forward and RX remained high for 13,281
samples with zero transitions. All 376 settings matched before/after. The removed branch is
the leading suspect, not a proven specific component. The earlier isolation instructions below
are retained for reproduction; the next step is branch inspection/repair/substitution followed
by repeat acceptance. Filter remains uninstalled; no further motor test is queued.

**November 11 latest:** held-state reads eventually showed RX=0 in reverse and RX=1 in forward,
and one reverse attempt worked. The next forward trace recorded **861 RX transitions in 30
seconds** with inconsistent direction. [Evidence](../../../hardware/vesc/kart3/2026-11-11/reverse-diagnostic-02-held-state/README.md).
The owner powered the VESC off. **Isolate the long switch harness before activating any filter.**
The filter is still unloaded/disabled; no tune, calibration or input override was changed.

With power and USB removed, replace only the long reverse-switch branch with a short known-good
local contact from confirmed RX to VESC signal GND. Keep the throttle and its signal ground
connected. Verify the pull-up is between RX and the controller's 3.3 V on the controller side.
Do not infer pin orientation from wire colors. Reconnect USB/power only for the supervised
pedal-released input check below; no motor test is queued. A stable local input followed by
failure with the original harness helps isolate the external wiring. A software filter can
still accept a wrong level held long enough and cannot establish a wiring repair.

## Existing firmware and battery

Kart 3's November 10 [identity](../../../hardware/vesc/kart3/2026-11-10/usb-before-tune/decoded/identity.json) reports **6.02 / 75_300_R2 / no_hw_limits**, UUID `37004e000951343037353739`. Its [runtime snapshot](../../../hardware/vesc/kart3/2026-11-10/usb-before-tune/README.md) recorded 82.1 V and fault 0. The captured `l_max_vin=90 V` is a software setting, not a 90 V hardware rating. Flipsky rates the confirmed 75100 Pro V2.0 at [14–84 V](https://flipsky.net/products/flipsky-75100-pro-v2-0-with-aluminum-pcb-based-on-vesc-for-electric-skateboard-electric-scooter-ebike-speed-controller).

The owner's concern about a 72 V limit is grounded in [Flipsky's firmware guidance](https://flipsky.net/blogs/vesc-tool/tips-of-75-serise-esc): build variants/settings matter. **Do not update or replace firmware for this test.** Preserve the installed build, voltage limits, phase-filter setting, tune, Hall calibration and pedal calibration. Other karts need their own identity/configuration check; this is not a fleet-wide firmware prescription.

## Diagnostic setup

1. Leave throttle on **ADC1**. For the latest isolation check, use the short local contact on **RX → signal GND** described above. Keep a verified approximately 10 kΩ pull-up from RX to the VESC's **3.3 V**. The switch LED terminal stays disconnected and insulated. Do not move to PPM for this RX-specific diagnostic.
2. Connect the VESC USB **data** port to the computer. No ATOM, new CAN wires, 12 V accessory supply or new Heltec connection is needed.
3. Before power/testing: driven wheels securely supported clear of the ground, pedal released, and operator beside the physical cutoff. Do not infer that an old readiness confirmation still applies.
4. A multimeter is useful for checking held high/low levels. Digital sampling below cannot establish electrical voltage margins or exclude glitches between samples.

## Backup before any Lisp evaluation

Identify the current USB port rather than copying an old device name. Close other serial clients. Capture/decode the complete runtime state with `tools/vesc/capture.py` and `decode.py` into a new dated evidence directory, confirming the UUID above, 6.02, ADC application (`app_to_use=2`), Current Reverse Button (`ctrl_type=3`), buttons bitfield **0**, and servo output OFF. Confirm pedal release/rest and inspect faults. The capture is runtime evidence, not a raw-flash image.

Use the separate read-only helper to preserve any valid stored Lisp payload:

```sh
python3 -B tools/vesc/read_lisp.py \
  --port /dev/cu.usbmodemACTUAL_PORT \
  --expected-uuid 37004e000951343037353739 \
  --out /absolute/path/to/new/lisp-backup
```

This sends only identity/read-code requests. Inspect its manifest before proceeding. The blob excludes the size/CRC/flags header; it does not establish run-on-boot state, current running contexts or an erased flash region. If existing code or ownership is uncertain, review it before evaluating anything. Never overwrite or stop another collaborator's script to get this test running. Save its source and run-on-boot setting through VESC Tool as appropriate.

## First test: read the switch only

**USB observation requirement:** temporarily remove the competing VESC Bluetooth client before a supervised capture. In stock 6.02, asynchronous Lisp output follows the most recent command interface; Heltec polling diverted or lost USB visibility in the first attempt. The owner powered off Heltec, contexts were inspected after the incomplete pass, and a new observation then completed. Never automatically resend after missing output or reset the controller to clear an uncertain run.

The maintained [`rx_probe.py`](../../../tools/vesc/rx_probe.py) provides fixed `--inspect` (stats and `:ctxs`), `--snapshot` (one RX/TX/ADC/RPM/fault read), and fixed monitor modes. Run `--inspect` into a new evidence directory after the fresh identity/config/stored-code backup; review current ownership before using `--ownership-reviewed` for the monitor. No arbitrary expression or motor/control command is exposed. The source hash must match the reviewed monitor. Keep each capture in a new directory.

[`rx-monitor-compact.repl`](rx-monitor-compact.repl) is a single bounded expression intended for the LispBM **REPL**, after the checks above. Strip its trailing newline when framing it: the expression is 403 UTF-8 bytes; command byte + expression + NUL is **405 bytes**, within the pinned firmware’s 512-byte packet-payload limit. It reads the existing GPIO state and telemetry, reports approximately once per second, and ends by itself. It does not configure GPIO, detach inputs, override direction, command the motor or write configuration/flash. Evaluating a REPL expression may initialize the Lisp interpreter if it was not already running; it is not the same as an entirely passive USB read.

Do **not** use Upload Code, erase, Run on Boot, `:reset`, script restart, or stream-restart as a shortcut to this monitor. Use VESC Tool's console or a reviewed single REPL submission; preserve the output with the fresh capture.

Output is approximately once per second: `(elapsed_seconds raw_RX cumulative_edges sample_count decoded_ADC electrical_RPM fault)`, then `(done cumulative_edges sample_count)` at about 30 seconds. The nominal sampling interval is 2 ms; it is not a hard real-time guarantee. The separate [`rx-monitor-30s.lisp`](rx-monitor-30s.lisp) adds qualified-transition and maximum-gap reporting, but is too large for one REPL packet.

Keep the pedal released throughout. Observe roughly 10 seconds in forward, 10 seconds with reverse selected, then 10 seconds in forward. Stable forward should read RX high (1); stable reverse should read low (0). Transitions during the deliberate switch movement are expected. Unexpected transitions during a held position support further noise/contact investigation; low/high voltages still need checking. If RX remains low throughout a failed reverse request, do not assume debounce is the cure: revisit configuration, faults and the separately documented zero-braking-limit hypothesis.

## Second test: candidate only after reviewing the monitor

`rx-filter-candidate.lisp` defines a removable filter and remains disarmed on load. It uses the supported stock 6.02 button override API; physical ADC1/ADC2 processing stays with the native app. Both buttons are detached by that API, so cruise-disabled/buttons=0 is a mandatory preflight condition. No throttle override or motor-current/RPM command belongs in this module.

**Do not activate before the local wiring isolation check.** The revised offline candidate uses
an ADC release guard of 0.12, below the unchanged 0.15 native deadband. Released-pedal readings
were roughly 0.081–0.106; this threshold describes a zero-command region, not proof that a pedal
is physically untouched. No calibration or motor-braking setting changed.

The candidate requires RX stable for 50 ms and decoded pedal <=0.12, |electrical RPM| <=50,
and fault 0 continuously for 250 ms before accepting a change. A sampling gap above 10 ms resets
qualification. A faulty level persisting 50 ms while at rest can still be selected; this is a
supervised direction-interlock candidate, not a commissioned cure or a stop command.

The candidate and detailed monitor exceed the single-packet REPL limit. A future reviewed **volatile** `LISP_STREAM_CODE` loader with `restart=0` is needed; no commissioned loader is included here. The reviewed stock stream implementation can partially evaluate source and has a buffer-timeout underflow path; a host timeout cannot prove firmware recovery. [Loader review](../../../docs/reverse-input/volatile-loader-review.md). Do not paste the whole file into an unverified sender or use flash upload to bypass that limit. Stream acknowledgement alone would prove byte receipt, not successful evaluation. Loading the definitions must not overwrite an active copy or another script’s runtime environment.

After that loading/ownership review, manual entry points are:

```lisp
(gk-rx-filter-start t)     ; t asserts completed host preflight and supervised setup
(gk-rx-filter-stop)        ; wait for worker exit; hold last direction
(gk-rx-filter-rollback t)  ; explicit reattach only at rest with matching raw RX
```

Complete each call before the next. Rollback requires the worker joined, pedal released, motor stopped, no fault, and raw RX agreeing with the held direction for 250 ms; stale observations refuse rollback. Never change direction by resetting the interpreter.

Do not start the candidate merely because it parses. Review the file's preflight/start/stop/rollback entry points and fresh electrical observations first. Keep this initial trial volatile; no flash installation or run-on-boot setting is authorized by these instructions. Do not combine it with the separate `gokart_brake.lisp` experiment.

The override lives in native C state. A paused/failed Lisp worker can leave the last direction selected while the wired throttle still operates. Stopping a worker is therefore **not rollback**. Reattach the physical button only through the explicit stopped/pedal-released rollback procedure; wait for worker exit first. A whole VESC reset clears the override and returns to the configured physical input. Stock 6.02 also suppresses Lisp autostart after a watchdog reset. These behaviors require hardware acceptance before any permanent deployment.

## Offline validation

The read-only backup helper passed 15 focused tests. The fixed input helper now passes 24 cases, including the actual brace-wrapped float reply; the latest complete project check passed **395 tests across seven suites, zero skipped**. The staged Lisp scripts passed **29 mocked cases** using the actual interpreter vendored in the pinned 6.02 source, with 2,464 cons cells. Independent review covered sampling gaps, direction interlocks, startup, joined stop and explicit rollback. [Reproduce the Lisp checks](tests/README.md).

These are host tests. The 64-bit build’s other memory pools, real scheduling, firmware extensions and electrical behavior differ from the controller. The compact monitor's read APIs and completion have since been exercised on kart 3. Button override APIs, electrical voltage margins, filter behavior and permanent deployment remain unvalidated.

## Why the first test is not ATOM/CAN

A dedicated ATOM could filter the switch, but its GPIO output can release during reset. CAN would additionally need a transceiver and a VESC-side receiver: stock CAN has no direct reverse-button packet for this ADC setup. VESC-local filtering avoids those additional links for the first test. It remains a candidate, not proof that the fleet fault is electrical noise or that the kart is fixed.

API/lifecycle references are pinned to stock 6.02 commit `f7c2b34e1cff2234cae98be3abf0cd50e249558f`:
[button API](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif_vesc_extensions.c#L1146-L1202),
[ADC input handling](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c),
[Lisp lifecycle](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif.c),
[CAN handler](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/comm_can.c).
