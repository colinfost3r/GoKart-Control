# R07 — floor-backed GPS supports and accessible clamp bolts

R07 retains the **79 ×36 mm enclosure**, internal GPS wiring, board positions, OLED opening and integral antenna lid. The GPS support structure now reaches the case floor, and the two M4 tube-clamp screws move outward so their heads and driver access clear the enclosure. There are still **three printed parts and four installation screws**; the two M3 lid screws stay in place.

The inspected R06 model matched the previous milestone and was archived in `input/` before creating R07. The owner then made additional manual edits directly to R07. Those edits are authoritative and retained in the final native model; the generated-base script does not reproduce them and must not be used to replace them.

## Owner edits preserved

The final model retains `OffsetFaces1` and `Extrude19`–`Extrude24`, captured in `input/owner-edited-R07-timeline-667.f3d` before the final adjustment. These edits raise/extend several GPS supports and add material near the end clip. Only a local **lid relief** was subsequently added around the enlarged left front support. The case volume stayed exactly **39.939555021424 cm³** before and after that relief; the lid remains one solid and retains all four capture feet. The relieved foot has **2.4345 mm²** of remaining horizontal capture face. See `owner-edit-provenance.json` for the measured comparison and relief bounds.

## GPS support changes

Rear socket ribs run directly from the floor at Z2.5 mm to the existing support ledges. Forward supports avoid the Heltec PCB: their feet sit behind or outside the board, with 45° transitions up to the GPS supports. The central harness space and the P3 plug approach remain open.

The table describes the generated base. Owner edits extend some support faces; the final native archive is the complete specification. The final independent review checks these floor columns again.

| Support | Floor sample centers, mm | Generated-base transition |
| --- | --- | --- |
| Rear PCB capture ribs | X±11.6, Y−40.9 | Floor Z2.5 to Z14.4 |
| Rear GPS ledge ribs | X±11.375, Y−32.55 | Floor Z2.5 to Z14.1 |
| Forward ledge ribs behind PCB | X±11.375, Y−27.1 | Y−26.4/Z13.0 to Y−25.3/Z14.1, 45° |
| Front socket columns outside PCB | X±14.7, Y−21.0 | X±16/Z7.7 to X±8.25/Z15.45, 45° |

The generated base retained the flexible end clip. Subsequent owner edits add material around the front supports and end-clip region; final clip movement must be checked physically and is not assumed unchanged. Short retaining lips and the clip are intentional overhangs. This revision improves internal FDM support paths; it does **not** claim that the entire enclosure can print without supports. Check the external case-floor/clamp overhangs and latch support placement in the slicer.

## Clamp access

The two M4 axes move from X±18.5 to **X±26 mm**, giving **52 mm bolt spacing**. Upper and lower ears extend to X±33 mm, making the collar **66 mm wide**. A nominal **12 mm diameter straight driver envelope** leaves **2 mm to the 36 mm enclosure sides** above the collar mounting plane; the final independent review checks the complete lid shape as well.

The original 25.273 mm tube, 25.523 mm bore and 1.5 mm split gap remain. Both old bolt holes and nut channels are filled before the new passages are made. New nut pockets use 7.3 mm across-flats clearance with flats aligned to 7.5 mm insertion slots; pocket depth is 3.4 mm. Insert the M4 nuts from the outboard ends of the ears.

Use two **M4 ×30 socket-head screws** and M4 nuts for the clamp, plus two **M3 ×8 screws** and M3 nuts for the lid. Nominal reference screws model a 4 mm shaft and 7 mm ×4 mm socket head; the 8 mm ×2 mm counterbore leaves part of the head exposed below the collar for access. Actual fastener dimensions and driver shape still need checking. The 12 mm reference is a straight access corridor, not a guarantee for every tool handle.

## Files

- `GoKart-Heltec-FDM-Supports-R07.f3d`: editable assembly and preserved input history.
- `case-upper-collar`, `lid-integral-antenna`, `lower-collar`: each exported as STEP and millimetre STL.
- `assembled-preview.png`: the widened collar and bolt locations.
- `open-case-supports-preview.png`: lid and hardware hidden to expose the floor-connected ribs.
- `owner-edit-provenance.json`: archived owner features, unchanged case volume and the lid-only correction.
- `model-audit.json`, `independent-review.json`, `export-verification.json`: geometry and exported-file checks.
- `build_fdm_revision.py`, `apply_owner_lid_relief.py`, `export_revision.py`, `make_previews.py`: construction/export/view scripts. The build script describes the generated base only. Use the final native archive for the owner-edited result; do not regenerate over it.

Hardware, assumed harness envelopes, nominal screws/nuts and driver cylinders are non-printable references. The inherited earlier user parameters do not uniformly resize R07; use the explicit feature dimensions/source and repeat interference checks after edits.

## Preserved fit limits

The GPS bare socket still has **4.247 mm** to the inner rear wall, satisfying the owner's confirmed 4 mm reference. The wires route entirely inside the case, down behind the GPS and forward beneath the Heltec PCB into its **P3 8-pin GNSS connector**. The 8 ×2 mm wire envelope and mating-plug allowances remain assumptions; actual cable diameter, plug dimensions, length and bend radius are unmeasured.

The preserved GPS receiver still slightly overlaps the conservative rectangular OLED-cover proxy (approximately 0.0845 mm in Y and 0.3 mm in Z). The actual accessory/cover fit must be checked without force. Motor/control electronics and hardware poses are unchanged.

Use unfilled PETG or ASA. Check print tolerance, clamp fit, nut insertion, tool access, clip flex and the actual harness before installation. FDM strength, vibration durability, weather sealing, radio/GPS performance and road use remain unvalidated prototype work. Manufacturer hardware sources and the internal route rationale are recorded in [R06](../r06-internal-harness/README.md).
