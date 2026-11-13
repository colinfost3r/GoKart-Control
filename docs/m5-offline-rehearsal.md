> Historical no-output display rehearsal. Real host downloads and native FIRE were subsequently
> implemented; use [the current player guide](m5-player-mode.md) and [handoff](CLAUDE_HANDOFF.md).
> These browser/demo scenarios remain synthetic and never send commands.

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
  mode selection, own-kart following and course storage remain available. Maintenance/OTA
  is available only in `m5-espnow`; UART `m5` and standalone `m5-demo` require USB firmware updates.
  Live FIRE stays unavailable; invitations/items in the demo are not live radio features.

From the repository root:

```sh
python3 tools/m5/preview_driver.py --out /tmp/gokart-core2-preview
# Open /tmp/gokart-core2-preview/index.html in a browser.
# Or open docs/previews/core2-player-rehearsal/index.html for the committed copy.
```

The compiler needs ArduinoJson headers; set `ARDUINOJSON_DIR` when they are outside the
usual Arduino library directory. `--write-scenes` additionally exports all 32 SVG scenes.
The preview can be regenerated without Python packages or an internet connection.

## Background map, game symbols and compact HUD

The Pi uses `kart/server/mapsync.py` to download `/map/package.json`, its image and zones
from the pit over Wi-Fi into a local cache. The repository shop preset uses CT ECO aerial
imagery; the Manresa preset references Eamon’s local-only SkyFi image with CT ECO assets
available as a fallback. Those are georeferenced images, not Google Maps tiles. Its MAP
style additionally uses the cached SoNo OpenStreetMap extract.

The Core2 demo now reuses a 240 m square shop crop from that **same OSM extract**, quantized
to decimetres and drawn as quiet outlines. Rebuild with `python3 tools/m5/export_preview_map.py`.
Source/ODbL attribution: [Pi map notes](../pit/server/map/SONO-MAP.md); the full derivative
geometry remains in `pit/server/map/sono-map.geojson`. Credits appear on a five-second startup screen only; they are absent from the map and
game menu. The source and license remain with the geometry. Startup is nonblocking and
consumes touches until release, so a held splash touch cannot select a mode.

The loop, checkered S/F gate, green boost arrows and gold `?` pickup box are
**demonstration overlays**, not surveyed course/game data. Gold 3 is the own kart;
blue numbers identify other karts. Nearby markers are clipped to the follow view.
A fixed 70 m vertical span and north-up orientation remain, but their label and the
scale bar are removed at the owner’s request. The 320×240 map has no kart/status header
or full-width FIRE footer. A small floating card shows GPS MPH and the actual VESC pack
voltage relayed by Heltec. There is no measured SOC field and no local percentage estimate.
Lost GPS hides speed; lost VESC/link hides voltage. FIRE is a compact lower-right control.

Live builds use the same telemetry card but do **not** draw invented game markers or
the shop demo background. (Since November 13 they draw their own built-in street outlines
for the shop and Manresa Island; see
[COURSE_MAP](../firmware/m5-core2/COURSE_MAP.md#built-in-street-lines).) Full host background/zone/lapline packaging and download are
still needed; the current USB course upload accepts an outline only. This preview is
not evidence of lap counting, pickups, boost effects or real radio synchronization.

## Standalone demo interaction

- Upper-right MAP/DASH changes page. A touch remains consumed until release; dragging the
  same press into a mode button, FIRE or another control cannot activate it.
- JOIN opens a simulated invitation; JOIN inside it starts a three-second simulated download.
  On completion the preview carries one SHELL. MAP/FIRE consumes it once, with no packet sent.
- The invitation dot pulses until opened. A failed download retains the previous demo course.
- Demo USB diagnostics accept `demo invite`, `demo download`, `demo ready`, `demo used`,
  `demo download-error`, `demo host-lost`, `demo gps-lost`, `demo link-lost`.
  These only select simulated states; none connect to or change a vehicle. Live builds do
  not implement these scenario commands. `status` remains available on the board's own USB.
- Touch/visibility still need physical checking on a Core2 at its mounted viewing distance.
  Host renderings do not establish sunlight readability, gesture reliability or RF behavior.

The [Claude handoff](CLAUDE_HANDOFF.md) has the exact installed/candidate boundary,
artifact paths, rollback cautions and kart 3 → 4 → 5 sequence.

## Next hardware session: small, separate acceptance steps

1. Record the installed Core2 image, target, kart ID and existing pairing/OTA state. Select
   either the no-output demo or the live display update deliberately; never flash the separate
   Eamon `core2` item-only target over this dashboard. Preserve rollback/NVS.
2. **Core2 on USB, VESC off:** verify DEMO / NO OUTPUT, page switching, invite pulse/acknowledge,
   simulated download, single FIRE, and disabled modes. This can be done without a kart.
3. **Live display:** restore/use `m5-espnow`, verify kart3 and paired Heltec, inspect stale/lost
   states and existing course persistence. Hold the upper-right DASH/MAP button for 1.8 seconds to open updates; sliding away cancels
   the hold. BACK must stay consumed until release, even over a mode button.
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
