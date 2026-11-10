# Kart 3 M5 telemetry and OTA evidence — 2026-11-10

The owner confirmed working DASH/MAP tabs and live readings on the Core2.
[observations.json](observations.json) contains sanitized device observations and exact application hashes.
Raw captures, full 16 MiB rollback images, Wi-Fi credentials and ESP-NOW keys remain private under ignored
`firmware/build/bench-private/`; no credentials or precise GPS coordinates are included here.

The original copied BLE binding belonged to kart 2. The owner confirmed kart 3 has a different VESC.
The copied binding was cleared; the sole newly discovered candidate was connected read-only, its UUID
read and pinned, and fresh telemetry reached the Core2. Kart 3 is **75_300_R2 / firmware 6.02**,
MAC **f7:bd:23:cc:62:0e**, UUID **37004e000951343037353739**. This is distinct from the original
6.00 / 75_100_V2 baseline. Runtime limits are observations, not a saved configuration backup or tuning approval.
No VESC firmware/settings, throttle, brake, current or duty commands were written.

Both accessory USB uploads verified four segments and retained NVS. Core2 also accepted an authenticated
wireless upload of the same tested application and recovered its paired display link. OTA credentials
persisted, while the update window returned to inactive after restart. Heltec's authenticated OTA
advertisement was observed earlier; an actual Heltec OTA upload was not tested here.

The Core2's `mode_ready:false` is intentional: installed Heltec firmware has `ENABLE_VESC_WRITES=0`.
Reading/confirming the VESC's current mode does not enable driver or pit mode commands. Enabling those is
subsequent work, including fresh controller identity, baseline association and explicit request checks.

276 offline tests passed with zero skipped; all eight affected firmware targets compiled. ESP-NOW reception,
recovery and real BLE coexistence were observed at the bench, with occasional dropped/expired packets.
Eight-kart RF capacity, physical authenticated-packet tamper tests, prolonged soak and driving tests remain open.
