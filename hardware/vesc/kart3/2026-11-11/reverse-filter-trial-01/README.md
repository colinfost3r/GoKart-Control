# Kart 3 volatile reverse-input filter trial — 2026-11-11

**The supervised wheels-up trial produced working forward and smooth reverse according to the operator.** The forward capture recorded 152 raw RX changes while sampled rotation remained forward. The reverse capture recorded no raw RX changes. Both finished at zero sampled motor current and ERPM with fault code 0. This is evidence for this bench trial; it is not fleet, road, endurance or permanent-repair acceptance.

This review concerns `hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/`. It was performed offline without device access. [summary.json](summary.json) contains independently decoded packet statistics, configuration comparisons, timestamps and source-file hashes.

## What ran

The RAM loader completed all 24 fixed steps. It assembled and checked the compact definitions, evaluated them, then removed its temporary buffer; it did not activate the filter. Source hashes are:

- Reviewed human source: `1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f`.
- Deployed compact source: `d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc`.
- Fixed 24-step plan: `c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805`.

One explicit start created worker PID 1244 and applied forward (`applied=0`). The start helper correctly retained a **verification failure** because its first `:ctxs` snapshot did not list that PID. A subsequent forward-only status also missed it. No second start was issued. Later at-rest reverse and forward observations showed `applied=1/raw=0`, then `applied=0/raw=1`, with PID 1244 positively listed. Stock 6.02 context listing omits the currently executing context; initial absence was not proof of worker death. See [start-forward](start-forward/manifest.json), [status-reverse-01](status-reverse-01/manifest.json) and [status-forward-02](status-forward-02/manifest.json).

The filter changes only the native reverse-button override after its qualification checks. Wired throttle remains native. All traces used read-only telemetry plus the fixed bounded GPIO monitor; their recorded outgoing command IDs were 0, 4 and 138. Manual throttle came from the operator. No configuration, motor-current, reset, firmware, flash or STREAM139 command was sent by these trace tools.

## Recorded results

| Capture | Telemetry samples | Raw RX changes / reads | ERPM range | Signed Iq range | Operator report |
|---|---:|---:|---:|---:|---|
| [Forward](filtered-forward-trace/manifest.json) | 304 | 152 / 12,453 | 0 to 29,491 | −2.64 to +33.40 A | “forward worked” |
| [Reverse](filtered-reverse-trace/manifest.json) | 303 | 0 / 12,458 | −22,217 to +45 | −19.82 to 0 A | “Yes—smooth reverse” |

Each capture lasted about 35 host seconds, with a nominal 30-second raw GPIO monitor. Every recorded telemetry fault code and every one-second monitor fault sample was 0. The reverse +45 ERPM sample occurred near rest after the negative rotation; it does not establish a physical reversal. The forward negative-Iq sample likewise does not mean the wheels reversed: every captured forward ERPM value was nonnegative.

Forward raw changes accumulated between monitor times 12.030 and 15.038 seconds: 0→36→60→152. They were present during acceleration/coast despite all one-second raw-state snapshots being 1. These are changes between sampled GPIO reads, not 152 filtered direction changes. There were no `gk-rx-filter-applied` change messages during either trace; before/after status retained the intended direction. Those observations are consistent with the filter holding direction through chatter, but are not continuous independent readback of the native override.

**Requested pulse and measured duration are different quantities.** The instruction was a gentle manual pulse of at most one second. Recorded electrical activity and coasting extend longer, and these data cannot certify the exact pedal duration:

- Forward `|ERPM|>50` samples span 12.355–15.793 seconds, a 3.438-second first-to-last span including coast. Positive `Iq>1 A` appears at 12.355–13.573 and 13.895–14.793 seconds; one −2.64 A sample lies between these intervals.
- Reverse `|ERPM|>50` samples span 9.081–12.080 seconds, a 2.998-second first-to-last span including coast. `Iq<−1 A` appears at 9.081–10.190 and 10.399–11.190 seconds.

Times are host elapsed timestamps of received telemetry. These intervals are sampled threshold windows, not exact switch, pedal or motor-command boundaries. Do not label these captures “verified one-second pulses.”

## Configuration preservation and final recorded state

All 16 later motor payloads and 17 later application payloads were byte-identical to [preflight](preflight/raw/manifest.json), including the [final forward status](status-final-forward/manifest.json). Independent decoding confirmed all **189 motor + 187 application = 376 fields** unchanged. This preserves the existing tune and pedal/Hall calibration.

- Motor payload SHA256: `ab486bff0406bd7b84c0932160a4387e6862b7dee754ed38f4cc5dc7515a7b71`.
- Application payload SHA256: `2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d`.

The final recorded status has `run=true`, `active=true`, PID 1244 listed, `applied=0`, raw RX 1, decoded pedal 0.087836, essentially zero ERPM and fault 0. **The filter remained active in RAM at that capture.** No stop, rollback, persistent/autostart install or power-off is claimed here. A later shutdown or state change needs its own record.

The 152 forward raw changes show the original electrical/input instability still existed during this test. The software trial does not establish its specific wiring cause or repair it. Physical behavior statements above are operator observations; the packet captures establish sampled controller behavior only.

## Repository validation

All **435 tests across seven project suites passed, zero skipped**. The integrated source
passed all33 pinned-interpreter mock cases; the baseline decoder verified both signatures
and all376 fields. [Check manifest](offline-validation/project-checks.json). These checks
are offline and separate from the physical operator reports above. Portable tool changes
only changed paths; the exact used session tools/source are archived in
[host-tools](host-tools/README.md).

Reproduce the independent evidence statistics without a device, from the repository root:

```sh
python3 -B hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/host-tools/analyze.py \
  --out /absolute/path/to/new/offline-report
```

The output directory must be new. Original captures, including the initial failed start
verification, are never rewritten. Integrated replay matched the independent summary
exactly apart from its review timestamp.
