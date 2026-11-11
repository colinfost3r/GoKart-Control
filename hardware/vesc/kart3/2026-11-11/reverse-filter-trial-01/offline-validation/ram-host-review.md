# Volatile RX-filter source load through fixed REPL expressions

Offline scratch validation only. No hardware or repository files were changed by this helper work.

The deployment plan is `compact-plan/plan.json`. Its 24 fixed expressions allocate a 3,733-byte RAM byte array, copy the exact 3,732-byte compact source in 192-byte pieces, acknowledge the cumulative byte count and CRC16 after every piece, verify length/CRC/trailing NUL, evaluate the one top-level expression, print explicit disarmed state, then remove the two loader bindings and collect garbage. It does not start the filter, detach inputs, override buttons, change settings, write flash, or send STREAM139. Each REPL138 payload is at most 397 bytes including command ID and NUL, below the firmware's 512-byte payload bound.

Human source: `../gokart-rx-filter-lifecycle-20261111/rx-filter-candidate.lisp`, 7,881 bytes, SHA256 `1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f`.

Deployment source: `../gokart-rx-repl-host-20261111/compact-candidate.lisp`, 3,732 bytes, SHA256 `d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc`, CRC16 883. Compaction removes semicolon line comments, asserts that remaining code contains no double quotes, collapses whitespace, and appends LF. All 33 behavior fixtures were regenerated using these exact compact source bytes and passed the pinned interpreter.

Plan SHA256: `c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805`.

## Runtime ownership and completion

An empty `:ctxs` report does not prove candidate globals or native overrides are absent. Require the owner's review of a fresh/known runtime with no previous copy and no conflicting overrides. Do not reload this candidate over an existing copy. The loader itself deliberately does not probe by overwriting arbitrary variables. Its only temporary globals are `gk-rx-load-buffer` and `gk-rx-load-pos`; these must also be absent at entry.

Every fixed step must finish before another is sent. Accept only the exact expected marker (all numeric CRC/count fields included); do not retry an uncertain or partial write. The final ready marker is `(gk-rx-load-ready nil nil -1 -1)`. REPL firmware internally waits up to 500 ms for a context before removing its result-callback association, so the usual `> t` may be absent after a slow parse. A host that also requires `> t` should abort without retrying; that does not prove definitions were absent. Never activate after ambiguous completion. `:ctxs` is a separate readonly ownership observation, not a native override readback.

The Heltec/BLE command stream must remain disconnected during USB loading: firmware's global reply function can redirect asynchronous Lisp output to another command interface. No packet storms are used to compete for ownership.

## Validation

`host_repl.c` is a scratch sequential-expression runner built against the exact vendored LispBM tree `5173bfae688fb89e45fba09011e33404a4ee7c29` from VESC commit `f7c2b34e1cff2234cae98be3abf0cd50e249558f`. It uses heap 2,464 cons cells, GC stack 160, print stack 128, and variable storage 64. It pauses/GCs between expressions to model normal REPL sequencing, registers native-style print/CRC and counted mock button-output functions, and never opens a port.

```
make -C /tmp/gokart-rx-repl-load-20261111
/tmp/gokart-rx-repl-load-20261111/host_repl /tmp/gokart-rx-repl-load-20261111/compact-plan/plan.repl 2048
```

The 2,048-word LBM64 pool is exactly 16,384 bytes. Compact-source load PASS: all expected CRC/ready/cleanup markers, zero mock override and detach calls, final 1,424 free memory words and 1,768 free cons cells. These are host values, not VESC measurements: pointers, registered extensions, scheduler and C structures differ. This is a constrained host check, not a hardware memory guarantee. The uncompressed 7,881-byte human source was intentionally not chosen for deployment; the older 7,532-byte source failed late reading under the strict 16KB host pool, before definitions or output calls.

Five negative cases passed with no ready marker and no output calls: wrong chunk offset, duplicate first chunk, source corruption, truncated cursor, and nonzero trailing NUL. `negative-tests/results.json` and corresponding logs record them. `compact-behavior/validation-results.json` records 33/33 behavior tests; those use the standard pinned host runner at `-h 2464` and larger non-cons memory pool, not the strict16KB sequential-loader harness.

CRC16 protects accidental corruption; it is not a cryptographic source identity. The host pins source and plan SHA256 independently and only sends the reviewed expressions. Native `bufcpy` may silently truncate but returns true; cumulative native CRC and final length/NUL checks therefore remain mandatory.

## Pinned source support

- `/tmp/gokart-602-lispif.c`: `ext_crc16` lines 3755–3777, registered as `crc16` at line 3851; native print has a 256-byte temporary buffer at line 442.
- `/tmp/gokart-lbm-602/src/extensions/array_extensions.c`: `bufcpy` line 1023; bounds may truncate, hence CRC checks.
- `/tmp/gokart-lbm-602/src/eval_cps.c`: `read`/`read-program` array conversion line 1738; `eval` line 1865.
- `/tmp/gokart-602-lispif-core.c`: REPL138 handling and firmware heap/memory/stack constants.

The actual serial host and supervised start/stop/rollback tools are owned and reviewed separately by the root agent. This directory is not a generic evaluator and contains no hardware sender.
