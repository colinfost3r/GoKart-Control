# Reverse-input conditioner: prototype v1

**PROPOSED — not built, installed or validated.** This is a one-kart bench design for the owner-reported Flipsky 75100 Pro V2.0 and Nilight maintained SPST switch. Kart 3 currently uses **ADC / Current Reverse Button on RX**. No reverse wiring, app setting, motor/Hall detection or pedal calibration has changed.

The standalone circuit keeps throttle and direction local to the ESC. An optocoupler reads a stronger-current switch loop; a MAX6817 removes switch bounce before presenting active-low reverse to PPM/SERVO. It needs no Heltec, display, radio or software. See the [wiring diagram (SVG)](wiring.svg) and [PNG preview](wiring.png).

## Parts for one prototype

| Ref | Qty | Part / specification |
| --- | ---: | --- |
| U1 | 1 | LITE-ON LTV-817, through-hole DIP-4 photocoupler |
| U2 | 1 | MAX6817EUT+T, SOT-23-6 dual debouncer; [DigiKey 774085](https://www.digikey.com/en/products/detail/analog-devices-inc-maxim-integrated/MAX6817EUT-T/774085) |
| Adapter | 1 | [Proto-Advantage PA0085](https://www.proto-advantage.com/store/product_info.php?products_id=2200091), SOT-23-6, 0.95 mm pitch to DIP-6; choose the needed pin/assembly option |
| R1 | 1 | 390 Ω, ¼ W resistor |
| R2 | 1 | 100 Ω, ¼ W resistor |
| R3 | 1 | 10 kΩ, ¼ W resistor |
| D1 | 1 | 1N4148 diode, through-hole DO-35 |
| C1 | 1 | 100 nF ceramic, at least 10 V |
| C2 | 1 | 1 µF ceramic, at least 10 V |
| Assembly | 1 set | Soldered perfboard, headers, insulated enclosure, strain relief and connectors matching the actual ESC |
| Cable | As needed | Twisted pair for the two mechanical switch contacts |

Retain the existing switch; identify its mechanical contacts with an unpowered continuity check. Insulate the third, illumination terminal. Build **one** first; quantities multiply by eight only after acceptance. Prices and stock are not promised.

The [NOYITO B0B537T73S listing](https://www.amazon.com/dp/B0B537T73S), specifically its advertised 3–5 V variant, is only a sourcing candidate for an optocoupler module. It is **not a drop-in substitute and provides no established debounce**. Its exact resistors, polarity, terminals and output pull-up would need checking; the diagram uses the bare LTV-817 above.

## Connections

Mount the board beside the ESC. Use its **regulated 5 V, regulated 3.3 V and signal GND**; never connect 12 V, traction-battery voltage or the switch illumination terminal. Keep the long pair away from phase/power wiring. All listed grounds join ESC signal GND: this shared-ground arrangement is **not galvanically isolated**.

Pin numbers below are IC pin numbers, not assumed adapter/header numbering. Verify adapter continuity and chip orientation before power.

| Connection | Destination |
| --- | --- |
| ESC regulated 5 V | R1 390 Ω → U1 pin 1, LED anode |
| U1 pin 2, LED cathode | Cable → switch contact A |
| Switch contact B | Return cable → signal GND |
| D1, across U1 pins 1–2 | **Banded cathode to pin 1; unbanded anode to pin 2** (antiparallel) |
| U1 pin 3, emitter | Signal GND |
| U1 pin 4, collector | U2 pin 1, IN1 |
| U2 pin 2 | Signal GND |
| U2 pin 5, VCC; pin 3, unused IN2 | ESC regulated 3.3 V |
| U2 pin 4, unused OUT2 | Unconnected |
| U2 pin 6, OUT1 | R2 100 Ω → ESC PPM/SERVO **signal** |
| R3 10 kΩ | PPM signal side of R2 → ESC 3.3 V |
| C1 and C2, in parallel | U2 pin 5 → pin 2; place C1 directly beside U2 |

Replace the old RX switch/pull-up connection during installation; never parallel that wiring with this 5 V loop.

No external capacitor goes on the switch/input node. U2 already provides the qualification delay; this avoids the discharged-input-capacitor startup pulse of the earlier RC proposal.

## Behavior and limits

Switch open: optocoupler off, input/output high, forward. Switch closed: optocoupler on, input/output low, reverse after qualification. At nominal 5 V, R1 gives approximately 9–10 mA; this improves contact loading but does not establish the Nilight switch's minimum reliable load.

MAX6817 qualification is **20–80 ms, 50 ms typical**. Below its undervoltage threshold, debounce becomes transparent and follows the switch; it does not force forward or neutral. If 3.3 V precedes 5 V with the switch closed, forward can appear until the loop powers, then reverse qualifies. Open-loop startup has no intentional RC reverse pulse, but brownout behavior still requires measurement. [MAX datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX6816-MAX6818.pdf)

A broken cable, failed-open optocoupler LED or lost 5 V can select forward; a shorted switch loop can select reverse. There is no fault diagnosis, throttle/neutral interlock, battery-voltage fault rating or verified fleet reliability.

## Validation and later installation

1. Start with all ESC connections disconnected. Check shorts, diode orientation and switch continuity. Use current-limited regulated 5 V and 3.3 V bench supplies with a common GND; never parallel them with the ESC supply rails. Then verify U2 IN1 below 0.8 V closed and near 3.3 V open; check output polarity/delay with a scope or logic analyzer.
2. Repeat switch operations, connector movement and separate/together supply startup/shutdown. Check clean levels and unintended transitions; do not infer motor behavior from an LED indicator alone.
3. Only after electrical acceptance, arrange a separate wheels-up integration test with released pedal and accessible cutoff. PPM reverse requires **ADC and UART**, **Current Reverse Button**, and **servo output disabled**. Retain ADC1 pedal, Hall and motor calibration; capture/read back the app change. Moving the wire alone while still in ADC/RX mode will not work. [Pinned native input selection](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app.c#L116-L120)

The [LTV-817 datasheet](https://optoelectronics.liteon.com/upload/download/DS-70-96-0016/LTV-8X7%20series%20%20Rev.S.PDF) specifies saturation at different test currents; confirm the actual low voltage rather than treating typical calculations as acceptance.

## Heltec alternative: concept only

Optocoupler → Heltec software debounce → transistor pulling PPM low is possible; Core2 would remain display-only. A reboot can release that transistor and select forward, conflicting with the standing requirement that accessory loss never changes driving behavior. Resolving startup, brownout and a blocked software loop requires a dedicated design/task before implementation. It is not part of this standalone prototype.
