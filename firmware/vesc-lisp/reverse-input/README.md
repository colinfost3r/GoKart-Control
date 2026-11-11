# Kart 3 reverse-input filter — volatile bench trial

The November 11 [first filter trial](../../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/README.md)
passed at-rest forward/reverse/forward selection, then operator-confirmed forward and smooth
reverse using the wired pedal. The original reverse-switch branch was connected. Forward had
152 raw RX transitions while captured motor rotation stayed forward; reverse had zero raw
transitions. Both returned to rest with no sampled fault. All 376 motor/app settings were
byte-identical to preflight. This demonstrates useful mitigation on one bench trial, not an
identified/repaired electrical fault or permanent fleet acceptance.

**Last recorded state:** filter active in RAM, PID 1244, forward applied=0/raw RX=1,
released-region pedal, near-zero ERPM and fault0. Heltec was off. No stop, rollback or power-off
has been recorded. **Do not reload an active copy.** No flash/autostart install was made;
a whole VESC restart removes this trial and restores the original raw reverse input.

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
--port ... --out ...` for a held-forward state with rawRX1. It requires pedal release, rest,
fault0 and raw direction agreeing with the held direction continuously for 250 ms, then
reattaches the physical button. Use raw0 only for a verified held-reverse state. A mismatch,
gap, unknown state or ambiguous reply must not cause automatic reset or retry.

Joined stop/rollback passed pinned-interpreter tests but **have not been exercised on this
controller**. A deliberate later power-off removes the volatile filter, returning to the
original raw-input behavior; USB absence alone cannot prove battery power is off.

## Validation and next step

The [test harness](tests/README.md) passes 33 cases in the interpreter vendored with pinned
VESC6.02, including spawn allocation failure, reused context IDs, actual worker join, chatter,
interlocks and explicit rollback. The same 33 cases pass with the exact compact source. A
strict16KB loader harness passed all24 steps with no mock output calls plus five negative cases.
Portable Python checks add 12 loader, seven plan and 21 lifecycle-controller tests. These are
offline tests with mocked hardware; native load and first F/R trial are separate recorded results.

Next evaluate the physical switch branch and repeat controlled acceptance, then explicitly
validate stop/rollback, boot/power loss and Heltec coexistence before deciding on persistent
installation. Do not combine with the uninstalled `gokart_brake.lisp` experiment. Other karts
need their own identity/settings/electrical checks; this pinned trial is not a fleet installer.
