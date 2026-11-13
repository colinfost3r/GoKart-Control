# Kart 3 complete USB capture — 2026-11-10

The replacement/reseated USB data cable worked. This read-only capture establishes kart 3's
current runtime motor/app settings **before any tune alignment**. It is not a saved-flash image,
rollback firmware or an approved import preset. No settings, resets, motor commands, motor detection
or firmware writes were sent by the capture procedure.

| Item | Recorded value |
| --- | --- |
| Capture time | 2026-11-10 19:28:31–19:28:32 UTC (14:28 EST) |
| Transport / port | USB serial, `/dev/cu.usbmodem3041` |
| Firmware / hardware | 6.02 / 75_300_R2, `no_hw_limits` |
| Controller UUID | `37004e000951343037353739` |
| Fleet assignment | Kart 3, matching the independently commissioned Heltec pin |
| VESC CAN/controller ID | 19; separate from fleet kart ID 3 |
| Motor settings | 189 fields, signature `2e43a161`, 482-byte payload |
| Application settings | 187 fields, signature `1d003a2c`, 494-byte payload |
| Snapshot telemetry | 82.1 V, 0 ERPM, 0 A motor/battery current, fault 0, ESC 19.1 C |
| Motor temperature | Sensor unwired (owner); raw -95.4 C is unusable despite NTC configuration |

## Evidence and reproducibility

- [raw/manifest.json](raw/manifest.json) records the four allowlisted queries (0, 4, 14, 17),
  successful receive-time CRC checks, UTC query times, payload lengths/SHA-256, complete identity
  and both schema validations. Raw files contain response payloads, not transport frames.
- `raw/*.bin` and `decoded/*.json` are retained unchanged. Sequential reads are not atomic;
  another client or the driver could have changed state between replies.
- [comparison-reviewed/comparison.md](comparison-reviewed/comparison.md) and its JSON companion
  compare every one of the **376 fields** with the dated November 5 kart-2 reference:
  **326 equal, 50 different (40 motor / 10 app)**. Exact equality has no numeric tolerance.
- The initial `comparison/` report is retained for provenance. It contains a stale sentence
  saying a new kart-3 capture is still required. `comparison-reviewed/` corrects that sentence;
  identities, timestamps, hashes, values and all counts are identical.
- [Every-field assessment](assessment.json) and [all 50 differences reviewed](assessment.md) preserve
  calibration/identity and separate shared tuning from protections.
- [Review and proposed next steps](../../../../../docs/kart3-tune-comparison.md) distinguish
  shared tune candidates from per-unit calibration, protections and unresolved measurements.

Commands run from the repository root (output directories were new):

```sh
python3 -B tools/vesc/capture.py --port /dev/cu.usbmodem3041 \
  --out hardware/vesc/kart3/2026-11-10/usb-before-tune/raw
python3 -B tools/vesc/decode.py hardware/vesc/kart3/2026-11-10/usb-before-tune/raw \
  --out hardware/vesc/kart3/2026-11-10/usb-before-tune/decoded
python3 -B tools/vesc/compare.py hardware/vesc/baseline-kart/2026-11-05/raw \
  hardware/vesc/kart3/2026-11-10/usb-before-tune/raw \
  --out hardware/vesc/kart3/2026-11-10/usb-before-tune/comparison-reviewed
```

The November 5 reference does not establish kart 2's tune today. Eamon reports its drivetrain
metadata is inaccurate and compensated by Heltec `speedcal=2.48`; those stored values are not
measurements to copy. Heltec calibration, installed Lisp scripts and commercial component ratings
are not part of these 376 VESC fields. The generic offline decoder reports motor-temperature
wiring as unknown; the owner's unwired-sensor statement above supplies that missing context.
