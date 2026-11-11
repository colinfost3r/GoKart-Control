# Offline reverse-input checks

These cases run the new Lisp source against the interpreter **vendored in VESC 6.02**, with hardware APIs replaced by mocks. They do not connect to a controller. Keep generated cases/logs in a new temporary directory.

## Provenance and reproduction

- VESC source commit: `f7c2b34e1cff2234cae98be3abf0cd50e249558f`.
- Vendored path: [`lispBM/lispBM`](https://github.com/vedderb/bldc/tree/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispBM).
- Vendored Git tree: `5173bfae688fb89e45fba09011e33404a4ee7c29` (a normal tree, not a submodule).
- Build the unchanged source with `make -C /path/to/pinned/bldc/lispBM/lispBM/tests all64`.
- November 10 host: Apple Clang 21.0.0, arm64 Darwin; `-DLBM64 -D_PRELUDE`, upstream Makefile flags. No upstream source edits.

From the GoKart repository root, supplying your actual built binary:

```sh
python3 -B firmware/vesc-lisp/reverse-input/tests/run_mock_tests.py \
  --runner /path/to/pinned/bldc/lispBM/lispBM/tests/test_lisp_code_cps \
  --out /tmp/gokart-reverse-new-test-run
```

The wrapper generates cases, invokes each with `-h 2464`, saves logs and a hash manifest, and exits zero only if every case passes. **The upstream runner itself returns 1 on success**, so the wrapper checks that code together with `Test: OK!` and `Result: t`. The main project test script does not download or build this external interpreter.

## November 11 result and limits

**33/33 passed** after adjusting the provisional release guard to 0.12 below the native 0.15 deadband. The earlier 22/29-case sets also passed. New lifecycle cases cover allocation failure, stale PID reuse equal to the calling context, and actual joined worker stop before rollback. Additional cases cover measured rest values 0.09/0.106, refusal at 0.13, continuous chatter, moving-state hold and no stale queued direction. Cases cover disarmed load, startup preserving actual reverse state, short glitches, accepted stable transitions, pedal/RPM/fault interlocks, configuration changes, worker join, rollback disagreement and stalls within/around qualification windows. Both read-only monitors terminate after simulated 30 seconds and produce no detach/override calls.

The 2,464-cell cons heap matches the pinned firmware’s cell count. This is a **64-bit host** with different remaining memory pools, mocked time/hardware and a different scheduler. It does not prove MCU memory fit, real sampling deadlines, API presence on this custom build, USB behavior or electrical reliability. The exact compact source also passed all 33 cases. A strict 16KB sequential-loader host harness passed the 24-step plan and five corruption/order refusal cases. The subsequent kart-3 RAM load and first forward/reverse trial passed; permanent install, stop/rollback, coexistence, restart and fleet acceptance remain open. See the current trial evidence; host tests do not establish those outcomes.

## Guarded automatic startup trial

The separate `rx-filter-autostart.lisp` preserves the exact tested compact candidate and appends
one UUID/firmware/app-guarded startup call. Reproduce its 14 boot cases with:

```sh
python3 -B firmware/vesc-lisp/reverse-input/tests/run_autostart_tests.py \
  --runner /path/to/pinned/bldc/lispBM/lispBM/tests/test_lisp_code_cps \
  --out /tmp/gokart-autostart-new-test-run
```

The wrapper requires the exact reviewed source and package hashes, uses a new output directory,
and checks the same upstream exit-code-1 / `Test: OK!` / `Result: t` convention. Cases exercise
forward/reverse startup, pedal/RPM/fault/chatter refusal, requalification after release/rest,
wrong UUID/firmware/app/control type and genuine spawn-allocation failure without retry.
The package hash covers ASCII source, one NUL and a big-endian zero import count; it excludes
the separate flash size/CRC/flags header. No serial/network access occurs.

These mocked interpreter tests do not establish MCU boot ordering or reliability. Stock6.02
starts native ADC before Lisp and can suppress Lisp after a watchdog reset. Raw RX remains
in charge until the worker qualifies; maintain released pedal until active worker and correct
direction have been verified during supervised startup acceptance. A failed worker can leave
its previous override held. Installation, cold-boot acceptance and removal are separate steps.
