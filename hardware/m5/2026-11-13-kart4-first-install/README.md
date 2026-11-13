# Kart 4 boards: first install, pairing and read-only checkpoint — 2026-11-13

Kart 4's Heltec and Core2 were fitted but had never been flashed. They now run the November 13
game-rules candidate ([manifest](../../../docs/validation/m5-game-rules-2026-11-13.json)), are
paired with each other, and the Heltec is bound to kart 4's own VESC. The read-only checkpoint
and its soak passed; the Heltec was then moved to the write-capable build at the owner's
request, and ECO/NORMAL/SPORT were written from the Core2 and read back with the wheels up.
Details are in [observations.json](observations.json). The VESC side is in
[the kart 4 VESC record](../../vesc/kart4/2026-11-13/README.md).

| Item | Kart 4 |
| --- | --- |
| Heltec WiFi LoRa 32 V4 | MAC `f8:5b:1b:a2:15:50` |
| M5 Core2 | MAC `3c:8a:1f:d7:51:40` |
| VESC Bluetooth address | `ec:4b:65:41:40:51` |
| VESC UUID | `55004d000951343037353739` |
| Heltec application now | `kart-m5-espnow` `84e1da0ea79dbd576df5e4adc9bce04e8673aa305441943c29ea86d5bc7b4486` |
| Core2 application now | `m5-espnow` `0d904a89671272c08f794e848047e28341e6d232968723afdc3c017054e1a169` |
| ESP-NOW channel | 1 (no Wi-Fi configured on either board) |
| Heltec speed factor | 0.507 |

These values are **only for kart 4**. Never use them as defaults for another kart.

## What was done, in order

1. **Identified** both boards by USB descriptor and chip; neither is one of kart 3's.
2. **Backed up** the full 16 MB factory flash of each, privately. The Core2's first read at
   921600 baud failed without changing the board; 460800 baud completed.
3. **Stored the kart ID before the kart firmware ever ran.** With no stored ID the Heltec
   firmware uses ID 1 and starts LoRa telemetry at boot, and Eamon's kart 1 was live. The
   Heltec was erased, given the new no-radio helper `firmware/provision-kart-id` built with
   `-DKART_ID=4`, and reported `"before":0,"stored":4,"ok":true`.
4. **Heltec:** the frozen `kart-m5-espnow-readonly` application (`483fc642…1680`) written at
   `0x10000` without erasing. First status: kart 4, `writes:false`, no VESC pins.
5. **Core2:** erased, then bootloader, partition table, `boot_app0` and the frozen `m5-espnow`
   application written and verified.
6. **Paired** with `tools/m5/pair_espnow.py --kart-id 4`: fresh random keys for this pair, the
   private recovery file kept out of Git. Both sides linked on channel 1 with aligned channels,
   and the Core2 showed kart 4.
7. **VESC binding.** With kart 5's VESC off, `blescan` showed one unclaimed VESC. The UUID read
   over USB earlier was pinned first, then the address. The Heltec connected and read firmware
   6.02, `75_300_R2` and the same UUID; `id_ok` and `limits_ok` true, zero CRC errors. It read
   140 A and ±150000 ERPM over Bluetooth, the tune written over USB earlier that day.
8. **Read-only telemetry.** Heltec: VESC link up, 79.9 V (80.0 V over USB at the same time),
   fault 0. Core2: kart 4, live, VESC connected, mode controls unavailable. The owner confirmed
   the screen shows kart 4 at about 80 V.
9. **Read-only soak, 600 s:** no reset on either board, VESC link up in all 1197 samples,
   fault 0, zero CRC errors, writes disabled throughout, heap steady (Heltec low-water mark
   54.4 kB, Core2 147.8 kB). The owner pressed the screen 21 times trying to select a mode;
   every request was refused, as designed.
10. **Write-capable build.** The frozen `kart-m5-espnow` application was written at `0x10000`
    only; ID, pairing and pins were kept. Status: kart 4, `writes:true`, UUID equal to its pin,
    `id_ok`, `limits_ok`, baseline `read`, still linked. `speedcal 0.507` was stored before any
    mode could be selected, and the Core2 then reported `mode_ready:true`.
11. **Idle on that build:** 480 s and then 717 s untouched, no reset, VESC link up, fault 0,
    Heltec heap low-water mark 53.2 kB.
12. **Mode check, wheels up, modes held by the owner on the Core2.** Each was written and
    verified:

    | Mode | Scale | ERPM cap | Wheel peak | Peak motor current |
    | --- | ---: | ---: | ---: | ---: |
    | ECO | 0.50 | 15163 | 14834 | 44.6 A |
    | NORMAL | 0.75 | 25272 | 23891 | 41.9 A |
    | SPORT | 1.00 | 150000 (none) | 34446 | 75.1 A |

    Fault 0, no link drop, no reset; pack 75.3–80.0 V. The owner reported it felt right.
    **Final state: SPORT**, stopped. No reverse run was made in this check.

## Speed factor

Kart 4's VESC stores 14 poles, gear 2.769 and a **0.083 m** wheel diameter. Kart 2, where the
default 2.48 was measured, stores 14 / 2.769 / 0.406 m. The Heltec converts mph to ERPM with
the stored numbers, so 2.48 × 0.083 / 0.406 = **0.507** gives kart 4 the same caps as karts 2
and 3: 15163 ERPM in ECO and 25272 in NORMAL. With 2.48 the ECO cap would be about 74000 ERPM.
It rests on the owner's statement that the drivetrains match and is provisional until a GPS
check on the road.

## Not done, not verified

- Reverse under the caps on the write-capable build (reverse was run natively before the
  boards were installed; see the VESC record). The speed factor against GPS on the road.
- Wi-Fi and OTA settings on either board: nothing provisioned, hostnames unset.
- GPS, map and peers (indoors); whether the pit sees kart 4; pit commands; link-loss recovery.
- The reverse filter on kart 4's VESC; anything on the road.

## Rollback

Factory images of both boards, the pairing recovery file and all console and upload logs are
in the ignored private folders `firmware/build/bench-private/kart4-boards-20261113/` and
`firmware/build/bench-private/espnow-pair-20261113T175620Z/`. They contain keys and must stay
out of Git. To return the Heltec to read-only, write
`2026-11-13-game-rules/kart-m5-espnow-readonly.app.bin` at `0x10000`.
