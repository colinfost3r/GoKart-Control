**Kart 3 reverse-input diagnostic — November 11, 2026**

The reverse trial succeeded, according to the operator. The forward trial recorded **861 sampled RX transitions**, including transitions before the first nonzero reported motor speed and another burst while reported speed was zero. This supports investigating the direction-input circuit. It does not identify which contact, wire, connector, pull-up or input-stage component is responsible.

The controller identified itself as firmware **6.02 / no_hw_limits**, target **75_300_R2**, UUID `37004e000951343037353739`. The owner identifies the physical controller as a Flipsky 75100 Pro V2.0. The Heltec was off for the successful USB captures. At the end of this captured session, the owner reported the VESC powered off as well.

**What the records show**

| Capture | Observed result | Evidence |
|---|---|---|
| Held reverse | RX=0, TX=1; released-pedal decoded value 0.089019; approximately zero ERPM, fault 0 | [Packets](reverse-01/packets.jsonl), [manifest](reverse-01/manifest.json) |
| Held forward | RX=1, TX=1; decoded pedal 0.089599; approximately zero ERPM, fault 0 | [Packets](forward-01/packets.jsonl), [manifest](forward-01/manifest.json) |
| Reverse trial, directory named `failure-trace-01` | Operator confirmed reverse worked. 303 telemetry replies; 13,381 RX samples; zero sampled RX transitions; all printed RX states 0 | [Packets](failure-trace-01/packets.jsonl), [manifest](failure-trace-01/manifest.json) |
| Forward trial | 303 telemetry replies; 13,208 RX samples; 861 sampled transitions, although each one-second printed RX state was 1 | [Packets](forward-trace-01/packets.jsonl), [manifest](forward-trace-01/manifest.json) |

`failure-trace-01` was named for the intended investigation before its outcome was known. Preserve that evidence path; it is not a record of a reproduced failed reverse start.

The reverse trace reached **−23,434 electrical RPM**, motor current up to **27.86 A**, and Iq down to **−25.46 A**. Battery voltage ranged from **78.6 to 81.9 V**. Its first nonzero telemetry speed appeared at host elapsed **29.087 s**. The RX monitor ended at **29.967 s**, while motion continued in telemetry until about **32.04 s**. Therefore, **RX was not monitored through the full reverse coastdown**.

The forward trace ranged from **−7,646 to +31,975 electrical RPM**, motor current from **−16.65 to +83.39 A**, and Iq from **−30.70 to +54.94 A**. Battery voltage ranged from **73.4 to 81.8 V**. These are electrical RPM and controller measurements, not calibrated kart speed.

Forward RX had already accumulated **79 transitions by host elapsed 1.019 s**; the first nonzero telemetry speed arrived at **1.399 s**. Later, the count increased from **477 to 861** between approximately **18.033 and 21.036 s**. All 28 telemetry samples in the surrounding 18.0–21.1 s interval reported zero ERPM. The burst cannot be attributed solely to the kart already rotating. No nonzero fault code, timeout flag or kill-switch flag appeared in either trace; intermittent events between samples remain possible.

**Configuration and scope**

After the owner-reported power cycle/reconnect, [runtime readback](raw-after-reconnect/manifest.json) showed SPORT-equivalent limits: current scale **1.0**, motor-current maximum **140 A**, and ERPM limits **±150,000**. Motor-braking current remained **0 A** and battery-current minimum **−12 A**. The app-configuration blob was byte-identical to the preceding diagnostic: ADC app 2, control type 3, buttons 0, servo output disabled, and native deadband approximately 0.15. Small current/voltage ADC-offset differences were also observed across the reconnect; these are listed in the [machine summary](summary.json), with no Hall or pedal detection command performed.

This session sent diagnostic reads and fixed input-reading Lisp expressions. **No motor-output command, tune/configuration write, flash write, calibration/detection command, or direction-filter activation was performed.** The owner operated the wired controls. REPL diagnostics can initialize or briefly pause/GC/resume the Lisp interpreter; they do not reset the controller. [Fixed terminal checks](terminal-before-trace/manifest.json) reported no logged faults since startup and zero Iq target at rest before the traces.

The [snapshot immediately before the reverse trace](reverse-before-trace/packets.jsonl) contains a valid raw response: `(pins 0 1 {0.082444} {0.000007} 0)`, followed by `> t`. Its [manifest](reverse-before-trace/manifest.json) remains incomplete because the portable host recognizer rejected LispBM's curly-brace float notation. Preserve that host-side error and the missing identity-after check; do not classify it as a VESC fault or rewrite it as a completed automated capture.

Meter descriptions were corrected during troubleshooting, and some reference points/units were uncertain. Treat them as operator reports, separate from the saved GPIO/telemetry evidence. Do not infer a verified resistance or connector voltage from those descriptions.

**Next step and evidence limits**

Keep the controller off while identifying the switch's mechanical contact pair and isolating the short local signal/ground path. Perform the no-throttle electrical isolation check before a software-filter trial. The filter remains deferred; a wrong input level lasting 50 ms can pass a debounce filter.

The monitor sampled nominally every 2 ms and printed once per second for 30 seconds; the telemetry capture lasted 35 seconds and requested 10 Hz. Actual telemetry timing and extrema are recalculated in [summary.json](summary.json). Individual pulse widths and continuously sampled electrical voltages were not recorded. Motor temperature is unavailable because the motor sensors are not wired.

The exact monitor file hash is recorded in the run manifests. Historical helper-source hashes were not captured at execution time; current helper copies may contain later parser or console changes. Treat their current hashes as inventory, not proof of the exact executed version. Logged transmitted frames provide the action-level record. [summarize_session.py](summarize_session.py) independently decodes the saved 74-byte telemetry payloads and reproduces the counts/extrema without opening a device.
