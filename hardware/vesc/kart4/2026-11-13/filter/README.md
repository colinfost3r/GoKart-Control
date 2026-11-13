# Kart 4 reverse-input filter installed — 2026-11-13

At the owner's decision the reverse-input filter was stored on kart 4's VESC with the new
`tools/vesc/fleet_rx_filter.py`. The script is kart 3's tested filter core, byte for byte, with
only the controller UUID in its one-shot startup guard changed. It started by itself at the next
power-up, armed in the selected direction, followed the switch at rest, and the owner ran the
pedal both ways and reported it felt right.

| Item | Value |
| --- | --- |
| Controller | UUID `55004d000951343037353739`, firmware 6.02, `75_300_R2`, `no_hw_limits` |
| Package | `../prepared-limits/` (`rx-filter-codeblob.bin`, 3984 bytes) |
| Script SHA-256 | `177ae066b9be9c5f16dca5fc7fbc217a444be13bd18e25925d8fd7651e8dfbae` |
| Startup guard | UUID literal `'(85 0 77 0 9 81 52 48 55 53 55 57)`, firmware `(6 2 0)`, ADC app / Current Reverse Button |
| Worker after power-up | context 1507 |

Kart 3's staged in-memory trial was **not** repeated: its purpose was to prove the filter
logic, which is unchanged. What is specific to this kart was checked by observation instead.
During all of this kart 4's Heltec was held in its bootloader so it was not using the VESC
(6.02 sends Lisp prints to the interface that spoke last); it was restarted afterwards.

## What was done, in order

| Folder | Step | Result |
| --- | --- | --- |
| `observe-01/` | First observation | **Refused by the tool, nothing sent beyond reads.** Its motor check expected the full tune limits and saw the ECO cap the Heltec had written. The check was corrected to accept tighter runtime ERPM limits, never looser, and tested |
| `observe-02/` | Switch in forward | RX 1 in all 8 samples, released pedal 0.032–0.033 (limit 0.12), at rest, fault 0, no stored code, no contexts |
| `observe-03-reverse/` | Owner set reverse | RX 0 in all 8 samples; same pedal level; at rest, fault 0 |
| `install/` | Owner go-ahead, switch back in forward | Four preflight checks and a final one 0.31 s before the erase: forward, pedal 0.032, at rest, fault 0. One erase and 17 writes, each acknowledged; stored bytes read back equal to the script; all 376 settings unchanged; **not activated** |
| `status-01-forward/` | After the owner's power cycle, forward | Stored bytes intact. `run` and `active` true, worker 1507, applied forward (0) with RX 1 |
| `status-02-reverse/` | Owner set reverse at rest | Same worker, applied reverse (1) with RX 0 |
| `pedal-check/` | 51 s telemetry at 10 Hz | Three reverse runs (peak −20132 ERPM) and three forward runs (peak 15563 ERPM), alternating, fault 0, pack 76.8–79.8 V, no direction change within any run. The owner reported it felt right |
| `status-03-…`, `status-04-…` | Two checks while the owner was still moving the switch | **Refused: the stated switch position did not match.** Each recorded the state it saw: armed, applied direction equal to the switch |
| `status-05-forward-final/` | Switch in forward | Armed, applied forward, same worker, stored bytes intact |

The switch convention on kart 4 is the same as on kart 3: RX high is forward, RX low is
reverse, and with `buttons` 0 the controller's own reverse input reads it the same way.

## Limits

- The filter now starts at every normal power-up. There is a short raw-input interval before
  it qualifies a direction, and a watchdog reset skips Lisp: keep the pedal released until the
  kart is seen to respond in the selected direction.
- It accepts a switch change only at rest with the pedal released, after about a quarter of a
  second. A wrong electrical level held that long would be accepted; the filter does not repair
  a switch circuit.
- `:ctxs` reported no contexts while the worker was running. Stock 6.02 omits the executing
  context, so an empty list is inconclusive; the state variables and the kart's behaviour are
  the evidence.
- **There is no tested removal tool for kart 4.** Removing the script means stopping it and
  erasing stored Lisp from VESC Tool, at rest. `fleet_rx_filter.py` refuses to install over
  existing code, so it cannot update or reinstall this copy either.
- Not verified: behaviour under load or on the road, a watchdog or brown-out restart, long
  running, and whether kart 4's switch input is electrically noisy (no edge count was taken).

After this work the Heltec was restarted and reconnected: kart 4, identity and limits OK. The
VESC had been power-cycled, so it was at its stored limits (scale 1.00, 150000 ERPM), which the
Heltec adopts as SPORT until a mode is selected.
