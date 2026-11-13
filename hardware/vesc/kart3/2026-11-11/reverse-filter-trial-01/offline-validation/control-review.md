# Fixed RX-filter controller — offline draft

No hardware has been opened or commanded by this work. The script is separate
from the existing read-only diagnostics and from the RAM source loader. It does
not load/redefine Lisp, write configuration/flash, reset, or command the motor.
An explicit start changes the native reverse-input path through the reviewed
candidate. Hardware use requires the root operator's fresh setup confirmation.

Reviewed full candidate: 7,881 bytes, SHA-256
`1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f`.
Root's comment/whitespace-compacted deployment hash:
`d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc`.
`--loaded-reviewed` is an explicit human attestation to the separate successful
fixed-source load; this controller does not read back or authenticate function bodies.

## Native API review

Pinned upstream firmware commit: `f7c2b34e1cff2234cae98be3abf0cd50e249558f`.
Local source: `/tmp/gokart-602-lispif.c` lines 1146–1200 and
`/tmp/gokart-602-app_adc.c` lines 124–149 and 267–312.

- `(app-adc-override 2 desired)` writes only `rev_override`.
- `(app-adc-detach 2 1)` sets `buttons_detached`; ADC1 throttle stays native.
- Both reverse and cruise button values are replaced when buttons are detached.
  Inversion bits still apply afterward. Requiring `buttons=0` disables cruise and
  both inversions, matching candidate RX-low → reverse=1 logic.
- `(app-adc-detach 2 0)` restores raw native button input. It does not clear the
  old override value, which is ignored while attached.
- No reviewed public Lisp getter independently exposes `buttons_detached` or
  `rev_override`. A successful exact candidate call, lifecycle values, applied
  direction and positive worker context-PID presence are evidence of operation,
  not independent native flag readback.
- Decoded ADC level is recorded before native deadband. The candidate's ≤0.12
  guard stays below the unchanged 0.15 deadband; it is not a physical pedal sensor.

## Host preflight and actions

Every session pins UUID `37004e000951343037353739` and firmware 6.02, preserves
raw settings and identity reads, and checks the complete 494-byte application
payload against SHA-256
`2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d`.
The verified 187-field schema additionally checks app=2, ADC control=3, buttons=0,
servo output=0, safe start=1 and deadband=0.15000000596046448. Exact whole-payload
equality preserves every pedal calibration and other application setting.

Before start: require separately reviewed load, fresh supervised setup, explicit
expected raw RX level, disarmed globals, empty reported contexts, released-region
ADC, |ERPM|≤50 and fault=0. Read four stationary/fault-free telemetry samples,
then fresh fixed input/lifecycle data and the complete application again. Send
the one fixed start call only once. The candidate independently qualifies 250 ms
at rest and 50 ms stable RX before seeding the override and detaching buttons.

After a reported successful start: require run/active, expected applied direction,
the returned PID, and that exact PID positively listed in `:ctxs`. Absence is
**inconclusive**, because the firmware iterator can omit the currently executing
context. An inconclusive result means no driving and a later explicit read-only
status check; never auto-start again. A worker not yet armed can qualify later.

**Stop means stop filtering, join the worker, and hold its last direction. It is
not a motor stop.** The fixed candidate handles spawn failure and a stale worker
PID equal to the current REPL context. Stop does not restore raw RX. Rollback is
a separate supervised command, requiring the worker already joined, the pedal
released, rest/fault guards, and raw RX agreeing with the held direction. The
candidate qualifies that agreement for 250 ms before reattaching raw input.

Successful lifecycle result records are followed by full application, motor-byte
and identity checks. A missing/ambiguous command reply aborts without further
sends, retries or automatic cleanup; post-action settings cannot then be claimed
verified. Partial sends may have changed state. Preserve evidence and inspect
explicitly before deciding recovery.

Raw RX bytes, attempted TX frames, CRC-valid packets and manifests are recorded.
REPL evaluation pauses/GC/resumes Lisp and can create sampling gaps. Candidate
gap checks then restart qualification while holding the previous applied state.
The controller's 40-second host deadline cannot guarantee MCU interpreter recovery.

## Boundaries

The candidate's runtime guard checks app/control type only. Host checks cover
the other fields before/after actions; no other USB/BLE/configuration writer may
run during the trial. Keep the original intended switch branch connected for
the supervised trial and hold the switch steady during start/rollback. Long
stable wrong electrical levels can still be accepted; software debounce cannot
repair a broken or marginal circuit.

All **21 focused mock tests passed**. These include real application payload
decoding, actual LispBM brace-float syntax, single-send framing, fragmented CRC
response handling, full-application mismatch, four-sample start gates, live-PID
confirmation, stop/rollback separation and refusal/no-retry behavior. The parent
reviewer separately validated 33 candidate tests in the pinned interpreter.
Neither test set constitutes a physical reverse-input acceptance test.
