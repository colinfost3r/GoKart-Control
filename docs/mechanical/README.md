# CAD and 3D-printing handoff

Updated 2026-11-11. Mechanical specialist lane for GoKart Control, created at the
owner's request with the project conversation as context. This brief records the
starting point. The current deliverable is a fit-check prototype, not a production release.

**Current CAD work:** [owner-edited Heltec/L76K enclosure R05](../../hardware/cad/heltec-bar-enclosure/r05-rectangular/README.md). It follows the owner's edited antenna, GPS and collar geometry, adds a slide-in GPS carrier with one end latch and an OLED window, and makes the antenna mount integral with the lid. The latest owner instruction calls for one 77 × 36 mm rectangular shell around both boards, with a flush GPS tray face and no rear appendage. The edited antenna is now 30° from vertical at 35° in plan, superseding R03's indexed 15° insert. The horizontal 0.995-inch bar, ASA/PETG and four installation screws maximum remain. The original edited input is archived with R05; [R03](../../hardware/cad/heltec-bar-enclosure/r03-parallel/README.md) remains available as history. Physical fit remains to be checked.

The owner chose to coordinate this specialist through the existing project chat.
Prefix a request with **CAD agent:** to route mechanical work to this specialist;
this is a conversation convention, not a built-in app mention.

## Scope and ownership

Develop enclosures, display cradles, accessory mounts, cable guides and strain
relief for the karts. Priorities are driver visibility, service access, positive
retention, repeatable assembly and replacement across the fleet. Keep mechanical
work coordinated with Eamon and Hunter through the existing GoKart Control repo.

- Canonical project: `~/Projects/50 Day/GoKart Control/`.
- Mechanical branch: `mechanical/kart-mounts`; worktree: `.worktrees/cad-3d-printing`.
- Current software base: `e77d19b` on `v1.5/m5-core2`, November 11; includes the
  no-SD follow map and Eamon integration. Initial mechanical brief used `a3990c4`.
- Software work proceeds independently in `.worktrees/m5-v1.5`; read its current
  handoff before deciding any connector, orientation or maintenance requirement.
- Do not edit controller settings, firmware, radio configuration, board pairing or
  Hall/pedal calibration as part of mechanical work. Do not operate the kart.
- Preserve existing CAD and measured evidence. Never derive dimensions by scaling
  an uncalibrated photo or by copying a differently named controller's CAD.

## Established project facts

| Item | Current evidence and mechanical implication |
| --- | --- |
| Fleet | Eight target karts. Kart 3 is this setup's tested electrical reference; karts 4 and 5 will copy it. Karts 1 and 2 remain Eamon's test units. No chassis geometry survey is recorded here. |
| v1.5 display | Owner-confirmed M5Stack Core2 v1.3 / K010-V13, 320×240 touchscreen. Touch, live telemetry and mode selection have been demonstrated. Preserve screen access and USB maintenance access. |
| Local link | Core2 and Heltec use paired ESP-NOW; a data cable between them is optional. Each still requires appropriate power and mechanical retention. Do not add UART wiring as a mechanical prerequisite. |
| Supervisor | Heltec HTIT-WB32LAF V4.3, OLED and USB-C, external LoRa antenna/pigtail. OLED and connector access are useful for service. Protect the small RF connection from cable loads. |
| GPS | Separate cabled Quectel L76K daughterboard with ceramic patch antenna is visible in supplied photos. Mounting must account for the actual module, cable, antenna orientation and outdoor reception. |
| v2 option | Raspberry Pi 3 Model B V1.2 and LESOWN L7-family 7-inch 1024×600 HDMI/USB-touch panel. A separate packaging variant, not a requirement for the current Core2 design. |
| Controller | Owner identifies kart 3 as Flipsky 75100 Pro V2.0. Firmware reports `75_300_R2`; that string is not a mechanical model identification. |
| Power and driver controls | 72 V nominal / 84 V full battery; hardwired throttle and reverse, mechanical brake. Motors have no wired temperature sensors. Accessory mounts must preserve existing controls and service access. |
| Reliability | Display, supervisor or radio loss must not alter the kart's driving state. Mounting/power choices must not make VESC operation dependent on a display enclosure. |

Current electrical evidence and commissioning limits live in the
[main handoff](../../HANDOFF.md), [M5 guide](../../firmware/m5-core2/README.md) and
[kart 4/5 replication guide](../kart4-kart5-replication.md). The saved reverse filter
and −5 A motor-braking minimum passed kart-3 bench checks; this is not fleet or
loaded-road acceptance. Mechanical work must preserve that setup.

The [November 5 photo archive](../../hardware/photos/2026-11-05/README.md) identifies
hardware but is not a dimensional survey. Some early statuses in
[the hardware inventory](../hardware.md) predate the later bench evidence.

## Existing mechanical work to preserve

1. **CH20 charger/buck-converter steel holder:** the canonical checkout contains
   untracked `hardware/cad/charger-holder/2026-11-09/` with four DXF exports and
   `README.txt`. The README identifies Fusion document **GoKart Battery Holder
   RENEW**, component **CH20 Steel shell**, and says design changes were unsaved at
   that checkpoint. Verify the current Fusion document before making changes.
   These files were not copied, staged or modified for this handoff.
2. **Eamon's Pi dash hood:** the main handoff records a November 7 redesign with
   CAD outside this repository. Locate that source before duplicating its mounting
   interface. Its geometry is not established by the software handoff.
3. **Core2 cradle orientation:** coordinate with current firmware and any existing
   physical cradle before fixing a new mount's rotation. The software branch is
   actively evolving; do not assume orientation from an old screenshot.

## Other candidate parts

A later candidate is a **removable Core2 cradle mounted to the kart's existing dashboard
support**, with a replaceable mounting adapter. This gives a small, testable first
part for kart 3 and a reusable interface for karts 4/5. Preserve the Core2's factory
case. Keep the entire touch area clear and provide positive retention plus access
to power/USB, buttons and any intended SD or Grove use. Confirm the actual installed
unit and cable plugs before designing those openings.

The active Heltec/GPS enclosure is separate from the Core2 display mount. Its RF placement is a prototype layout requiring outdoor testing, not qualified antenna separation.

## Measurements for a future Core2 mount

| Priority | Capture | Status |
| --- | --- | --- |
| 1 | Actual kart-3 attachment surface: tube diameter/section or plate dimensions, usable length, hole centres and diameters, nearby obstructions | Not measured |
| 1 | Desired screen position and orientation; driver eye/reach position; steering and knee clearance through full movement | Not measured |
| 1 | Actual Core2 case envelope, retention/contact surfaces and connector/button locations; installed plugs and cable bend envelope | Not measured |
| 2 | Existing cradle/hood source and fastening method, available hardware and tool-access space | Source/measurements needed |
| 2 | Printer model, nozzle/process, build volume and available materials; expected sun, rain, cleaning and heat exposure | Not recorded |
| 2 | Kart-4/5 mounting-interface comparison with kart 3 | Not checked |
| Later | Heltec and GPS board envelopes, mounting features, antenna bulkhead thread/panel requirements, harness lengths and supply location | Not measured |

For the first pass, a perpendicular photo of the intended mount location with a
ruler plus measured attachment dimensions is sufficient to begin layout; a final
fit requires direct measurements. Record units, measurement tool and which kart
was measured. Use millimetres in new CAD and identify any inch-based legacy files
explicitly.

## Deliverables and validation for each part

Keep each component under `hardware/cad/<component>/` with an editable source,
neutral STEP when applicable, print-ready 3MF/STL, a dimensioned assembly view,
fastener/insert list and a short revision/readme. Record print orientation,
material, layer settings and fit allowances only after choosing the printer and
validating the mating geometry. Do not release anonymous STL-only revisions.

First print a fit coupon or partial cradle to check retention and connector
clearance. Then check the assembled part on kart 3 for touch access, cable strain,
service removal, steering/knee clearance and fastener retention. Record observed
results before copying to 4/5. Environmental, vibration and outdoor GPS/radio
checks remain separate acceptance tasks; a successful desk fit does not establish
those results. The active Heltec prototype records its ASA/PETG selection, dimensions and explicit fit assumptions in its own README. Future parts need their own measured inputs and validation.
