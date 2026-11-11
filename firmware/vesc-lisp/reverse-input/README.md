# Kart 3 reverse-input filter — persistent commissioning trial

The owner requested saving the successful filter after the RAM-only forward/reverse trial.
The [persistent installation](../../../hardware/vesc/kart3/2026-11-11/reverse-filter-persistence-01/README.md)
verified every stored byte, automatic normal startup with forward and reverse selected, a
subsequent switch change, and live workerPID 1507. The saved program is the exact tested compact
core plus one UUID/fw/app-guarded start. Final verified state: active/forward/rest/fault0,
Heltec off. No host motor command or tune/Hall/pedal configuration write was sent.

**The filter now survives normal power cycles.** Startup still has a raw-input interval before
Lisp qualifies direction; watchdog-reset boot skips Lisp. Keep the pedal released until the
filter's active state and selected direction are verified. No startup throttle interlock or
fleet/endurance acceptance is implied. Do not reload definitions over the active copy.
The physical input fault is not repaired: the earlier successful forward trace still counted
152 raw RX transitions. All configuration bytes matched during save; native current/voltage
measurement offsets recomputed across reboot under the already-enabled startup setting.

## Persistent source and installation record

[`rx-filter-autostart.lisp`](rx-filter-autostart.lisp) is3981bytes, SHA256
`30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700`.
The canonical3984-byte stored payload is ASCII source +NUL +BEuint16 zero imports, SHA256
`a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801`.
The prefix3732bytes exactly matches the RAM-tested core. Existing UUID/fw/app checks gate a
single start; refusal/spawn failure does not trigger retries or a default direction write.
Fourteen pinned-interpreter startup cases passed separately from the33 core cases.

VESC6.02 boots any valid stored Lisp on normal boot; header flags0 do not mean disabled. The
fixed installer writes only this script's storage, body first/header last, and verifies exact
payload plus all376 settings. Erase resets Lisp, and flash operations temporarily release
motor output, so installation requires stationary maintenance. No133 activation was sent;
the owner physically power-cycled the controller for acceptance. This is a session-specific
installer with pinned runtime config: do not rerun it over valid code or relax its motor hash
because native boot offsets changed. Persistent removal requires explicit joined stop/raw
rollback, then a separately reviewed erase of the verified filter-only stored program at rest.
Stopping the worker alone does not prevent the next normal boot from starting it again.

The RAM-only procedure retained below is for a separately reviewed empty/fresh runtime, not
this installed copy. See the persistent evidence for exact preflight, source hashes, ACKs,
readback, normal cold-boot results, and remaining acceptance work.

## Scope and hardware

Kart 3's identity is **6.02 / 75_300_R2 / no_hw_limits**, UUID
`37004e000951343037353739`. The owner identifies the physical controller as a **Flipsky 75100
Pro V2.0**. Preserve that installed build, voltage limits, phase filters, tune, Hall calibration
and pedal calibration. No firmware upgrade is needed for this test. Flipsky's
[75100 Pro V2.0 specification](https://flipsky.net/products/flipsky-75100-pro-v2-0-with-aluminum-pcb-based-on-vesc-for-electric-skateboard-electric-scooter-ebike-speed-controller)
lists 14–84 V; captured `l_max_vin=90 V` is a software setting, not a hardware rating.

Throttle stays on **ADC1**. The maintained reverse contact is **RX → VESC signal GND**, with
the owner-reported approximately 10 kΩ pull-up RX → 3.3 V and the LED terminal unused. Do not
infer physical connector orientation from wire colors. Throttle retains its signal ground;
no isolated ground is required. Remove all power and USB before changing wiring.

The pinned application is ADC=2, Current Reverse Button=3, buttons=0, servo output=0,
safe-start=1, native deadband=0.15. The host pins the entire 494-byte app payload SHA256
`2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d`.
The decoded pedal is measured before deadband; observed release around 0.081–0.106 does not
mean native motor demand is nonzero. No calibration change accommodates the filter.

## What the filter does

[`rx-filter-candidate.lisp`](rx-filter-candidate.lisp) defines functions but is disarmed on load.
It requires a stable raw RX level for 50 ms and decoded pedal <=0.12, |ERPM|<=50 and fault0 for
250 ms before accepting direction. A sampling gap >10 ms restarts qualification. Nominal
2 ms sampling is not a hard realtime guarantee. RX low means reverse; high means forward.
While moving or outside that zero-command region, it holds the previous applied direction.

It seeds the qualified reverse override before detaching native button reads. The VESC API
detaches both reverse and cruise buttons, so buttons=0/no cruise or inversion is mandatory.
ADC1 throttle remains native. There are no throttle, current, RPM, timeout-reset, configuration,
flash or firmware commands. Runtime guards check app/control type; full host app checks and
exclusive configuration ownership cover the remaining prerequisites.

A stable wrong electrical level can qualify at rest. A stopped, failed or paused worker can
leave the last native override active while the wired pedal continues working. This prototype
has not passed restart, failure-recovery, long-duration or fleet validation. The earlier
[local contact isolation](../../../hardware/vesc/kart3/2026-11-11/reverse-diagnostic-03-local-contact/README.md)
and [861-edge original-branch failure](../../../hardware/vesc/kart3/2026-11-11/reverse-diagnostic-02-held-state/README.md)
remain evidence that the external branch warrants repair/investigation.

## Observe the existing trial

Use the actual currently identified USB port and a new evidence directory. Keep the pedal
released, driven wheels lifted and operator at the physical cutoff for this bench work. Keep
Heltec/other BLE clients off during USB Lisp observations: stock 6.02 asynchronous prints
follow the most recently used command interface. Do not flood commands to compete for replies.

```sh
python3 -B tools/vesc/rx_filter_control.py status \
  --port /dev/cu.usbmodemACTUAL_PORT --out /absolute/path/to/new/status
```

Status reads identity, lifecycle/input state, contexts and full settings. It does not start,
stop, reload or command the motor. `run=true` alone is not proof of a live worker. A positive
PID listing proves presence at that observation; stock `:ctxs` omits its currently executing
context, so absence is inconclusive. The first start check failed for this reason; the failed
manifest is retained. Later positive PID listings and at-rest applied0→1→0 changes resolved
it **without repeating start**. There is no independent public getter for the native C detach
and override flags; lifecycle/applied values plus physical behavior are bounded evidence.

No throttle test is queued by these commands. Each manual pulse needs its own confirmed setup,
selected-direction verification and recording cue. Do not treat electrical/coasting timestamps
as exact pedal-pulse durations.

## Load only into a reviewed fresh runtime

This is for a later deliberate session, **not the current active copy**. First capture/decode
all runtime settings with `capture.py`/`decode.py`, preserve exposed stored Lisp with
`read_lisp.py`, inspect runtime ownership and establish that no previous candidate, native
input override, conflicting script or loader globals remain. An empty context list or
`no_valid_blob` alone does not prove that. Never reset/erase another script to make room.
Read-only capture's original allowlist remains IDs0/4/14/17.

The exact reviewed compact source is 3,732 bytes; its fixed 24-step plan fits every REPL packet
under 512 bytes. It assembles source in RAM, checks cumulative CRCs/length/NUL, evaluates once,
requires the explicit disarmed marker and removes its buffer. Each expected marker and `> t`
must arrive before advancing. No uncertain send is retried and no automatic recovery runs.
See [loader review and exact hashes](../../../docs/reverse-input/volatile-loader-review.md).
The reviewed STREAM139 path was rejected and is not a fallback.

```sh
# Offline validation only; never connects to hardware:
python3 -B tools/vesc/prepare_rx_filter.py
# Fixed memory/context inspection, not a load:
python3 -B tools/vesc/rx_filter_repl_load.py --inspect \
  --port /dev/cu.usbmodemACTUAL_PORT --out /absolute/path/to/new/inspection
```

Only after the actual ownership/no-previous-copy reviews and supervised setup, the loader
accepts `--ownership-reviewed --no-previous-copy-reviewed` instead of `--inspect`. Its
successful completion is a **disarmed definition load**, not activation or function readback.
Activation is separate: `rx_filter_control.py start --loaded-reviewed --setup-confirmed
--expected-rx 1 --port ... --out ...` for verified forward (raw1). The flags attest to completed
checks, not permission to skip them. The host rechecks stationary telemetry, target identity,
whole application and disarmed state, then sends one start. Any ambiguity means no driving
and explicit inspection, never repeat start/reload.

## Stop and rollback are different

`rx_filter_control.py stop --loaded-reviewed --port ... --out ...` calls the candidate's joined
stop. **It stops the filter worker and holds the last direction; it is not a motor stop.**
The candidate handles a failed spawn and a stale worker ID reused by the calling REPL context.

Rollback is a separate explicit supervised operation after the worker is joined:
`rx_filter_control.py rollback --loaded-reviewed --setup-confirmed --expected-rx 1
--port ... --out ...` for a held-forward state with raw RX=1. It requires pedal release, rest,
fault0 and raw direction agreeing with the held direction continuously for 250 ms, then
reattaches the physical button. Use raw0 only for a verified held-reverse state. A mismatch,
gap, unknown state or ambiguous reply must not cause automatic reset or retry.

Joined stop/rollback passed both pinned-interpreter tests and the stationary hardware
removal check immediately before this persistent installation. A power-off removes only a RAM-only trial. This installed program starts again on normal
boot; use the persistent removal procedure above to remove it. USB absence alone cannot prove
battery power is off.

## Validation and next step

The [test harness](tests/README.md) passes 33 cases in the interpreter vendored with pinned
VESC6.02, including spawn allocation failure, reused context IDs, actual worker join, chatter,
interlocks and explicit rollback. The same 33 cases pass with the exact compact source. A
strict16KB loader harness passed all24 steps with no mock output calls plus five negative cases.
Portable Python checks add 12 loader, seven plan and 21 lifecycle-controller tests. These are
offline tests with mocked hardware; native load and first F/R trial are separate recorded results.

Next evaluate the physical switch branch and repeat controlled acceptance, then validate longer-duration behavior, abnormal-reset/startup handling and Heltec
coexistence before wider deployment. Normal forward/reverse cold boots and stationary
stop/rollback passed; persistent removal and abnormal-reset behavior remain separate checks. Do not combine with the uninstalled `gokart_brake.lisp` experiment. Other karts
need their own identity/settings/electrical checks; this pinned trial is not a fleet installer.
