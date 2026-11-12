# R09 — connected clamp ears, extended base preserved

R09 restores the missing left clamp ear and replaces the right ear's edge-only connection with **4 mm thick structural webs on both sides**. The owner's extended base is retained: this repair adds material and removes none. The recessed lid, GPS supports, internal wire route, antenna, board positions and lower collar stay unchanged.

This supersedes R08's non-print-ready case. R08 remains archived as the exact pre-repair evidence; use R09 for the repaired case geometry.

## Repair geometry

The left ear is an exact mirrored copy of the surviving right ear, including its bolt passage, captive-nut pocket, insertion slot and rounded outside corners. The original **±26 mm M4 bolt axes**, **52 mm bolt spacing** and **66 mm overall collar width** are restored.

Each web occupies **|X|14–18 mm, Y−12–12 mm, Z−16.25–0 mm**. The resulting 4 ×24 ×16.25 mm connection joins the ear to the case floor across a finite area. The webs sit within the extended case's existing outside envelope. Their inner faces at |X|14 mm leave 1.2385 mm beyond the nominal 12.7615 mm bore radius; the 25.273 mm tube, 25.523 mm bore and 1.5 mm clamp split are retained.

The repair adds 3.120 cm³ of web material plus 5.3451 cm³ for the mirrored ear. A Boolean comparison found **zero removed volume** from the original owner case. The lid and lower collar are copied unchanged. Every edge of each current printed part has two native coedges; a periodic seam may have one unique face but still has its valid pair of coedges. Independent review also found zero overlap with a 200 mm long nominal tube, a 0.125 mm minimum radial tube gap, the retained 1.5 mm split, clear M4 bolt axes and 2 mm clearance for the 12 mm driver corridors above the ears. All three STL meshes pass closed-manifold, consistent-winding and single-component checks; see `export-verification.json`.

## Fasteners and printing

- Lid: **two #4 ×1/2 inch pan-head thread-forming screws for plastic, McMaster 92295A103**. The chosen prototype pilot is 2.65 mm diameter ×12 mm deep, with 3.4 mm lid clearance and 1.8 mm nominal tip clearance. This is not a generic sheet-metal-screw pilot. [Supplier specification](https://www.mcmaster.com/products/90380A108/).
- Clamp: **two M4 ×30 socket-head screws and two M4 nuts**. Insert the nuts from the outside ends of the ears.

There remain three printed parts and four installation screws. The lid retains its 1.5 mm recessed locating edge, 0.3 mm side clearance, 0.5 mm entry chamfer and approximately 1 mm perimeter bearing. See [R08's lid specification](../r08-recessed-lid/README.md) for its detailed dimensions; its old clamp warning is resolved by this revision.

Use unfilled PETG or ASA. Review support placement around the clamp/case overhangs in the slicer. Prototype the screw/pilot fit, check the actual tube and nut insertion, and confirm grip before installing the electronics. Manifold geometry does not establish printed strength, vibration endurance or safe clamping torque.

## Files and evidence

- `GoKart-Heltec-Connected-Clamp-R09.f3d`: editable final native assembly with owner history retained.
- `case-connected-clamp`, `recessed-lid`, `lower-collar`: STEP and millimetre STL parts.
- `assembled-preview.png`, `clamp-webs-underside-preview.png`, `open-case-preview.png`: assembled result and repair/support details.
- `input/current-R08-before-R09.f3d`, `owner-layout.json`, `input-view.png`: exact live model captured before repair; no intervening owner edits were found.
- `repair-audit.json`, `model-audit.json`, `independent-review.json`, `export-verification.json`: material preservation, geometry and export evidence.
- `capture_input.py`, `build_clamp_repair.py`, `make_previews.py`, `export_revision.py`: derive and export this repair from its archived input. Do not regenerate older revisions over owner edits.

The retained historical R07 feature `45deg front socket transition` at timeline607 reports a lost-profile/cached-geometry warning. That old feature was not rebuilt. Current R09 print bodies are separate copies with the authorized additive repair, and the native/history warning remains documented.

Physical-fit limits remain: the GPS receiver slightly overlaps the conservative rectangular OLED-cover proxy (0.0845 mm in Y and 0.3 mm in Z), and the mating plugs, wire bundle and bend radius are unmeasured. The 4.247 mm bare-GPS-socket rear gap and internal harness envelopes are retained. Check actual module/cover, cable, clip and screw fit without forcing them. Weather sealing and radio/GPS performance are not established by the CAD checks.
