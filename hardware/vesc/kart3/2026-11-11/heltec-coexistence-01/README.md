# Kart 3 Heltec/Core2 coexistence — November 11, 2026

**Wheels-up local mode, forward and reverse checks passed with accessories online.**
The previously saved −5 A motor minimum stayed intact. The owner confirmed all three
Core2 modes verified, smooth forward, and smooth reverse; final state is pedal released,
wheels stopped, physical switch forward and temporary ECO selected. Final USB readback
shows zero ERPM/current, fault0, −5 A motor minimum/minscale1 and battery minimum−12 A.
No host motor commands, settings writes, resets, filter reloads or firmware updates were
sent in this session. The owner's Core2 mode selections used existing temporary controls.

## Evidence and measured scope

| Check | Result / evidence |
| --- | --- |
| Accessory reconnect | Correct kart3 BLE UUID, Core2 live/mode-ready, paired channels aligned. Full motor/app bytes matched the prior cold-boot capture before mode selection. Initial startup status was disconnected; later status verified established links. See `reconnect/`, `links-settled/`. |
| Core2 ECO/NORMAL/SPORT | Observed scales0.50/0.75/1.00 and ERPM limits±21661.4004 /±36102.3359 /±150000. All 95 full motor replies preserved−5/minscale1; only max-current scale and ERPM pair differed. All 94 application replies identical. Owner: all three verified. |
| Stationary recorder boundary | `mode-readback/` stopped at 48.69s when motion appeared. Owner confirmed deliberately trying the throttle after modes. Preserve `complete:false`; this is evidence of the observed mode changes, not a completed 90 s stationary test. No automatic retry/cleanup was sent. |
| First 120 s pedal capture | `pedal-trace/` is idle-only: 1,158 samples, all released/zero speed, counters flat. Owner clarified actual pedal use preceded that window. It verifies stationary coexistence, not pedal response. |
| Forward ECO | `pedal-trace-02/`: 1,158 pairs over ~120 s; 13 above-deadband intervals, all with positive rotation; peak 15,276ERPM. Some were coasting/short-rest reapplications. Zero sustained missed-start candidates and faults. Owner confirmed smooth forward. |
| Reverse ECO | `reverse-trace/`: 579 pairs over ~60 s; ERPM−19019..0 with no positive motion. Of 25 above-deadband intervals, 22 contain observed reverse rotation; three are single-sample brief crossings without >50ERPM in that sample. No sustained missed-start candidate/fault. Do not count 25 independent successful starts. Owner confirmed smooth reverse. |
| Settings during motion | Whole motor payload polled periodically; all 189 motor + 187 app fields identical before/after each pedal recording. Brake−5/minscale1 throughout; no unexpected profile change. |
| Wireless coexistence | During stationary/forward/reverse recordings, Core2 stayed live/mode-ready and both peers stayed aligned on channel 6. No new ESP-NOW failure/drop/invalid/hop counters, no VESC BLE CRC errors; LoRa traffic continued. GPS eventually acquired a fix. |
| Final state | `final/vesc/`, `final/boards/`, `final/verification.json`: exact settings match, stopped/fault-free, both accessories live; owner confirmed forward switch. |

## What this establishes

This is one kart's supervised ECO forward/reverse bench acceptance with BLE, ESP-NOW
and LoRa active, plus all three modes read back while stationary. It does not establish
road/load/endurance/range, eight-kart capacity, pit-command physical acceptance, abnormal
reset/fault behavior or a repaired reverse-switch harness. The filter's internal worker
and raw RX were intentionally not polled during Bluetooth coexistence; its startup was
verified separately, and direction here is supported by measured signed rotation plus
owner observations. No motor-temperature sensor is wired.

The earlier −5 A trial logged one 84.4 V bus sample after release. These ECO tests stayed
within 79.4–81.0 V forward and 77.9–81.0 V reverse; they do not close charged-pack/BMS
validation. See [prior trial](../brake-limit-trial-01/README.md).

The session's host scripts are archived in `host-tools/` with SHA256 sums. They use only
fixed getters and status queries; the original `capture.py` four-command allowlist was
unchanged. Pedal sampling is sequential ADC/GET_VALUES, about 10 Hz, not atomic. The
sustained-candidate rule requires ADC>.20, |ERPM|≤50 and |Iq|<8 A for≥.20s, resetting
on sample gaps>.35s. A lack of that trigger does not prove every brief hesitation absent.

Full project validation: **469 tests / seven suites / zero skipped, all passed**.
Independent read-only-path reviews and raw-payload replay also passed. Frozen failures,
idle captures and operator clarifications remain alongside the successful traces.

For karts 4/5, use the [replication guide](../../../../../docs/kart4-kart5-replication.md).
The full-scale post-cold-boot reference there is intentional: this session ends in the
owner-selected temporary ECO profile. Preserve each target's calibration and identities;
no kart 4/5 installation was performed and karts 1/2 remain Eamon's test units.
