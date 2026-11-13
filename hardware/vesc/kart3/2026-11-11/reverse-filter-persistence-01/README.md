# Kart 3 persistent reverse filter — November 11, 2026

**Saved at the owner's explicit request; normal startup passed in both switch positions.**
The owner freshly confirmed driven wheels lifted, pedal released, Heltec off and cutoff within
reach. The earlier [RAM trial](../reverse-filter-trial-01/README.md) established owner-confirmed
forward and smooth reverse. The owner then asked to apply/save the filter for continued testing.

The old worker was joined while holding forward, then a guarded matching-RX rollback restored
raw input at rest. Both hardware operations completed, with all settings unchanged. Stored-code
reads exposed no valid blob, which is not a raw-flash backup. The reviewed installer sent one
Lisp-sector erase and 17 writes: 16 body chunks and the eight-byte header last. Every ACK matched;
all3984 stored payload bytes matched exactly, and all 376 settings matched during
installation. No133 activation, motor-output, configuration, firmware-image, Hall/pedal
calibration or offset-restoration command was sent. The owner performed both physical restarts.

Source 3,981 B SHA25630981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700;
canonical payload 3,984 B SHA256a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801.
Full stored image 3,992 B SHA256428657a58bc6d4a2a0e85df858e36fc7d34972007d7df436ed236632a9a19495.
The payload is the exact tested compact core plus one UUID/fw/app-guarded start call, NUL and
zero-import count. Header flags0 do not disable normal-boot Lisp execution in this firmware.

## Independent boot and settings review

Kart 3's filter survived both normal power cycles: with the switch held forward it reported `active=true`, applied direction `0`, raw RX `1`; with the switch held reverse it reported `active=true`, applied direction `1`, raw RX `0`. Both checks reported fault `0` and effectively zero ERPM. The final forward check again reported applied `0` / RX `1`. A separate final context inspection positively enumerated worker PID `1507` in the sleeping queue, with maximum reported stack usage `44`.

The stored 3,984-byte Lisp code blob read back after both cold boots is byte-identical to the installation readback: SHA-256 `a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801`. Command 130 returns this code blob, not the eight-byte flash header; this does not independently read back header flags.

All **376 decoded settings were byte-identical before and after installation**, and before and after each individual status session. Across the cold boots, all **187 app settings and all 183 motor settings other than the six current/phase-voltage measurement offsets remained unchanged**. This includes the motor tune, Hall calibration, and pedal calibration. The full motor payload is consequently **not byte-identical across boots**.

| Runtime measurement field | After installation | Forward cold boot | Reverse cold boot |
|---|---:|---:|---:|
| `foc_offsets_current__0` | 2047.0050048828125 | 2047.16796875 | 2047.18603515625 |
| `foc_offsets_current__1` | 2042.72802734375 | 2042.655029296875 | 2042.6300048828125 |
| `foc_offsets_current__2` | 2043.8360595703125 | 2043.81298828125 | 2043.68896484375 |
| `foc_offsets_voltage__0` | -0.0041 | -0.0041 | -0.0040 |
| `foc_offsets_voltage__1` | 0.0049 | 0.0048 | 0.0047 |
| `foc_offsets_voltage__2` | -0.0008 | -0.0006 | -0.0006 |

Five motor fields differed at the forward boot, and six differed at the reverse boot. `foc_offsets_cal_on_boot` was already `1` and remained `1` in every capture. These changes are consistent with normal native measurement-offset calibration: pinned VESC 6.02 initialization [calls `mcpwm_foc_dc_cal(false)` when that flag is enabled](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L463), and that routine [updates the three current and three phase-voltage offsets in the runtime configuration](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L2415). [GET_MCCONF serializes that runtime configuration](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/commands.c#L573), so fresh measurement offsets appear in readbacks even without a tune write. The calibration routine does not store a new motor configuration to flash. This is a source-backed interpretation, not an instrumented function-call trace.

**Do not restore the older offsets to force a matching hash.** They are native measurement calibration results, distinct from the Hall/pedal calibration the owner asked to preserve. The recorded TX frames contain no motor/app configuration-write commands and no command 133 activation/reset request. Persistence wrote the reviewed Lisp storage image; its startup was exercised by owner-operated normal power cycles.

Evidence links below are relative to this persistence session's directory if this note is incorporated there:

- [Installation manifest](install/manifest.json), [motor before](install/motor_before.bin), [motor after](install/motor_after.bin), [app before](install/app_before.bin), [app after](install/app_after.bin), [TX frame journal](install/tx-attempts.bin).
- [Forward cold-boot status](coldboot-forward/manifest.json), [reverse cold-boot status](coldboot-reverse/manifest.json), [reverse follow-up](coldboot-reverse-confirm/manifest.json), [final forward status](final-forward/manifest.json).
- [Positive final worker context](final-contexts/manifest.json) and [printed context records](final-contexts/packets.jsonl).
- [Stored-code capture after cold boots](stored-after-coldboots/manifest.json) and [exact code bytes](stored-after-coldboots/lisp_code.bin).

The accompanying `summary.json` records every decoded motor/app field, comparison counts and exact differences, input hashes, verified TX command counts/expressions, and pinned-source provenance. `summarize.py` regenerates it offline from the captured files. Its reviewed local source files were checked byte-for-byte against the firmware archive for commit `f7c2b34e1cff2234cae98be3abf0cd50e249558f`.

These are stationary boot acceptance checks. Earlier RAM-only trials established owner-observed forward/reverse operation; post-install driving tests are separate. `:ctxs` is only a queue snapshot and excludes the currently executing context, so intermediate listings that omitted PID 1507 do not establish that the worker had stopped. The final inspection positively found it. Native C button-detach state has no independent read API here; reported filter state, context evidence, and direction transitions are the available checks.

## Latest operator observation and limits

After installation the owner reported it seemed good, but sometimes retained the previous
direction with very slight throttle. They confirmed there was still slight throttle or coasting.
That matches the documented guard: direction cannot change until RX is stable50ms and the pedal
is within <=0.12, |ERPM|<=50 and fault0 for250ms. This is an explanation consistent with the source
and operator report, not a recorded trace of the specific event. No thresholds or tune were
changed. The owner was instructed: release the pedal, let the wheels stop completely, select
direction, wait about half a second, then gently apply throttle.

The later [observation snapshot](owner-low-throttle-observation/manifest.json) showed run/active
true, PID 1507 positively present, appliedforward0/raw RX=1, released-region pedal, near-zero ERPM
and fault0. This is the latest recorded state. The owner may continue supervised wheels-up checks;
post-install driving/endurance acceptance is not established by the stationary captures.

Native ADC reads raw RX before Lisp qualifies direction at startup. Watchdog-reset boot can skip
Lisp entirely. Keep the pedal released until active/correct-direction readiness is verified.
A stable wrong input at rest can still qualify; worker failure may hold direction while the wired
pedal remains native. The external input fault is not repaired. Normal boots passed; abnormal
resets, Heltec coexistence, persistent removal and fleet acceptance remain separate work.

Stopping/rolling back the worker is temporary when code is saved: normal boot will run it again.
Persistent removal requires exact stored-program/identity verification and a separate stationary
Lisp erase after joined stop/matching-direction raw rollback. No generic remover or automatic
fallback is installed. The [installer runbook](../../../../../docs/reverse-input/persistent-filter.md)
is session-specific and refuses any valid existing script, including this one. Native boot
measurement offsets also make its old exact motor hash unsuitable for blind reuse.

## Collaboration and reproducibility

The exact executed installer, dependencies, package and reviews are archived under `host-tools/`;
maintained portable tools are in `tools/vesc/`. The archived `summarize.py` is the exact historical
auditor with original scratch/source-archive paths; do not run it in place. Its full field table
and source provenance are retained in `summary.json`. Portable installer tests use committed
fixtures and synthetic rollback evidence; they never open hardware.

The two `status-owner-retest*` captures initially lived under the earlier RAM trial after its
checkpoint. They were moved here without changing their bytes to preserve that earlier trial's
reproducible fixed scope. The original RAM summary still reproduces exactly.

All **457 tests across seven project suites passed, zero skipped**, plus **33 core** and **14
startup** cases in the actual pinned host interpreter. The baseline decoder verified both
signatures/all 376 fields. [Validation](validation.json). These are separate from physical
operator observations and normal-boot checks.
