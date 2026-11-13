# Kart 5 boards: first install, pairing and mode check — 2026-11-13

Kart 5's Heltec and Core2 were fitted but had never been flashed. They now run the same
application images as karts 3 and 4, the November 13 game-rules candidate
([manifest](../../../docs/validation/m5-game-rules-2026-11-13.json)), are paired with each
other, and the Heltec is bound to kart 5's own VESC. Modes were written from the Core2 and read
back with the wheels up. Details are in [observations.json](observations.json). The method is
the one recorded for [kart 4](../2026-11-13-kart4-first-install/README.md); the VESC side is in
[the kart 5 VESC record](../../vesc/kart5/2026-11-13/README.md).

| Item | Kart 5 |
| --- | --- |
| Heltec WiFi LoRa 32 V4 | MAC `a4:cb:8f:a0:20:34` |
| M5 Core2 | MAC `3c:8a:1f:d7:53:44` |
| VESC Bluetooth address | `dd:d4:b8:ff:58:f6` |
| VESC UUID | `3d0020000951343037353739` |
| Heltec application now | `kart-m5-espnow` `84e1da0ea79dbd576df5e4adc9bce04e8673aa305441943c29ea86d5bc7b4486` |
| Core2 application now | `m5-espnow` `0d904a89671272c08f794e848047e28341e6d232968723afdc3c017054e1a169` |
| ESP-NOW channel | 1 (no Wi-Fi configured on either board) |
| Heltec speed factor | 2.48 (the default) |

These values are **only for kart 5**. Never use them as defaults for another kart.

## What was done, in order

1. **Identified** both boards by USB descriptor and chip; neither belongs to kart 3 or kart 4.
   On the first two looks neither board appeared on USB; they did after the owner re-seated
   them.
2. **Backed up** the full 16 MB factory flash of each, privately.
3. **Stored kart ID 5 before the kart firmware ever ran:** Heltec erased, the no-radio helper
   `firmware/provision-kart-id` built with `-DKART_ID=5` reported `"before":0,"stored":5,"ok":true`.
4. **Heltec:** frozen `kart-m5-espnow-readonly` application written at `0x10000` without
   erasing. First status: kart 5, `writes:false`, no VESC pins.
5. **Core2:** erased, then bootloader, partition table, `boot_app0` and the frozen `m5-espnow`
   application written and verified.
6. **Paired** with `tools/m5/pair_espnow.py --kart-id 5`: fresh random keys, private recovery
   file kept out of Git. Linked on channel 1 with aligned channels; the Core2 showed kart 5.
7. **VESC binding.** With kart 4 switched off, `blescan` showed one unclaimed VESC. The UUID
   read over USB was pinned first, then the address. The Heltec connected and read firmware
   6.02, `75_300_R2` and the same UUID; `id_ok` and `limits_ok` true, zero CRC errors, and
   140 A / ±150000 ERPM, the tune written over USB earlier.
8. **Read-only telemetry:** VESC link up, 82.9 V (82.8–83.0 V over USB), fault 0; Core2 kart 5,
   live, VESC connected, mode controls unavailable. **No read-only soak was run on kart 5**: at
   the owner's instruction to keep moving, the write-capable build followed directly.
9. **Write-capable build:** frozen `kart-m5-espnow` application written at `0x10000` only.
   Status: kart 5, `writes:true`, UUID equal to its pin, `id_ok`, `limits_ok`, baseline `read`,
   still linked; the Core2 reported `mode_ready:true`.
10. **Mode check, wheels up, modes held by the owner on the Core2.** Each was written and
    verified:

    | Mode | Scale | ERPM cap | Wheel peak | Peak motor current |
    | --- | ---: | ---: | ---: | ---: |
    | ECO | 0.50 | 15163 | 14098 | 10.4 A |
    | NORMAL | 0.75 | 25272 | 22085 | 26.4 A |
    | SPORT | 1.00 | 150000 (none) | 40166 | 82.6 A |

    Fault 0, no link drop, no reset; pack 77.3–83.0 V. The owner reported it felt right.
11. **Reverse filter** installed on the VESC afterwards, with the Heltec held in its
    bootloader; see [the filter record](../../vesc/kart5/2026-11-13/filter/README.md).
12. **Soak, 600 s,** on the write-capable build after the Heltec was restarted: no reset on
    either board, VESC link up in all 1196 samples, fault 0, zero CRC errors, Heltec heap
    low-water mark 53.0 kB, Core2 heap steady at 147.8 kB with zero parse errors. The VESC had
    been power-cycled for the filter check, so the kart sat at its stored limits (adopted as
    SPORT) throughout. The Core2 dropped about 70 of roughly 3200 received lines, around 2%,
    against about 0.5% on kart 4 and 0.3% on kart 3; the link stayed up.

## Speed factor

Kart 5's VESC stores 14 poles, gear 2.769 and a 0.406 m wheel diameter, the numbers the default
2.48 was measured against on kart 2. It therefore keeps 2.48, which gives the same caps as the
other karts: 15163 ERPM in ECO and 25272 in NORMAL. This rests on the owner's statement that
the drivetrains match and is unverified until a GPS check on the road.

## Not done, not verified

- Wi-Fi and OTA settings on either board: nothing provisioned, hostnames unset.
- GPS, map and peers (indoors); whether the pit sees kart 5; pit commands; link-loss recovery.
- Reverse under the mode caps; the speed factor against GPS; anything on the road.
- Why kart 5's Core2 drops more lines than the other two.

## Rollback

Factory images of both boards, the pairing recovery file and all console and upload logs are
in the ignored private folders `firmware/build/bench-private/kart5-boards-20261113/` and
`firmware/build/bench-private/espnow-pair-20261113T190736Z/`. They contain keys and must stay
out of Git.
