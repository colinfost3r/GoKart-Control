# R06 — enclosed GPS wiring and side-supported socket

R06 keeps the owner's current hardware positions and the two additional face-healing edits found in the open R05 model. That exact input was archived before creating a separate Fusion document. The enclosure is now one **79 ×36 mm rectangle**, only 2 mm longer than R05. The rear tray opening and underside release hole are closed.

The GPS sits in a fixed socket supported from the case sidewalls. Its underside stays open for the wires. Two rear lips capture the exposed PCB corners; one front end clip retains the module. Remove the lid to service it. The former exterior pull-out tray is superseded. The rear M3 lid pillar and captive-nut seat were restored after clearing the old tray structure; its working screw clearance opens from the top and stops at Z21 mm, leaving the lower pillar solid.

## Geometry and wiring reference

The owner confirmed **4 mm behind the bare GPS board socket** as the required reference. The actual imported GPS socket's rear face is at Y−39.752710 mm and the new inner rear wall is at Y−44 mm: **4.247290 mm modeled clearance**. The mated plug and its wire bend have not been measured.

The destination is the Heltec's **P3 SH1.25 8-pin GNSS connector under the PCB**, not the antenna IPEX connector. Its reference housing spans approximately Y−17.344…−12.044 mm and Z3.341…6.941 mm, with the mating approach from the rear. The modeled route goes behind the GPS socket, down beneath the GPS and around the rear edge of the Heltec PCB, then forward at Z5.1 mm into P3. The rear support pads have local relief for that approach. An internal wire keeper retains the wires below the GPS.

Hidden, non-printable `REF R06…` components show the routing allowances:

| Reference | Assumed envelope |
| --- | --- |
| Wire bundle | 8 mm wide ×2 mm thick |
| GPS mating plug | 12 ×3 ×2.5 mm |
| Heltec P3 mating plug | 12 ×5 ×2.7 mm |

These are explicit design allowances, **not measurements of the owned harness**. The wire reference has square turns for clearance checking; it does not establish a usable bend radius. Independent CAD checks measured minimum clearances to printed parts of 0.25 mm for the wire reference, 0.71063 mm for the GPS plug reference and 0.75 mm for the P3 plug reference. Its rear extent leaves approximately 0.25 mm to the inner rear wall. Check the actual connector, individual wires and routing without compression before closing the lid. The original supplied harness length is also unverified.

## Assembly

1. Fit the Heltec on its supports and confirm the USB plug and P3 mating connection have clearance.
2. Connect the harness to P3 and lay it through the internal keeper, below the GPS socket. Route the other end upward behind the GPS connector, entirely inside the rear wall.
3. Connect the GPS, engage its rear PCB edge beneath the fixed lips, then lower the front edge past the single end clip. The ceramic patch faces upward. Release the clip toward the front (+Y) with the lid removed when servicing.
4. Confirm the connector, wires and PCB are not forced against the shell or lid. Close the lid with its two M3 screws.

Small hot-glue spots on PCB edges/back are optional; keep adhesive off the ceramic antenna, connectors and flexible clip. The supports contact the actual reference PCB underside at Z15.6 mm and the upper captures allow approximately 0.3 mm above its top. Print tolerance and clip flex still need a physical trial.

## Parts and files

There are **three printed parts** and **four installation screws total**:

- Case with integral upper collar and GPS socket.
- Lid with the owner's integral antenna mount and OLED opening.
- Lower collar.
- Two M4 ×30 socket-head clamp screws with M4 nuts; two M3 ×8 lid screws with M3 nuts. The stock SMA nut is connector hardware.

The tube remains 25.273 mm (0.995 in), with a 25.523 mm modeled bore and 1.5 mm split gap. The clamp is 50 mm wide. The main shell plus flat lid is 30 mm high; the canted antenna mount extends above it. Fastener length and physical clamp fit require checking.

`GoKart-Heltec-Internal-Harness-R06.f3d` contains the editable assembly and preserved history. The three parts also have STEP and millimetre STL exports. `model-audit.json`, `independent-review.json` and `export-verification.json` document the checks. `assembled-preview.png` shows the closed exterior; `internal-route-preview.png` shows the routing reference through the transparent shell: **orange is the assumed 8 ×2 mm wire envelope; blue represents the two unmeasured mating-plug allowances. These colored solids are not printable parts or a measured harness.** `input/` preserves the owner's exact pre-R06 state. The build/export scripts are for fresh copies and the named R06 document; inherited older user parameters do not uniformly resize the new layout.

## Remaining physical checks

The owner's GPS position still creates the previously recorded tiny receiver overlap with the conservative rectangular OLED-cover envelope (about 0.0845 mm in Y and 0.3 mm in Z). The imported Heltec STEP omits that cover, and the real accessory revision differs between Heltec's GPS photo drawing and STEP. Check the actual hardware without force; R06 does not silently move it to hide that uncertainty.

The OLED opening remains a straight-down service view, approximately ±12° for the complete nominal display. The antenna collar retains the owner's approximately 30° cant/35° azimuth, 2 mm SMA seat, 6.6 mm bore and 13.2 mm underside access. The 2-inch antenna is a reference only; its diameter and actual bulkhead thread/flange dimensions are unverified.

Use unfilled PETG or ASA and inspect support placement, especially beneath the side-supported socket and flexible clip. This is a fit prototype; physical latch action, harness bend/length, print shrinkage, vibration, weather sealing, RF performance and road use are unvalidated.

Manufacturer references: [Heltec V4.3.1 STEP](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/3D/HTIT-WB32LAF_V4.3.1%281%29.step), [V4.3.1 datasheet, page 15 for OLED](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/datasheet/WiFi_LoRa_32_V4.3.1_Datasheet.pdf), [GPS accessory STEP](https://resource.heltec.cn/download/L76K/3D/GPS-Module1.STEP), and [GPS accessory dimensions](https://heltec.org/wp-content/uploads/2025/07/L76K_DIMENSION.png).
