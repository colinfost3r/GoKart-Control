# Kart 3 Core2 updated over the air — 2026-11-13 evening

Kart 3's Core2 now runs the `m5-espnow` application of the race-screen candidate
([manifest](../../../docs/validation/m5-race-screen-2026-11-13.json)): built-in street lines and
the pit-race screen. **Only the Core2 was updated.** Kart 3's Heltec still runs the November 13
game-rules application, so the Core2 can show the race position and finish, but **not the grid
countdown or GO**, which need the newer Heltec. Details are in
[observations.json](observations.json).

| Board | Before | Now |
| --- | --- | --- |
| Core2 `m5-espnow` | `0d904a89671272c08f794e848047e28341e6d232968723afdc3c017054e1a169` (game rules) | `f0d74bdc86e316cc33603e3fcbb0a106f2303dcd748f4a421a90bbac3f38cdf6` |
| Heltec `kart-m5-espnow` | `84e1da0e…4486` (game rules, reports `kart-0.3.3`) | unchanged |

## What was done

The owner asked for the update over the air and opened the Core2's update window on its screen
twice. The upload used `tools/m5/ota_core2.py` with the private credentials file kept for this
Core2; the password was never typed or shown. No USB cable was connected at any point.

1. **Three attempts stopped at the tool's 120-second deadline.** After each, the Core2 was
   still advertising update mode on the network, which a restarted Core2 does not do, so the
   old application was still running and nothing had changed.
2. **Cause measured, not guessed:** during the third attempt the uploader had sent 572 kB after
   106 seconds, between 3 and 8 kB/s. At that rate the 1.4 MB image needs four to five
   minutes. The router answered the Mac in 5 ms; the Core2 in 10 to 460 ms with some loss. Why
   the link was that slow (distance, or sharing the channel with the paired Heltec) was not
   examined.
3. **The tool's deadline is now adjustable up to 480 seconds** (default still 120). The fourth
   attempt, with 480, was **acknowledged after 2 min 57 s**.
4. The Core2 then stopped answering on Wi-Fi, as it does after restarting into normal
   operation with updates off.
5. **The owner reported that the screen looks right.** He had been asked to check the map
   (street outlines, or the SHOP AREA overview without GPS), live battery volts on the dash and
   the mode buttons; which of them he looked at was not stated.

## Not verified

Everything the Core2's USB console would show. Without a cable there was no `status`, no
`ota status`, no check that the encrypted pair re-linked or that mode requests still work, and
no confirmation of the running image beyond the uploader's acknowledgement. **The owner's look
at the screen is the only check**; no race has been run with it.
Nothing was selected or written on the VESC by this update.

## The Core2 now boots from its second slot

An over-the-air update writes the slot that is not running and then switches to it. This
Core2 booted from `app0` (offset `0x10000`) before, so it now boots from **`app1` at
`0x650000`**, and `app0` still holds the game-rules application.

**A later USB update of this Core2 must not simply write `0x10000`:** that slot is no longer
the one that boots. Either read `otadata` (`0xe000`, 8 kB) first and write the slot in use, or
also write `boot_app0.bin` at `0xe000` to switch back to `app0`. Karts 4 and 5 have never been
updated over the air and still boot from `app0`.

## Rollback

The game-rules application is still in `app0` and the frozen image is in
`firmware/build/bench-candidates/2026-11-13-game-rules/`. Over USB: write `boot_app0.bin` at
`0xe000` to boot `app0` again. Over the air: upload that image the same way.
