# R08 — recessed lid and #4 plastic screws

This revision starts from the **owner's extended-base model**, archived before any changes. The final native preserves that base, the lower collar, GPS supports, internal wiring route and hardware positions. Only the upper lid interface and lid fasteners are revised. Earlier build scripts must not replace the owner's edited geometry.

**Not print-ready as a complete assembly:** the owner input has no upper-left tube-clamp ear, and the remaining right ear touches the case only along three edges with zero-thickness attachment. The case STL therefore fails manifold validation. The new lid and lower-collar meshes pass their individual checks; the case STL is retained for diagnosis, not printing. The original base remains unchanged pending authorization for a finite-thickness connection and a decision about the missing ear. See `case-topology-diagnostic.json`.

## Lid interface

The lower **1.5 mm** of the lid locates inside a raised case rim with **0.3 mm nominal clearance per side**. A **0.5 mm, 45° entry chamfer** guides the lid into place. An inward ledge provides approximately **1 mm of perimeter bearing**. The lid's top remains at Z30 mm; the antenna and OLED opening stay at their existing positions. The lid has a full-size top cap with a stepped lower edge, so it seats on the perimeter rather than relying on two screws for location.

The locating opening is 32 ×75 mm, centered at Y−6.5 mm. The lower lid edge is 31.4 ×74.4 mm. The case rim reaches Z29 mm and the lower lid edge starts at Z27.5 mm. These are prototype fit allowances for PETG or ASA; actual printer fit has not been tested.

## Lid screws

Use **two #4 ×1/2 inch pan-head thread-forming screws intended for plastic**, modeled around **McMaster 92295A103**. This is not a pilot specification for an arbitrary #4 sheet-metal screw. The source listing specifies a 0.219 inch head diameter, 0.080 inch head height, Phillips #1 drive and a 37-gauge recommended drill. [McMaster source table](https://www.mcmaster.com/products/90380A108/).

| Feature | R08 dimension |
| --- | --- |
| Screw axes, world XY | (13, −29), (−13, 28) mm |
| Upper boss diameter | 8 mm |
| Printed pilot | 2.65 mm diameter, 12 mm blind depth |
| Pilot lead-in | 0.35 mm chamfer |
| Lid clearance hole | 3.4 mm diameter |
| Screw length under head | 12.7 mm |
| Nominal head envelope | 5.5626 mm diameter ×2.032 mm high |
| Screw tip / pilot bottom | Z17.3 / Z15.5 mm |
| Nominal tip clearance | 1.8 mm |

The old M3 nut pockets and clearance bores are filled before the new pilots are cut. No lid nuts are required. The `r08_pilot`, `r08_pilot_depth` and `r08_lid_clear` user parameters expose the fastening fit. Check the chosen screw in an actual printed boss before assembling the electronics; FDM hole size and thread-forming torque are not validated by CAD. The reference screw uses smooth nominal crest/head envelopes, not modeled threads; overlap of the crest with the pilot wall represents intended thread formation.

The two tube-clamp fasteners remain M4 ×30 with nuts. **The owner input currently lacks the upper-left clamp ear.** It is preserved exactly pending the owner's mounting decision; this revision does not silently restore or redesign the base.

## Evidence and files

- `input/owner-extended-R07-timeline-677.f3d`, `owner-layout.json`, `owner-input-view.png`: exact authoritative starting model and inspection evidence.
- `GoKart-Heltec-Recessed-Lid-R08.f3d`: final editable assembly.
- `stepped-lid` and `lower-collar`: STEP and millimetre STL exports that pass individual mesh checks.
- `case-recessed-sill.step`: the unchanged-base case geometry for review.
- `diagnostics/case-as-edited-NOT-PRINT-READY.stl`: non-manifold case export retained for diagnosis, **not printing**.
- `assembled-preview.png`, `open-sill-preview.png`, `lid-underside-preview.png`: assembled result, locating ledge and lower lid step.
- `build_lid_revision.py`: derives R08 from the archived owner input; does not regenerate the earlier case.
- `model-audit.json`, `independent-review.json`, `export-verification.json`: final geometry and export checks.

The owner's seven post-R07 features are retained: OffsetFaces1, Extrude25–28, Sketch1 and Chamfer1. These include the deeper base and lower chamfers. The archived input also captures any edits to earlier feature definitions. Final native geometry is authoritative.

Final recompute reports one retained-history warning at timeline607: `45deg front socket transition` in the hidden R07 case has a lost profile reference and uses cached geometry. It was not rebuilt or repaired over the owner’s edits. The current R08 bodies remain closed, connected solids; this history warning remains relevant if editing or regenerating the old R07 feature chain.

The known GPS receiver/rectangular OLED-cover proxy overlap remains an actual-fit check: approximately 0.0845 mm in Y and 0.3 mm in Z. The GPS socket retains 4.247 mm rear clearance; mating plugs and the internal 8 ×2 mm wire envelope remain unmeasured assumptions. See [R06](../r06-internal-harness/README.md) for the hardware sources and route. Preserve the GPS ceramic, clip and cable clearance when fitting.

This is an FDM prototype, not a tested weather seal or production clamp. Review overhangs in the slicer, screw/pilot fit, remaining clamp geometry, cable fit and clip movement before installation. Use unfilled PETG or ASA.
