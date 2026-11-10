# Kart 3 VESC evidence — 2026-11-10

| Directory | Scope / outcome |
| --- | --- |
| [usb-before-tune](usb-before-tune/README.md) | Original complete USB runtime capture; 376 fields, 50 differences from dated kart 2. This is the Desktop backup source. |
| usb-backup-before-tune | Failed attempt: USB port absent; manifest incomplete, no payloads/settings sent. |
| usb-prewrite | Failed attempt: USB port absent; manifest incomplete, no payloads/settings sent. |
| usb-prewrite-connected | Successful fresh read after reconnect; all 376 settings match original. |
| [tune-trial-v1](tune-trial-v1/README.md) | Offline 12-field proposal; all other motor/app bytes preserved. Prepared artifact remains unchanged after application. |
| tune-preflight-v1 | Read-only guarded preflight passed; no configuration write. |
| [tune-applied-v1](tune-applied-v1/README.md) | One authorized persistent motor-config write, ACK and all-376-field exact readback. No motor actuation/reset/detection. |

Controller: UUID `37004e000951343037353739`, 6.02 / 75_300_R2, fleet kart 3, VESC CAN ID 19.
Historical reference: November 5 / UUID `2c004c000951343037353739`, 6.00 / 75_100_V2.
Neither runtime export proves saved-flash contents. Keep all captures unchanged; add new dated
folders for subsequent observations. Full change reasoning is in the [tune review](../../../../docs/kart3-tune-comparison.md).
