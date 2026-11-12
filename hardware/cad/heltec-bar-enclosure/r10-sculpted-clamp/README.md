# R10 — top Allen screws and sculpted clamp details

R10 keeps the complete lower clamp and adds **subtle machined-bike styling**: beveled ear shoulders, a beveled lower perimeter and flowing inner web-root transitions. The two M4 socket heads now sit fully recessed **on top**, with captive plain hex nuts **underneath**. The owner's extended base, recessed lid, tube fit, clamp split, board/GPS/antenna positions and internal wire route are preserved.

The live R09 model was inspected and archived first. Its lower clamp was already present and visible; this revision retains its functional shape and shows it clearly in assembled, underside and separated views. It does not roll back the owner's lower-clamp geometry.

## M4 clamp fasteners

Use **two M4 ×30 ISO4762 / DIN912 socket-head cap screws**, with **3 mm Allen drive**, plus **two plain DIN934 M4 hex nuts**. The modeled head is 7 mm diameter ×4 mm high; the nut is 7 mm across flats ×3.2 mm high. These traps are for plain nuts, not tall or nyloc nuts.

| Feature | Dimension |
| --- | --- |
| Screw axes | X±26 mm, Y0; 52 mm spacing |
| Top counterbore | Ø8.2 ×4.5 mm deep |
| Counterbore entrance | 0.5 mm chamfer |
| Shaft clearance | Ø4.5 mm |
| Bottom nut trap | 7.3 mm across flats ×3.4 mm deep |
| Nut-trap entrance | 0.3 mm chamfer |
| Head bearing / head top | Z−4.5 / Z−0.5 mm |
| Nut bearing / nut bottom | Z−30.6 / Z−33.8 mm |
| Screw tip | Z−34.5 mm: 0.5 mm below the lower face, 0.7 mm beyond the nut |

The old upper nut pockets and side slots, and the old lower head recesses, were filled before the new features were cut. There are no intentionally retained obsolete fastening cavities. Insert nuts from below and tighten the Allen screws from above. Actual fastener and FDM fit still require a physical check.

Primary dimensional sources: [Accu socket-head specification](https://accu-components.com/api/product-datasheet?id=2828), [Accu ISO/DIN head dimensions](https://www.accu.co.uk/api/product-datasheet?id=151797), and [Accu plain DIN934 M4 nut listing](https://www.diy.com/departments/m4-hexagon-nuts-din-934-stainless-steel-a2-pack-of-200-accu/5054328003347_BQ.prd).

The lid still uses **two #4 ×1/2 inch plastic thread-forming screws, McMaster92295A103**. Its 2.65 mm pilots, 3.4 mm lid clearance and recessed locating sill are unchanged. Total installation screw count remains four.

## Exterior shaping and protected geometry

The visual reference is the [Hope Gravity stem](https://www.hopetech.com/products/controls/stems/gravity-stem/): distinct flat fastener pads, clean bevels and rounded transitions. This is a restrained geometric treatment for an FDM enclosure, with no logos, simulated anodizing or decorative weight-relief pockets.

- **1.0 mm bevels** follow the upper ears' exposed top outer perimeter. Flat screw-bearing regions and the clamp split faces remain intact.
- **1.0 mm bevels** follow the lower clamp's exterior bottom perimeter, away from the tube surface and nut seats.
- **1.5 mm concave fillets** add material at the two inner web-to-floor roots. They retain the full 4 mm web sections and stay clear of the tube.

`sculpt-audit.json` records the exact selected edge bounds. The main case above Z0, lid/sill, tube-contact surfaces, 1.5 mm split, ±26 mm axes and hardware positions are protected. The 25.273 mm tube retains 0.125 mm nominal radial clearance in the 25.523 mm bore; driver access remains 2 mm clear for the 12 mm reference tool corridor.

## Files and review

- `GoKart-Heltec-Sculpted-Clamp-R10.f3d`: editable complete assembly and retained owner history.
- `case-sculpted-clamp`, `recessed-lid`, `lower-sculpted-clamp`: STEP and millimetre STL parts.
- `assembled-preview.png`: top Allen heads seated below the ear surfaces.
- `bottom-nut-pockets-preview.png` and `bottom-nuts-installed-preview.png`: underside access and nominal nuts.
- `web-root-transitions-preview.png`: additive internal fillets and beveled shoulders.
- `separated-bottom-clamp-preview.png`: lower clamp and nuts translated 20 mm only for the view; exact assembled transforms are restored before export.
- `input/current-R09-before-R10.f3d`, `owner-layout.json`, `input-view.png`: exact pre-edit model evidence.
- `sculpt-audit.json`, `model-audit.json`, `preview-state-audit.json`, `independent-review.json`, `export-verification.json`: dimensions, protected geometry, restored view state and export checks.

The historical R07 `45deg front socket transition` feature at timeline607 retains its cached-profile warning. It was not rebuilt over the owner's edits. All three current printable bodies are single solids with two coedges per edge, and their STL meshes pass closed-manifold, consistent-winding and single-component checks.

Use unfilled ASA or PETG and review print orientation/supports in the slicer. Screw/pilot fit, clamping torque, grip, vibration strength, clip motion, sealing and radio/GPS performance remain physical tests. The inherited GPS-to-conservative-OLED-cover proxy overlap and unmeasured plug/harness allowances remain documented in [R09](../r09-clamp-repair/README.md). The nominal fastener references omit real threads and are not printable parts.
