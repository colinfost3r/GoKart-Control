# Volatile RX-filter loader: reviewed and tested on kart 3

On November 11, 2026, the fixed **REPL-to-RAM loader completed all 24 steps** on kart 3's existing VESC 6.02. It verified the compact source, evaluated definitions, reported a disarmed state, and removed its temporary source buffer. The later supervised forward and reverse tests were separate operations using the driver's wired throttle. This is a **volatile bench trial**, with no flash write or persistent/autostart installation.

The [load manifest](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/load/manifest.json) preserves every completion marker, identity checks and before/after memory reports. Its [wire journal](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/load/wire.jsonl) and raw transmit/receive files preserve the actual session. The [current reverse-input guide](../../firmware/vesc-lisp/reverse-input/README.md) governs the next hardware session.

## Exact reviewed artifacts

Target: firmware **6.02**, hardware report **75_300_R2 / no_hw_limits**, UUID **37004e000951343037353739**. The physical kart uses the owner-confirmed Flipsky 75100 Pro V2.0. This loader is pinned to that controller, not a fleet provisioning tool.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| [Human candidate](../../firmware/vesc-lisp/reverse-input/rx-filter-candidate.lisp) | 7,881 | `1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f` |
| [Compact deployment source](../../firmware/vesc-lisp/reverse-input/rx-filter-candidate.compact.lisp) | 3,732 | `d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc` |
| [Fixed load plan](../../firmware/vesc-lisp/reverse-input/rx-filter-load-plan.json) | 13,010 | `c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805` |

Compaction removes semicolon line comments, requires no double-quoted strings in the remaining code, collapses whitespace and appends one LF. It does not rewrite Lisp expressions. The offline generator verifies the human and compact hashes, rebuilds every transmitted expression and marker, and compares them with the fixed plan. The plan retains its original scratch-source path as historical metadata so its deployed hash stays identical; no tool resolves that path or requires that directory on a collaborator's computer.

## Chosen transfer and completion checks

[`rx_filter_repl_load.py`](../../tools/vesc/rx_filter_repl_load.py) permits identity **0**, Lisp stats **134**, and fixed REPL **138** requests. The successful load used identity and REPL. There is no arbitrary-expression argument, filter activation, motor command, configuration write, flash operation, reset or STREAM request.

The 24 ordered steps are:

1. Allocate a 3,733-byte RAM array, clear it and initialize the copy cursor.
2. Copy 20 source pieces: 19 × 192 bytes and 84 final bytes. Each piece requires the expected cursor and prints its new offset and cumulative native `crc16` value.
3. Verify 3,732 source bytes, array length 3,733, CRC16 **883**, and a zero trailing byte.
4. Recheck those conditions, execute `(eval (read gk-rx-load-buffer))`, clear the source reference and print the four lifecycle globals.
5. Remove the two temporary loader bindings, collect garbage and print cleanup completion.

Every command-138 payload is at most **397 bytes**, including its command ID and terminating NUL; the pinned firmware ceiling is 512 bytes. Each step requires both its exact expected marker and the normal `> t` completion reply before the next step. The observed definition-load marker was:

```text
(gk-rx-load-ready nil nil -1 -1)
```

Those fields mean run=false, active=false, worker PID=-1 and applied direction=-1. Loading defines the candidate functions without calling them. Source validation and this marker do not independently read back every function body or the C-side detach state.

The loader checks target identity before and after, requires a complete context snapshot with no reported contexts, and requires separate manual reviews of runtime ownership and absence of an earlier candidate/override. **An empty context list does not prove that globals or native overrides are absent.** Reloading definitions over an old copy would reset its bookkeeping; it is prohibited.

Each frame gets one write. A partial/uncertain send, wrong or missing marker, unexpected result, pending/partial reply, timeout or receive limit aborts without retry, automatic reset, cleanup or activation. Limits are 240 seconds for the session, 256 KiB received, and five seconds for an individual step. A host timeout cannot establish what the controller completed. REPL itself may initialize Lisp and pause/GC/resume evaluation; it is not an entirely passive operation. Its firmware result callback normally waits only 500 ms, so an unusually slow expression can lose `> t`; the conservative loader then refuses to continue even if a marker appeared.

Keep other VESC command clients disconnected during this USB procedure. The pinned firmware routes asynchronous Lisp prints to its most recently used reply interface; Heltec BLE polling previously hid USB print output. Do not compete for that route with repeated sends.

## Hardware result and its limits

The successful load reported **1,755 free cons cells** and **2,968 free memory words** afterward, from the native pools of 2,464 cons cells and 4,096 32-bit words. No contexts remained at the post-load snapshot. This is actual MCU evidence for this source and session, not a capacity guarantee for future scripts.

After the separate start, the owner confirmed both forward and reverse operation with telemetry showing the corresponding direction. During the [forward trace](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/filtered-forward-trace/manifest.json), the raw RX monitor counted **152 transitions in 12,453 samples**, while forward operation remained successful; the following status check reported the live worker and forward applied. The [reverse trace](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/filtered-reverse-trace/manifest.json) recorded zero raw transitions in 12,458 samples. The monitor runs for about 30 seconds inside a 35-second telemetry capture; its input observations do not cover the entire capture interval.

The original [start check](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/start-forward/manifest.json) remains marked incomplete because arming was not verified at that check. Later read-only status checks established the live worker and accepted direction; this does not rewrite the earlier failure or justify automatically repeating start. At the [final recorded status](../../hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/status-final-forward/manifest.json), the worker was active in forward, the pedals were in the zero-command region, ERPM was effectively zero and fault was zero. Later power or lifecycle changes must be tracked separately.

These results support the filter for further supervised testing. They do not remove the electrical fault, prove long-term reliability or establish fleet readiness. A wrong RX level held long enough can still qualify at rest. The filter's stop operation joins its worker and **holds the last direction**; it is not a motor-stop command. Explicit guarded rollback is separate. The volatile definitions are lost on controller restart, returning to the original configured raw input; no persistence was installed in this trial.

## Why STREAM139 was rejected

The earlier review proposed STREAM command 139 with `restart=0`. **That route was not used.** Review of [pinned `lispif.c`](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif.c) found that a successful channel byte sets its timeout counter to zero; a subsequent full-buffer iteration decrements it and tests for equality with zero. That path can miss its intended exit. Smaller host chunks and a host timeout do not prove recovery of the firmware command thread.

STREAM also evaluates as bytes arrive, can initialize the interpreter despite `restart=0`, and has error paths with inconsistent reply lengths. A successful byte-transfer ACK is not successful evaluation. The previous scratch STREAM prototype and its mock tests remain historical review only; do not revive that route as a fallback after a REPL failure.

The chosen path instead uses the pinned runtime's ordinary `array-create`, `bufcpy`, `crc16`, `read` and `eval` primitives. `bufcpy` can silently truncate while returning true, which is why cumulative CRC and final length/NUL checks are mandatory. CRC16 detects accidental transfer corruption; independent host SHA-256 pins establish the exact reviewed source and plan.

## Reproduction and checks

From the repository root:

```sh
python3 -B tools/vesc/prepare_rx_filter.py
python3 -B tools/vesc/prepare_rx_filter.py --out /path/to/new/offline-review
python3 -B -m unittest discover -s tests -p 'test_vesc_rx_filter*.py' -v
```

The preparation command is offline only, accepts no arbitrary source and never updates pins. Its optional output directory must be new. The serial loader's `--inspect` mode observes fixed context/memory information; loading additionally requires `--ownership-reviewed` and `--no-previous-copy-reviewed`, an explicit port and a new evidence directory. These flags record actual reviews; they are not a remedy for an unknown runtime. Activation/stop/rollback belong to the separate guarded control helper and supervised procedure.

Validation completed before and during integration:

- **19 portable Python tests:** 12 loader tests plus seven preparation tests, independently rerun. They cover framing, identity/context refusal, uncertain/partial sends, exact completion, tampering, source reconstruction/CRC, refusal to overwrite output, and operation from another checkout and working directory.
- **33 pinned LispBM fixtures:** candidate behavior/lifecycle and two read-only monitor cases, rerun using the exact compact candidate with 2,464 cons cells. They include the 0.12 pedal guard below the unchanged 0.15 native deadband, timing gaps, chatter, joined stop/rollback, spawn failure and reused context IDs.
- A sequential loader harness passed with 2,464 cons cells, GC stack 160, print stack 128 and a strict 16 KiB 64-bit host allocation pool, with zero mock input overrides/detaches. Five negative cases rejected bad offsets, duplicate pieces, source corruption, a truncated cursor and a nonzero trailing byte. Host pointer sizes, extensions and scheduling differ from the MCU; the native load evidence above supplies the separate hardware result.

The interpreter comes from VESC commit `f7c2b34e1cff2234cae98be3abf0cd50e249558f`, vendored LispBM tree `5173bfae688fb89e45fba09011e33404a4ee7c29`. The [Lisp test notes](../../firmware/vesc-lisp/reverse-input/tests/README.md) document its unusual host runner convention: exit code 1 together with `Test: OK!` and `Result: t` denotes success. Full project suites remain required before pushing.
