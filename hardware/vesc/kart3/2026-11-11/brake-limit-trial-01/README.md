# Kart 3 temporary −5 A motor-braking-limit trial

The owner authorized a RAM-only `l_current_min` trial from 0 to −5 A. The guarded
setter changed that field alone; all other 375 fields remained identical. No flash
store, motor command, app reconfiguration, filter reload or reset was sent.

- Applied at 18:34:48 UTC, full expected readback verified.
- Recorded 1,658 ADC/telemetry pairs for approximately 180 seconds. No stall trigger
  fired, and no sampled fault, timeout or kill flag appeared.
- Owner reported: “No—starts are responding consistently.”
- The trace ends with intentional reverse/coasting; the owner then confirmed forward,
  pedal released and stopped. The guarded restore completed at 18:39:58 UTC with
  exact original 0 A motor and unchanged app readback.
- The owner subsequently requested a permanent save. That is recorded separately in
  [persistent save](../brake-limit-persistent-01/README.md), not in this RAM trial.

The automatic trigger checked decoded pedal >0.20, |ERPM|≤50 and |Iq|<8 A for at
least 0.20 seconds. It was widened from the earlier 1 A threshold so a 5 A stationary
clamp would still be detectable. ADC and motor samples are sequential, not atomic;
no trigger or owner-reported miss in this bench run does not establish endurance.

`apply/`, `trace/`, `restore-zero/` retain raw responses and full readbacks;
`owner-observations.json` separates owner reports from measurements. `host-tools/`
contains the exact recorders/setter. `guard-vm-results/` contains 26 passing mocked
native guard cases in the pinned LispBM interpreter. The original four-command
capture allowlist was unchanged. The full existing project suite passed 457 tests
across seven suites, zero skipped, during this trial; fleet-helper changes are later.

The internal missed-start evidence is in [pedal-response-03](../pedal-response-03/README.md).
The −5 A phase-current allowance is distinct from the −12 A battery regenerative
current limit, which was unchanged. Motor temperature sensors are not wired.

## Independent sample audit

The [offline audit](independent-audit/summary.json) redecoded all raw payloads:
78 contiguous above-deadband pedal windows all contained rotation. These include
coasting reapplications and are not 78 independent starts from complete rest.
The actual <8 A trigger had 17 instantaneous qualifying samples but zero sustained
qualifications or diagnostic snapshots. No absence of shorter hesitation is claimed.

One bus-voltage sample reached **84.4 V** after pedal release, with no reported fault;
the remaining samples were ≤84 V (overall range72.2–84.4 V). Neighboring records and
current values are archived. This does not establish its cause or continuous regen.
Charged-pack voltage/BMS behavior remains an acceptance item before fleet use.
