# Independent temporary -5 A trial audit

Archive `audit_trial.py` and `final-results/summary.json`. The script reads existing files only and redecodes all 1,658 recorded ADC/telemetry payloads.

Final verified counts: 78 contiguous sampled pedal windows above 0.15; all contain rotation above 50 absolute ERPM. The actual archived trial recorder uses **abs(Iq) < 8 A**, yielding **17 instantaneous qualifying samples and zero sustained triggers**. Its source hash is verified against the trace manifest. An earlier scratch calculation incorrectly used the preceding 1 A diagnostic threshold; that six-sample figure is superseded and the interim summary files have been removed.

The native deadband is 0.15000000596046448. Comparing sample classifications with this exact value versus 0.15 produces zero disagreements. No independent-start/full-rest count is claimed.

The summary includes the one 84.4 V bus-voltage sample and three neighboring samples on each side, with elapsed ADC/telemetry timestamps, pedal, battery current, motor current, Iq, ERPM and fault. It records the peak as an observation, without claiming a causal mechanism or continuous regenerative braking.

Regenerate into a new directory:

```sh
python3 -B audit_trial.py --repo /path/to/GoKart-Control --out /new/audit-output
```
