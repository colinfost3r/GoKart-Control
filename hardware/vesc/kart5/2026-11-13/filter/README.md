# Kart 5 reverse-input filter installed — 2026-11-13

At the owner's decision the reverse-input filter was stored on kart 5's VESC with
`tools/vesc/fleet_rx_filter.py`, the same way as on kart 4 earlier that day
([kart 4's record](../../../kart4/2026-11-13/filter/README.md) explains the method). The script
is kart 3's tested filter core, byte for byte, with kart 5's controller UUID in its startup
guard. **One bus-voltage reading in the pedal check needs attention; see the end.**

| Item | Value |
| --- | --- |
| Controller | UUID `3d0020000951343037353739`, firmware 6.02, `75_300_R2`, `no_hw_limits` |
| Package | `../prepared-limits/` (`rx-filter-codeblob.bin`, 3984 bytes) |
| Script SHA-256 | `adb00951c36bfdd0b0d232c55b945a04c5403aa95586e8a86d34f51d8c50f806` |
| Startup guard | UUID literal `'(61 0 32 0 9 81 52 48 55 53 55 57)`, firmware `(6 2 0)`, ADC app / Current Reverse Button |
| Worker after power-up | context 1507 |

Kart 5's Heltec was held in its bootloader for all of this and restarted afterwards.

## What was done, in order

| Folder | Step | Result |
| --- | --- | --- |
| `observe-01-forward/` | Switch in forward | RX 1 in all 8 samples, released pedal 0.012–0.013 (limit 0.12), at rest, fault 0, no stored code, no contexts |
| `observe-02-reverse/` | Owner set reverse | RX 0 in all 8 samples; pedal 0.013–0.014; at rest, fault 0 |
| `install/` | Owner go-ahead, switch back in forward | Four preflight checks and a final one 0.31 s before the erase: forward, pedal 0.012, at rest, fault 0. One erase and 17 writes, each acknowledged; stored bytes read back equal to the script; all 376 settings unchanged; **not activated** |
| `status-01-forward/` | After the owner's power cycle, forward | Stored bytes intact. `run` and `active` true, worker 1507, applied forward (0) with RX 1 |
| `status-02-reverse/` | Owner set reverse at rest | Same worker, applied reverse (1) with RX 0 |
| `pedal-check/` | 130 s telemetry at 10 Hz | Eleven runs alternating reverse and forward, peaks −14458 and 34686 ERPM, fault 0, no direction change within any run. The owner reported it felt right |
| `status-03-final-rx1/` | Switch in forward | Armed, applied forward, same worker, stored bytes intact |

The limits listed in kart 4's record apply here unchanged: the filter starts at every normal
power-up, accepts a switch change only at rest with the pedal released, does not repair a
switch circuit, and **has no tested removal tool**.

## Bus voltage above 84 V in the fast run

In the one fast forward run of the pedal check the wheel reached 34686 ERPM at 82.7 A, the top
of this kart's wheels-up range and above 0.9 duty. Two consecutive 10 Hz samples at the end of
that run read **86.4 V and 85.5 V** on the bus. Every other sample in the trace is between 74.7
and 83.0 V, and the pack rested at 82.8–83.0 V before and after, so it was close to full.

- No fault was raised: `l_max_vin` is 90 V on karts 3, 4 and 5.
- 86.4 V is above a full pack (84 V nominal maximum) and above the 14–84 V that Flipsky lists
  for this controller. `l_max_vin` is a software setting, not a hardware rating.
- Battery current reached −11.6 A during the trace, close to the −12 A regeneration limit.
- The mechanism is **not established**. The run was in the field-weakening range, and a pack
  near full has little room to absorb regeneration; either or both may be involved.
- Kart 3 logged one 84.4 V sample after a pedal release on 2026-11-11. Kart 4's traces stayed
  at its resting voltage, but its pack was at 80 V, and its fast run was sampled at 2 Hz by the
  Heltec rather than at 10 Hz.
- ECO and NORMAL cap the wheel at 15163 and 25272 ERPM, well below this region. It took an
  uncapped full-pedal run.

Nothing was changed in response. The tune is the same on all three karts, so this is a tune
question for the owner and Eamon (field-weakening current, regeneration and over-voltage
settings, charge level), not a kart 5 fault. Until it is understood, avoid uncapped full-pedal
runs on a freshly charged pack.
