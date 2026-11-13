# Kart 3 short local reverse-input isolation — November 11, 2026

**Both input checks passed, and the operator confirmed smooth forward with the long
reverse-switch branch disconnected.** The removed branch is the leading suspect;
this is not a repaired kart or proof of one specific failed component.

| Observation | Result | Evidence |
| --- | --- | --- |
| Short RX-to-signal-GND jumper fitted, pedal released | RX=0; 13,428 samples; zero edges | [Closed monitor](closed-monitor/manifest.json) |
| Jumper removed, long switch branch still disconnected, pedal released | RX=1; 13,364 samples; zero edges | [Open monitor](open-monitor/manifest.json) |
| Wired-throttle forward check, RX left open and long branch disconnected | Operator: smooth forward. RX=1; 13,281 samples; zero edges; 303 telemetry replies | [Forward trace](isolated-forward-trace/manifest.json) |

Every printed monitor fault and captured telemetry fault was zero. The forward
trace recorded 0 to +23,961 ERPM and 0 to +29.77 A Iq. It returned to zero speed and
current while still being recorded. The full acceleration/coastdown was inside the
30-second RX monitor window. Electrical RPM is not calibrated road speed.

The requested operator throttle duration was at most one second. Actual samples
above 1 A Iq span about 7.507–12.835 seconds of host time; the operator was told to
release once data were observed. **Do not label this a verified one-second pulse.**
No host motor-output command was sent. Raw packets preserve actual timing:
[forward packets](isolated-forward-trace/packets.jsonl), [summary](summary.json).

## Setup and scope

The requested closed setup was a short RX-to-VESC-signal-GND jumper replacing the
long reverse-switch branch. The owner then explicitly confirmed the jumper removed
and long branch still disconnected for the open check. The pull-up and throttle
wiring were to remain intact; their physical placement and voltage margins were
not independently inspected. Throttle and reverse share VESC signal ground;
there is no requirement for isolated grounds. Never bridge 3.3 V directly to GND.

Fresh USB identity matched kart 3: 6.02/no_hw_limits, UUID
37004e000951343037353739. Prechecks captured all 376 settings, 81.8 V, zero ERPM/current
and fault zero. ADC app 2/control 3/buttons 0, servo off and pedal calibration matched
the expected setup. Exposed stored-code reads had no valid blob; fixed context
inspections reported no active contexts after initializing Lisp if needed. Heltec
remained off; no competing USB/BLE writer was used.

The open-input precheck and final motor/app payloads are **byte-identical: all 376
fields unchanged**. Final telemetry: 81.7 V, zero ERPM/current, fault zero.
[Before](raw-open-before/manifest.json), [after](raw-after-forward/manifest.json).
No configuration, direction override, flash, reset or calibration command was sent.
The staged software filter remains uninstalled.

## Meaning and next step

The earlier original-branch trace recorded 861 RX transitions and wrong-direction
stuttering. Removing that branch coincided with stable input at rest and through
operator-confirmed smooth forward. This strongly prioritizes the external switch
branch for investigation; it does not prove which switch contact, crimp, return
wire, pull-up arrangement or noise path is responsible. A single bench pass does not
establish long-term reliability or prove all eight karts share the same fault.

Power off was requested before any further wiring; the host cannot verify battery
isolation from USB enumeration. Next inspect/repair or separately substitute the
removed branch, retaining the original throttle/Hall calibration and tune. Use a
signal-ground return paired with RX, verify the mechanical contact pair with LED
terminal unused, and verify pull-up placement near the controller. Keep filter
activation deferred: a stable wrong level can pass software debounce. Repeat input
and supervised low-throttle acceptance after any repair before calling it complete.
