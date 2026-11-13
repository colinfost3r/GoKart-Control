# Kart 3 internal current-target capture — November 11, 2026

**Later status:** a subsequent −5 A trial passed and the owner requested a persistent
save. See [the later save record](../brake-limit-persistent-01/README.md) for current
state and outstanding verification. The account below describes this earlier
capture session; its raw files and failure manifests are unchanged.

**Missed-start current-limiting interaction captured; no fix applied.** Owner requested
another supervised test to capture the VESC internal target. This follows the
[earlier pedal traces](../pedal-response-02/README.md).

## Result

During the owner-reported miss, native `APP_ADC` requested **45.776 A** while the
FOC print snapshot showed **iq_target +0.05 A** and **Mod q flt -0.01**. Pedal ADC
was .358289 immediately before and .407933 after the FOC read, with ERPM0 and
measured average Iq 0.05 A on both sides. The pair brackets the FOC snapshot by
53.7 ms. The fresh events read followed, while decoded pedal remained .457955
and ERPM0. This establishes that the native application accepted a substantive
current request; ordinary pedal deadband or the direction filter does not explain
the near-zero internal target.

Pinned firmware source applies an upper bound of `-lo_current_min` when filtered
q-axis modulation is nonpositive. The captured motor configuration has
`l_current_min=0` and `cc_min_current=0.05000000074505806`; native runtime logic
floors the braking limit to `-cc_min_current`. The resulting +.05A cap matches
the target during the failure. This is strong, direct evidence of the suspected
current-limit interaction. Printed values and event history are sequential and
rounded, not one cycle-atomic snapshot.

Sources: [FOC limiter](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L3065),
[runtime minimum](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mc_interface.c#L2410),
[accepted current event](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mc_interface.c#L650).

Application output was not disabled; sampled fault/timeout/kill flags were clear
and the controller reported no faults since startup. Applied direction remained
forward. One later raw-RX snapshot was low while forward stayed applied, so the
original switch harness chatter remains unresolved; filtering is still doing its
direction-hold job. This is not a claim that the raw switch circuit is repaired.

## Captures

- `triggered-01/`: preflight refused with pedal .96043 and zero ERPM. The owner
  was told to release. Keep the failed manifest: the recorder did not start.
- `already-held-snapshot/`: fixed read-only FOC/events/faults/output-disabled
  snapshot after that release; target0, so it did not capture the held failure.
- `triggered-02/`: start/rest checks passed. 362 paired samples and one automatic
  FOC snapshot, captured 28.328 s into the trace. It completed normally about
  ten seconds after the snapshot. Final active filter/PID1507, forward/raw1,
  released-region pedal, stationary, fault0. Motor/app payloads are byte-identical
  before and after.

## Recorder and verification

`host-tools/` preserves exact executed scratch tools and SHA256 values. The new
recorder imports the reviewed 180-second trace and fixed diagnostic helper.
Only identity0, telemetry4, motor14, app17, decodedADC32, fixed print-only
terminal20 and fixed status/output-disabled REPL138 payloads are allowed.
No motor-output, configuration, lifecycle, flash, calibration or reset command
was sent. GET_VALUES resets telemetry averaging accumulators; REPL status
can pause/GC the interpreter. The FOC snapshot itself uses terminal print.

Trigger: decodedADC>.20, |ERPM|<=50 and |Iq|<1A continuously >=.20s, with
>.35s sampling gaps resetting qualification. Maximum 180 s; at most 3 snapshots;
stop about 10 s after first snapshot. FOC is read before later diagnostic output,
then paired ADC/values immediately afterward. Expected terminal end fields and
a measured quiet tail are required. A missing/partial reply stops without retry.

Offline checks passed for command allowlists, CRC framing, ADC decoder, trigger
boundaries/gaps and expected response markers; the independent fixed diagnostic
helper passed 9 tests. A second agent reviewed the read-only paths and final
interpretation. Full project tests were not rerun for this capture-only session.

Historical invocation from repository root, with the original scratch dependencies
in the same directory:

```sh
PYTHONPATH=tools/vesc python3 -B /tmp/gokart-pedal-trace-20261111/triggered_target_trace.py --selftest
```

The archived helper retains its original absolute worktree reference. It is
evidence, not an unattended vehicle service or portable fleet diagnostic.

## Next step

Review a narrow temporary trial with a small nonzero motor-braking limit.
This changes allowed braking torque even though it does not itself request
regenerative braking, so review the battery/BMS/voltage and input behavior
before applying. Do not infer authorization from this read-only capture request.
No setting, Hall/pedal calibration, filter threshold or firmware was changed.
The missed-start issue is not fixed or accepted for normal driving.
