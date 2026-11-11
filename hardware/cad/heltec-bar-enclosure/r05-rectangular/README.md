# R05 — rectangular Heltec/GPS enclosure

This prototype preserves the owner's edited Heltec, GPS and antenna positions inside one clean rectangular enclosure. It supersedes the abandoned rear-bay R04 layout. The original owner-edited input is archived in `input/`; it was imported into a new Fusion document before this revision was built.

The rectangular main body, excluding the antenna mount and clamp, is **77 × 36 × 30 mm**, with the long axis parallel to the horizontal kart tube. The inherited clamp is 50 mm wide. Its nominal tube is **25.273 mm (0.995 in)**, with a **25.523 mm bore** and **1.5 mm split gap**. These are prototype fit allowances, not measured printer compensation.

The four printed parts are the case/upper collar, lower collar, lid with integral antenna mount, and removable GPS tray. Installation still uses **four screws total**: two M4 × 30 socket-head clamp screws with M4 nuts, and two M3 × 8 lid screws with M3 nuts. The existing SMA connector nut is connector hardware, not another enclosure screw. Verify actual fastener lengths before assembly; longer clamp screws can enter the electronics space.

## Files

- `GoKart-Heltec-Rectangular-Owner-Layout-R05.f3d` — editable Fusion assembly, including original hidden geometry and hardware references.
- `case-upper-collar`, `lower-collar`, `lid-integral-antenna`, `gps-slide-tray` — each supplied as STEP and millimetre STL; reference electronics, tube and antenna are excluded.
- `assembled-preview.png` and `tray-extracted-preview.png` — assembly and service views.
- `model-audit.json` — owner-pose comparison, dimensions and remaining fit limits.
- `independent-review.json` — independent Fusion geometry, connector and sampled tray-path checks.
- `export-verification.json` — independent exported-file checks.
- `build_rectangular_revision.py` — construction source for a fresh copy of the archived input; do not run it on an already-built R05 document.
- `export_revision.py` — exports the four R05 components.

The model has an editable feature history. Many R05 layout dimensions are explicit feature dimensions; the inherited R03 user parameters do **not** uniformly resize the new enclosure. Use the R05 features/source and recheck interference when changing the layout.

## GPS tray

The tray slides rearward along **−Y**; its rear face sits approximately 0.1 mm inside the shell's rear plane. Push the single latch tongue upward from the underside access opening, then pull the tray out. A 25 mm rearward translation fully exposes the tray. The physical harness must have enough slack or be disconnected before withdrawal.

Four pads support the reference GPS PCB underside at Z15.6 mm. Use small hot-glue spots at PCB edges/back to hold the module in the carrier; keep adhesive away from the ceramic patch, connector, cable strain relief and latch. The guides have 0.25 mm nominal lateral clearance per side and an upper retaining lip. The 10 × 6 × 0.8 mm latch beam requires a physical material/fit test. Its approximately 1.1 mm release movement is forward of the connector and below the receiver package; it must not press on either.

Reference geometry comes from the [official Heltec V4.3.1 STEP](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/3D/HTIT-WB32LAF_V4.3.1%281%29.step) and [GPS accessory STEP](https://resource.heltec.cn/download/L76K/3D/GPS-Module1.STEP), compared with the [GPS accessory dimension image](https://heltec.org/wp-content/uploads/2025/07/L76K_DIMENSION.png).

The actual GPS module is still a fit-check item: Heltec's accessory photo drawing and STEP show different envelopes. The preserved owner pose also puts the receiver very slightly into the conservative rectangular OLED-cover envelope (about 0.094 mm in Y and 0.3 mm in Z). The real cover is not established by the imported PCB STEP. **Do not force this fit or clamp the ceramic.** Check the actual module and cover before installing or gluing anything. The current model records this uncertainty rather than moving the owner's hardware silently.

## OLED and antenna

The OLED opening is 25 × 14.4 mm near the display, flaring to 29 × 18.4 mm at the lid. It is a straight-down service view, with approximately ±12° calculated visibility of the complete nominal display, not a wide-angle dashboard window. Actual text readability remains untested. The [official Heltec V4.3.1 datasheet, page 15](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/datasheet/WiFi_LoRa_32_V4.3.1_Datasheet.pdf) supplies the 22 × 11.4 mm visible display and 33 × 18.6 mm protective-cover dimensions. The owner's photographed board is V4.3, so revision fit still needs confirmation.

The antenna collar is integrated into the lid with a tapered root. Its **exact owner-edited pose** is preserved: approximately 30° from vertical with 35° plan azimuth. This supersedes the earlier 15° R03 choice. The 50.8 mm antenna reference remains non-printable; its 7 mm diameter is only an assumed envelope.

The SMA seat is 2 mm thick, with a 6.6 mm panel bore and 13.2 mm open underside access. Install and tighten the bulkhead while the lid is removed; route the pigtail with slack before closing it. [Samtec's example bulkhead drawing](https://suddendocs.samtec.com/prints/sma-j-c-x-st-bh4-mkt.pdf) specifies a 6.6 mm panel hole and 8 mm nut; this does not identify the owner's pigtail. Actual thread length, flange shape, washers and tool clearance must be checked. Do not force an unmatched connector or use the printed collar to resist excessive tightening torque.

## Printing and first fit

Use unfilled PETG or ASA. Avoid metal/carbon-filled material around the radio/GPS antennas. The tray should be printed floor-down so its latch can flex along continuous layers. Check slicer bridges/supports on the case, especially the collar and floor overhangs, and on the lid's recessed opening and canted collar. These are not claimed to be support-free parts. Remove support without enlarging the board stops, screw seats or SMA panel.

Independent CAD review found four single connected solids, a clear SMA seat/access path, a clear central OLED sightline, and no material interference along the sampled released-tray withdrawal path. That path check removes the tooth from the rigid test shape to represent release; it does not validate real flex, friction or harness motion. The tiny GPS/cover-envelope conflict above remains unresolved.

Before a full assembly, check clamp fit on the actual bar, tray/latch sliding, SMA seating, GPS/cover clearance and USB overmould access. Do not force a tight printed fit. Then check GPS reception outdoors with LoRa and the local wireless link active. This is a reviewable fit prototype; weather sealing, vibration endurance, clamp strength, print shrinkage and road use have not been validated.
