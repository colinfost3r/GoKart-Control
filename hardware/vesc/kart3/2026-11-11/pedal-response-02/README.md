# Kart 3 pedal-response investigation — 2026-11-11

**Later status:** a subsequent −5 A trial passed and the owner requested a persistent
save. See [the later save record](../brake-limit-persistent-01/README.md) for current
state and outstanding verification. The account below describes this earlier
capture session; its raw files and failure manifests are unchanged.

Owner reports intermittent failure to accelerate, including without changing direction.
This is unresolved. The initial requested check found the filter active/forward, pedal
released, still rotating (~13,003 ERPM), fault 0. No instruction to press was given then.

After owner confirmed wheels lifted, pedal released, Heltec off and cutoff accessible,
a 40-second read-only trace captured 375 paired ADC/GET_VALUES samples and periodic
existing filter-status reads. Start/end stationary; all sampled filter states active,
forward applied, RX high; all sampled faults 0. Owner confirmed this attempt responded
normally. ERPM 0..29,703; Iq -5.98..49.77 A; decoded ADC1 .077380...518407.
No sample had decoded ADC1 >.15 with |ERPM|<50. This normal trace does not explain
the reported missed starts or prove they are caused by filtering/deadband.
Motor and app payloads matched byte-for-byte before/after. No motor-output, settings,
filter lifecycle, flash or reset commands were sent. Motor temperature is unavailable.

`trace-01/` preserves raw packets and decoded samples. `host-tools/` preserves the exact
executed recorder and imported helper versions; use the project's reviewed schema path
if replaying copied helpers offline. Recorder tests checked denied write commands,
framing and strict ADC response decoding. GET_VALUES resets only telemetry averaging
accumulators; fixed REPL status can briefly pause/GC the interpreter.

Owner requests a longer recording with multiple gentle pedal presses because the symptom
usually occurs after several attempts. A follow-on trace must be assessed separately.

## Three-minute follow-on recording

`trace-02-long/`: 18:11:06–18:14:07 UTC, 1,686 paired samples. All sampled
ERPM zero, faults zero, timeout/kill clear, filter run/active true and forward
applied/raw RX high. Decoded pedal remained below .15 throughout. Both full
configuration payloads matched before/after. Exact executed 180-second recorder
is archived beside the 40-second version. See `long-trace-summary.json`.

The owner has been asked whether they physically pressed the pedal during this
window; no answer was received before the recording ended. Do not label this
a successful repeated-throttle test or conclude a wiring failure without that
answer. No settings or filter thresholds were changed. Recording is stopped.

## Owner clarification and captured missed start

Owner clarified that the pedal had **not** been pressed in trace-02-long. Its
released-pedal readings are expected, not evidence of a wiring failure. The
earlier awaiting-answer summary is retained as the historical record.

At the owner's ready/start request, `trace-03-long/` began at 18:15:48 UTC.
Owner reported "missed right now". 78 consecutive samples over 8.257 seconds
(16.479–24.736 seconds into the trace) had decoded pedal .336–.970, zero ERPM,
and median Iq .05 A (range .01–.16 A). Applied direction remained forward.
The preceding release window was about two seconds, and later presses moved
normally. No sampled fault/timeout/kill flag appeared. One later raw RX low
snapshot during rotation was held out by the filter; it did not reverse the
applied direction. The pedal signal reaching the VESC is established; ordinary
deadband/direction qualification does not explain this captured event.

The operator was told to release. The host recorder was interrupted at about
55 seconds after preserving the event. Its manifest is intentionally still
`complete=false` with KeyboardInterrupt: it did not perform its normal trailing
reads. Independent `status-after-miss/` then verified active filter/PID1507,
forward/raw1, pedal released, stationary, fault0. Its app/motor bytes match the
trace's pre-capture bytes exactly. No motor, settings or lifecycle command was
sent.

`after-missed-start/` uses the archived fixed print-only diagnostic helper:
terminal events/foc_state/faults and the app-output-disabled getter. No faults
were registered since startup; app output was not disabled at this later
snapshot. The event ring shows native APP_ADC set_current and no brake-current
entries. Event entries coalesce and update both value and timestamp; their
printed amplitudes do not recover peak demand. FOC was read **after release**,
so it cannot prove the internal target during the missed start.

Leading hypothesis: motor-braking limit 0 produces an internal minimum limit
near -.05 A; the FOC modulation-sign clamp can then restrict the requested
opposite-sign current to about .05 A. This is a strong match to the recorded
plateau, **not yet a demonstrated root cause**. Pinned source:
[FOC limits](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L3065),
[minimum limit](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mc_interface.c#L2410).
Next useful diagnostic is an immediate fixed internal-state snapshot at onset,
without extending a held pedal attempt. No brake limit, deadband, filter guard,
Hall/pedal calibration or other tuning has been changed. The symptom remains
unresolved; do not count this as reliability acceptance.
