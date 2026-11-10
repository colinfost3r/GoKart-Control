# Kart 3 Core2 mode commissioning — 2026-11-10

This supersedes the earlier read-only accessory checkpoint in the parent directory without changing its historical evidence. Both accessories now run the matching control-capable images from source `4a582f0`. See [observations.json](observations.json) for exact application hashes and readbacks; [Heltec](heltec-sanitized.json) and [Core2](core2-sanitized.json) records retain only selected non-secret fields in capture order.

Both segmented USB uploads verified four segments and preserved the existing NVS pairing and OTA credentials. The Heltec reports `writes:true`, correct pinned controller identity, validated limits and `baseline_source:"read"`. Both peers acquired channel 6 with matching received/advertised channel proof; Core2 reported `mode_ready:true`. Speed calibration remains 2.48. Initial SPORT was adopted from a fresh read without a mode write.

The operator held the Core2 buttons and selected ECO, NORMAL and SPORT. All three produced command results and confirmed VESC readbacks:

| Mode | Current scale | Positive ERPM cap |
| --- | --- | --- |
| ECO | 0.50 | 21661 |
| NORMAL | 0.75 | 36102 |
| SPORT | 1.00 | 150000 |

The operator also exercised the wired throttle with the wheels lifted. Rotation was recorded and all sampled VESC faults were zero. Final captured state was SPORT, confirmed, at zero ERPM. The owner confirmed all modes work. These are electrical limits/readbacks, not measured road speeds. Supervisory changes use temporary `store=0`; no app settings, Hall/pedal calibration or further persistent tune write occurred in this session.

Periodic LoRa `rate 1` commands were observed. They do not establish pit mode/STOP/SLOW/BOOST/race acceptance; those capabilities are enabled but still need their own hardware checks. No range, full-fleet, physical braking or road acceptance is implied.

A later Core2 source change makes a busy-radio hold show “release and hold again” instead of failing silently. Its three build variants compile and its production-path regression passes, but the candidate application (`35162e47…`) has **not** replaced the working installed `996c4387…` image. No command is queued or replayed by that change.

The owner plans two additional M5/Heltec karts; their fleet IDs are unassigned. Reuse the firmware architecture, provision unique identities/pairing/OTA credentials and preserve each VESC’s own calibration. Follow [BRINGUP](../../../../firmware/m5-core2/BRINGUP.md). Do not clone another kart’s NVS or whole VESC configuration.
