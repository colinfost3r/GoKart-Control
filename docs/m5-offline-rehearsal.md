# Core2 offline rehearsal and next bench session

This milestone changes the native Core2 presentation and adds an isolated demo. It does
not deploy firmware or implement host publishing, wireless course transfer or live items.

## Available before a kart is powered

- Open [the self-contained browser rehearsal](previews/core2-player-rehearsal/index.html)
  in a browser (path below is relative to the repository root). It needs no server, account,
  radio or hardware port. Select scenarios for invitation, download, GPS/link/host loss,
  fault, STOP/SLOW and course absence. The LIVE scenario is also fake, for appearance only.
- The pictures use `DriverView.h`, the same C++ drawing implementation as the firmware.
  Browser text approximates the LCD bitmap font. Browser interaction only selects scenes;
  separate native tests exercise the real touch functions and demo state transitions.
- Build `firmware/build.sh m5-demo` for a standalone Core2 rehearsal. It initializes neither
  ESP-NOW nor the serial VESC/display link, disables mode output, uses a RAM demonstration
  loop, and does not load or replace the saved course. No image has been uploaded by this work.
- Production `m5` and `m5-espnow` share the new styling and page button. Existing guarded
  mode selection, own-kart following, course storage and maintenance remain available.
  Live FIRE stays unavailable; invitations/items in the demo are not live radio features.

From the repository root:

```sh
python3 tools/m5/preview_driver.py --out /tmp/gokart-core2-preview
# Open /tmp/gokart-core2-preview/index.html in a browser.
# Or open docs/previews/core2-player-rehearsal/index.html for the committed copy.
```

The compiler needs ArduinoJson headers; set `ARDUINOJSON_DIR` when they are outside the
usual Arduino library directory. `--write-scenes` additionally exports all 30 SVG scenes.
The preview can be regenerated without Python packages or an internet connection.

## Standalone demo interaction

- Upper-right MAP/DASH changes page. A touch remains consumed until release; dragging the
  same press into a mode button, FIRE or the maintenance header cannot activate it.
- JOIN opens a simulated invitation; JOIN inside it starts a three-second simulated download.
  On completion the preview carries one SHELL. MAP/FIRE consumes it once, with no packet sent.
- The invitation dot pulses until opened. A failed download retains the previous demo course.
- Demo USB diagnostics accept `demo invite`, `demo download`, `demo ready`, `demo used`,
  `demo download-error`, `demo host-lost`, `demo gps-lost`, `demo link-lost`.
  These only select simulated states; none connect to or change a vehicle. Live builds do
  not implement these scenario commands. `status` remains available on the board's own USB.
- Touch/visibility still need physical checking on a Core2 at its mounted viewing distance.
  Host renderings do not establish sunlight readability, gesture reliability or RF behavior.

## Next hardware session: small, separate acceptance steps

1. Record the installed Core2 image, target, kart ID and existing pairing/OTA state. Select
   either the no-output demo or the live display update deliberately; never flash the separate
   Eamon `core2` item-only target over this dashboard. Preserve rollback/NVS.
2. **Core2 on USB, VESC off:** verify DEMO / NO OUTPUT, page switching, invite pulse/acknowledge,
   simulated download, single FIRE, and disabled modes. This can be done without a kart.
3. **Live display:** restore/use `m5-espnow`, verify kart3 and paired Heltec, inspect stale/lost
   states and existing course persistence. Existing OTA header is still a 1.8-second hold.
   Do not mistake demo status or a cached graphic for a real connection.
4. **Outside:** acquire a fresh own GPS fix, confirm own marker follows at fixed scale,
   nearby peer labels and clipping, and correct course geometry. The sample loop is not a
   surveyed Manresa route. Provision a deliberately selected real outline via the existing
   USB helper for this current milestone; it is not a host-course download.
5. **Stationary controls:** verify the page button cannot select a mode and that deliberately
   held mode buttons retain readback/unknown-state behavior. Existing VESC tune/filter settings
   are not part of this display update.
6. **Future multiplayer gate:** only test actual JOIN/download/items after the host publisher,
   full game package, course peer/channel integration and Core2/Heltec game requests are built.
   Use Eamon's host plus kart3; establish display-only transfer/session evidence before effects.

## Still needed before a real player-only game

The [player-mode brief](m5-player-mode.md) defines the remaining work: host Pi-to-Heltec
publisher, authenticated course transfer, atomic game-package cache, Core2 player/inventory
logic and typed session/attack requests through the own Heltec. A successful UI rehearsal is
not a successful radio download or motor-effect test. Eamon upstream `59976df` was reviewed;
this UI milestone does not merge its newer Pi inventory/OTA/power changes.
