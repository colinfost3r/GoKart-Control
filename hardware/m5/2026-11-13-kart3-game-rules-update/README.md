# Kart 3 game-rules applications installed — 2026-11-13

Both kart 3 accessories now run the November 13 game-rules candidate
([manifest](../../../docs/validation/m5-game-rules-2026-11-13.json)). This supersedes the installed
state recorded in [the November 12 update](../2026-11-12-kart3-player-update/README.md) without
changing that evidence. Details are in [observations.json](observations.json).

| Board | Before (2026-11-12 candidate, read back from flash) | Written |
| --- | --- | --- |
| Core2 `m5-espnow` | `894a1a34…d3ac` | `0d904a89671272c08f794e848047e28341e6d232968723afdc3c017054e1a169` |
| Heltec `kart-m5-espnow` | `d4366264…cab9` | `84e1da0ea79dbd576df5e4adc9bce04e8673aa305441943c29ea86d5bc7b4486` |

**Method.** The VESC was off for the backup and both uploads. Each board's partition table,
otadata, NVS and installed application were first read over USB; both applications matched the
November 12 candidate and both boards boot from `app0`. Only the application was then written
at `0x10000` with esptool 4.9.0, which verified the written data. Bootloader, partition table,
otadata and NVS were not written.

**Observed afterwards, VESC off.** The Heltec reports `kart-0.3.3` built Nov 12 19:42:53,
kart 3, `writes:true`, the same pinned VESC address and UUID, and rejoined Wi-Fi. The Core2
reports kart 3 live data with zero parse errors and keeps its OTA configuration and
`gokart-display-3` hostname. The encrypted pair re-linked on channel 2 with aligned channels.
No course peer is configured on either board. Both boards report the same version strings as
the pair they replaced; the hash and the Heltec's build time tell them apart.

**VESC powered.** The owner lifted the wheels and turned the VESC on; the console was watched
read-only. The Heltec connected to the pinned controller (6.02, `75_300_R2`, UUID equal to the
pin) with `id_ok`, `limits_ok`, baseline source `read` and zero CRC errors, and did not reboot.
It adopted the VESC's stored limits (scale 1.00, 150000 ERPM) as SPORT without writing. Core2
mode holds then produced ECO 0.50 / 21661 ERPM, NORMAL 0.75 / 36102 ERPM, SPORT 1.00 / 150000
ERPM and ECO again, each written and verified, the same values as November 10 and 12. The wheel
ran forward in every mode (peaks 19800, 31074 and 36776 ERPM) and once in reverse to −8630 ERPM
right after power-up; all 211 samples showed fault 0 and the VESC link never dropped. The owner
reported the sequence done and that it felt right. SPORT topped out at 36776 ERPM at 0.94 duty
with the wheels up, so NORMAL's 36102 ERPM cap was at this kart's no-load top speed.

**Soak.** Ten minutes (610 s) with the VESC on, in ECO, wheels up and nothing touched; both
consoles were logged and only `status` was sent. Neither board reset. The VESC link was up in
all 1219 samples with fault 0 and zero CRC errors. The Heltec's heap low-water mark went from
37620 to 37360 bytes in the first two minutes and stayed there for the remaining eight; free
heap stayed between 42.7 and 45.4 kB. The Core2's heap stayed at 147 kB with zero parse errors
and the pair stayed linked on channel 2 (ten of about 3200 received lines dropped). The pit
base sent kart 3 the telemetry-rate command eight times; no other remote command arrived.

**Speed factor.** After the soak the owner decided to set the Heltec's speed factor on kart 3
from the default 2.48 to **1.736**. The default was measured on kart 2 against its stored 14
motor poles; kart 3's VESC stores 20 poles with the same gear and wheel numbers, so the default
made kart 3's ERPM caps 20/14 times kart 2's (about 21 mph in ECO and 36 mph in NORMAL if the
drivetrains match, which the owner confirms). 1.736 = 2.48 × 14/20 gives kart 3 kart 2's caps:
15163 ERPM in ECO and 25272 in NORMAL. The console command `speedcal 1.736` stored it on the
Heltec; it wrote nothing to the VESC. Until a mode was selected (about ten minutes) the VESC
kept 0.50 / 21661 ERPM and the Heltec reported the actual mode as unknown, because that cap
matched no mode. The owner then held ECO and NORMAL on the Core2: 0.50 / 15163 ERPM and
0.75 / 25272 ERPM were written and verified. With the wheels up the wheel peaked at 14799 ERPM
in ECO and 23556 in NORMAL, against 19800 and 31074 earlier the same day at 2.48; fault 0, no
link drop, no reset. Final state: NORMAL, stopped. **The factor is provisional until a GPS
check on the road** (full pedal in ECO on flat ground should settle at 15 mph).

**Not verified here.** Everything that needs the host: course download, JOIN and its mode
write, the game-speed lock, FIRE and the relative boost. A boost end after a real VESC link loss
or Heltec restart. Pit STOP/SLOW/BOOST; a VESC cold boot; GPS; OTA. The new speed caps against
GPS speed on the road, and SLOW at the new factor. The pit and kart-Pi servers convert wheel
speed with a fixed 2.48 (`WHEEL_CAL`); whether they show kart 3's speed correctly was not checked.

**Rollback.** The November 12 applications are the frozen files in ignored
`firmware/build/bench-candidates/2026-11-12-player/`, and copies read back from these boards
today are in the ignored private folder
`firmware/build/bench-private/game-rules-update-20261113/` with the console and upload logs.
To go back, write `core2-before-app0.bin` or `heltec-before-app0.bin` at `0x10000` on the
matching board, and run `speedcal clear` on the Heltec to return to 2.48. The private dumps
contain pairing keys and Wi-Fi credentials and must stay out of Git.
