# Hardware inventory and evidence

| Item | Current information | Evidence status |
| --- | --- | --- |
| Kart count | Eight target; 1–3 development karts | Owner confirmed |
| Kart computer | Raspberry Pi 3 Model B V1.2 | Board silkscreen in photo 5; OS/runtime not inspected |
| Pit computer | Raspberry Pi 4 | Owner selected; not configured |
| VESC | Firmware 6.00, `75_100_V2`, `no_hw_limits`, controller ID 69 | USB read on one baseline kart |
| Commercial controller model | Fleet reported as Flipsky 75100; kart 3 specifically 75100 Pro V2.0 | Owner confirmed November 10; physical harness orientation still needs checking |
| VESC USB | Accessible, read successfully on Mac | Verified |
| VESC BLE | Preferred existing link; original code uses Nordic UART Service | Owner report + historical code; Heltec link/module identity unverified |
| Driver input | ADC and UART / Current Reverse Button | Configuration verified; physical wiring owner reported |
| Brakes | Mechanical pedal; motor braking limit 0 A | Owner report + runtime configuration |
| Motor temperature | No sensors wired; kart 3 initially NTC, corrected to Disabled in the Nov 10 tune | Owner confirmed; complete before/after readback |
| Motor sensing | FOC / Hall Sensors | Configuration; separate from temperature sensing |
| Motor model/rating | Unknown | Required for tuning |
| Battery | 72 V nominal / 84 V full; sampled 76.4 V | Nominal/full owner report; sample verified |
| Battery metadata | 20 cells, 20 Ah | Configured values, not battery/BMS rating verification |
| Battery/BMS rating | Unknown | Configured VESC BMS type is not proof of a connected BMS |
| Display | LESOWN L7 family, 7-inch IPS, 1024×600; HDMI video and USB-HID touch | Supplied guide Rev 2.1 + connector photos; exact suffix and live mode/touch still unverified |
| Heltec | HTIT-WB32LAF V4.3; packaging lists HF 863–928 | Photo-identified board; installed firmware and RF settings unverified |
| GPS | Quectel L76K with ceramic patch antenna, cabled to Heltec | Module marking and antenna visible; fix/serial operation untested |
| Base-station radio | LoRa attached to pit Pi 4 | Model/inventory pending |
| Pi/display/Heltec power | Regulated supply details unknown; Heltec must survive display power loss | Independent supply, USB backfeed and reset behavior need validation |
| Network | Pi 3 B has Wi-Fi/BLE and Ethernet; pit accessible locally | Board capability verified; site network not configured |
| Course imagery | Owner imagery or public CT ECO | No imagery/route selected or downloaded |

See the [photo evidence and connector guide](../hardware/photos/2026-11-05/README.md).
The supplied booklet says **L7 User Guide Rev 2.1**; the earlier LV marking was
a transcription, not an established PCB revision. Use **5V IN + TOUCH** for USB
touch data; the adjacent 5V IN connector is power-only.

Do not assign the captured controller to race kart 1 or assume controller ID 69
is a fleet-wide convention. Commission kart IDs and controller identities explicitly.
The controller's configured multi-ESC flag does not establish the physical CAN topology.

References: [Pi 3 B](https://www.raspberrypi.com/products/raspberry-pi-3-model-b/),
[Heltec V4](https://heltec.org/project/wifi-lora-32-v4/),
[CT ECO imagery](https://maps.cteco.uconn.edu/data/flight2023/).

## M5 v1.5 option (2026-11-09)

Owner confirmed M5Stack Core2 v1.3 / K010-V13 (320x240) on 2026-11-09
([product](https://shop.m5stack.com/products/m5stack-core2-esp32-iot-development-kit-v1-3)). Proposed wiring is Core2 PORT.A G33 RX to Heltec G47
TX, G32 TX to Heltec G48 RX, shared ground, 3.3 V UART logic at 230400 baud. Exact unit/pinout,
power supply/backfeed and sustained UART load are not yet checked. Keep Heltec power independent
of the display. [M5 wiring/build guide](../firmware/m5-core2/README.md). No hardware was changed.


## Kart 3 controller identity — observed 2026-11-10

This M5 v1.5 development kart is a different controller from the original captured baseline:
VESC **75_300_R2 / firmware 6.02**, Bluetooth **f7:bd:23:cc:62:0e**, UUID
**37004e000951343037353739**. The Heltec is fleet ID 3, with both pins saved/read back.
The old d8:94:35:be:e5:32 / 2c004c000951343037353739 pairing belongs to kart 2 per Eamon's
`fc7e610`; do not copy it to another kart. Read-only telemetry reached the Core2 and the owner
confirmed live readings. [Evidence and capture limitations](../hardware/m5/2026-11-10-kart3/README.md).


The replacement USB cable worked on November 10 at 19:28 UTC. All **189 motor + 187 app settings**
were captured from kart 3, with four CRC-valid replies: [complete evidence](../hardware/vesc/kart3/2026-11-10/usb-before-tune/README.md).
There are 40 motor and 10 app differences from the November 5 reference. At capture: 82.1 V,
0 ERPM/current, fault 0, ESC 19.1 C. The raw motor-temperature value (-95.4 C) is invalid for use:
the sensor is unwired despite the controller still being configured for NTC. This capture changes
no settings and is runtime evidence, not a saved-flash image. See the [all-settings review](kart3-tune-comparison.md).

The later [12-setting trial](../hardware/vesc/kart3/2026-11-10/tune-applied-v1/README.md) was applied at 19:58:55 UTC and fully read back. Sensor selection is now Disabled; input calibration/configuration stayed unchanged.

## Reverse switch and proposed interface — 2026-11-10

Owner identifies the Nilight three-terminal maintained SPST toggle and confirms the LED is
not used. Existing reverse is on RX with an approximately 10 kΩ pull-up to 3.3 V; throttle is
on ADC1. Intermittence predates the tune and spans eight karts/two switch types. No cause has
been measured. See [reverse investigation](reverse-input.md) and the separate
[proposed conditioner BOM/diagram](reverse-input/prototype-v1/README.md). No reverse hardware
or app change is installed. The Heltec alternative remains a concept with unresolved reset
behavior, not a change to the vehicle reliability requirement.
