# Compact Heltec/GPS bar enclosure — R03 prototype

**Four printed parts, four installation screws.** The 66 × 36 × 30 mm electronics
case runs parallel to the horizontal kart tube. The two-bolt collar is 50 mm wide,
so its ears extend 7 mm beyond each side of the case. Nominal bar diameter is the
owner's **0.995 in / 25.273 mm**; prototype bore is 25.523 mm with a 1.5 mm split gap.

The antenna insert is canted **15° from vertical toward the kart's outside**. Its
captured octagonal flange provides eight 45° rotation positions without another
screw. Open the lid to re-index it. Change cant by printing a replacement insert;
this is not an articulated swivel. The modeled short antenna is **50.8 mm from
mounting face to tip**; its 7 mm diameter is an illustrative envelope, not a
measured product. GPS remains sky-facing inside the lid.

## Files

- [Editable Fusion assembly](GoKart-Heltec-Compact-Parallel-R03.f3d), including the
  timeline, user parameters and separate non-printable hardware references.
- [Assembled preview](assembled-preview.png) and [exploded preview](exploded-preview.png).
- Each of `case-upper-collar`, `lower-collar`, `lid-gps-retainers` and
  `antenna-insert-15deg` has a STEP and a **millimetre STL**. Print one of each.
  Part exports use their local CAD coordinates; orient them in the slicer.
- [Model audit](model-audit.json), [independent export checks](export-verification.json),
  [export hashes](export-manifest.json),
  [construction source](build_model.py) and [export source](export_model.py).

The native assembly contains reference electronics, bar and antenna; these are
excluded from all four printable exports. Key sizes/angle/clearances are Fusion
parameters. Layout anchors and several retention details are script constants,
so arbitrary parameter changes are not automatically a validated new assembly.
The construction source expects a fresh named design with the two official STEP
references imported into components named exactly as shown in that source.

## Four-screw hardware and assembly

| Quantity | Item | Use |
| --- | --- | --- |
| 2 | M4 × 30 mm socket-head screws, measured under the head | Collar; 8 mm head pockets are 2 mm deep, so heads project below the clamp |
| 2 | M4 hex nuts | Slide into the two external collar channels before installing the lower half |
| 2 | M3 × 8 mm screws | Lid; check actual engagement and screw/head dimensions before tightening |
| 2 | M3 hex nuts | Two diagonal lid bosses, inserted before closing |
| Existing | SMA bulkhead nut/washer supplied with the pigtail | Connector retention, not another enclosure screw |

1. Test the lower collar and antenna insert first. Verify actual bar fit, screw/nut
   access and SMA thread length before printing the full case.
2. Slide the M4 nuts into the collar's external side channels. Clamp to the tube
   with the two M4 screws. Keep a remaining split gap; do not force the halves shut.
3. Seat the Heltec on its four PCB pads between the low edge stops. No stock PCB
   hole is enlarged. Lid posts capture the PCB/protective frame, not OLED glass.
4. Fit the GPS under the lid. Two snap hooks support its clear PCB edge strips;
   small upper stops capture the PCB rim. Do not force the ceramic antenna.
5. Install the SMA connector in the insert, choose its indexed direction, and
   route the coax/harness without loading the IPEX connector or trapping a wire.
   The USB-C plug enters from outside through the 13 × 7.5 mm access opening.
6. Insert the two M3 nuts, lower the lid and close with the two M3 screws. Confirm
   both boards are retained and cables are free before powering accessories.

## Dimension sources and fit limits

- Owner: horizontal 25.273 mm bar, ASA or PETG, compact case and four screws maximum.
- [Heltec official V4.3.1 STEP](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/3D/HTIT-WB32LAF_V4.3.1%281%29.step):
  actual PCB/connector geometry. The photographed board is V4.3, so exact revision
  interchangeability remains a fit check. The STEP omits the OLED cover and includes
  optional headers; headers are hidden, and a labeled cover envelope uses the
  [official V4.3.1 datasheet, page 15](https://resource.heltec.cn/download/WiFi_LoRa_32_V4/datasheet/WiFi_LoRa_32_V4.3.1_Datasheet.pdf)'s
  33 × 18.6 mm footprint and 5.5 mm height above PCB.
- [L76K accessory dimension photo](https://heltec.org/wp-content/uploads/2025/07/L76K_DIMENSION.png)
  gives 16.5 × 17.5 × 5.5 mm; [official GPS STEP](https://resource.heltec.cn/download/L76K/3D/GPS-Module1.STEP)
  differs (about 15.9 × 18.3 × 7.2 mm). Retention was checked against the latter's
  actual PCB and ceramic, not merely a block envelope. **Measure the owned module
  before printing the lid**; the thinner revision may need changed hook/stop heights.
- [Quectel antenna guidance](https://quectel.com/content/uploads/2024/04/Quectel_GNSS_Antenna_Application_Note_V1.0.pdf):
  patch faces the sky; this layout has 3.3 mm nominal roof air gap. Nearby support
  features have tighter clearances: final modeled ceramic-to-retainer minimum is
  **0.56 mm**. This is a physical fit-check limit, not guaranteed printed clearance;
  do not force or clamp the ceramic. Neither spacing nor 15° cant proves RF performance.

SMA hole 6.6 mm, panel thickness 2 mm, nut access 11 mm and antenna diameter are
unverified connector assumptions. Check the actual pigtail/antenna. The USB port
is about 6.2 mm behind the outer wall; confirm the actual plug overmould fits.
The supplied GPS harness is not modeled and its folded routing must be checked.
There is no gasket or weatherproof rating.

## Print and validation status

Use plain, unfilled ASA or PETG; no printer/shrink calibration has been supplied.
Start with fit pieces. Case printing needs support consideration: printing collar-down
leaves 21 mm floor overhangs at each end. Inspect the lid's snap hooks and SMA
counterbore in the slicer; no support-free claim is made. Avoid tightening hot or
soft printed collars and check retention after initial use; no structural rating
or tightening torque has been established.

Fusion checks found four single, connected solid printable bodies, correct
persisting board poses, no material electronics/body collision, coaxial 15° SMA
bores and a 50.8 mm antenna reference. The two imported timeline groups report no
feature error messages; they are not treated as failed modeling features. STL
triangle data and millimetre bounds were checked. These are CAD checks, not a
physical-fit, vibration, weather, GPS/radio or fleet commissioning acceptance.

Eamon's branch was checked through `c21baf8` before publishing; no enclosure CAD
or new mechanical measurements were tracked there. That final software-only
commit is not merged into this CAD milestone's `e77d19b` software base. His separate hood CAD and the canonical checkout's
untracked CH20 holder DXFs were untouched. No electronics, VESC settings or firmware
were changed by this CAD work. Earlier oversized prototypes were superseded and
are not part of these print exports.
