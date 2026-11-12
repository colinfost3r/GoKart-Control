# Kart 3 native-player applications installed — 2026-11-12

Both kart 3 accessories now run the November 12 native-player candidate
([manifest](../../../docs/validation/m5-player-2026-11-12.json)). This supersedes the installed
state recorded in [the November 10 commissioning](../2026-11-10-kart3/mode-commissioning/README.md)
without changing that evidence. Details are in [observations.json](observations.json).

| Board | Before (`4a582f0`, read back from flash) | Written |
| --- | --- | --- |
| Core2 `m5-espnow` | `996c4387…9b0a` | `894a1a34537b5894110ddb120b2419f18b0fad8432b0e7acac775306ce58d3ac` |
| Heltec `kart-m5-espnow` | `11e556e8…21f2` | `d43662645457f51283010d655cc2f60d5740adafc015adc59910e70fd136cab9` |

**Method.** The VESC was off throughout. Each board's partition table, otadata, NVS and
installed application were first read over USB; both applications matched the documented
hashes and both boards boot from `app0`. Only the application was then written at `0x10000`
with esptool 4.9.0, which verified the written data. Bootloader, partition table, otadata and
NVS were not written.

**Observed afterwards.** The Heltec reports `kart-0.3.3` built Nov 12 08:55:51, kart 3,
`writes:true`, the same pinned VESC address and UUID, and rejoined Wi-Fi as `gokart-3.local`.
The Core2 answers the new `m5_game` and `share status` commands, shows kart 3 live data, and
keeps its OTA configuration and `gokart-display-3` hostname. The encrypted pair re-linked with
aligned channels; the channel moved from 6 to 2 because the Heltec followed the Wi-Fi access
point. No course peer is configured on either board yet. The owner confirmed the Core2 shows the new
full-screen map with the DASH/MAP button and FIRE box.

**Not verified here.** VESC connection, identity and mode control with the new Heltec
application; wired throttle and reverse coexistence; touch and page switching; GPS; course download,
JOIN and FIRE; OTA. Free heap on the Heltec with Wi-Fi up is 45.7 kB, against 59.2 kB on the
previous application; watch `heap_min` once BLE is connected.

**Rollback.** The previous applications, NVS copies, raw console logs and upload logs are in
the ignored private folder `firmware/build/bench-private/player-update-20261112/`. To go back,
write `core2-before-app0.bin` or `heltec-before-app0.bin` at `0x10000` on the matching board.
The NVS copies contain pairing keys and Wi-Fi credentials and must stay out of Git.
