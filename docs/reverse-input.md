# Kart 3 reverse input — wiring investigation

Latest owner correction, November 10: **throttle ADC1; reverse switch RX**. The switch is a
maintained mechanical switch connected to VESC signal GND. The owner added an external pull-up
from **RX to 3.3 V, believed to be 10 kΩ** to get it working, but reverse remains intermittent
even when the wheels are fully stopped and the pedal is released before selection. The owner
confirms it was **already intermittent before the November 10 tune**; that tune did not introduce
the original fault. Resistor placement, measured voltage levels and exact physical connector
pinout are not yet verified.
Earlier statements putting reverse on TX or ADC1/ADC2 are superseded. No wiring or input setting
was changed by the agent.

The latest complete USB readback reports `app_to_use=2` (ADC), `app_adc_conf.ctrl_type=3`
(Current Reverse Button), `app_adc_conf.buttons=0` (no cruise/inversion bits), regular safe start,
and ADC1 throttle calibration 0.69–2.67 V. Every application byte was preserved by the tune trial.
[Readback](../hardware/vesc/kart3/2026-11-10/tune-applied-v1/decoded-after/app_configuration.json).

Pinned stock VESC 6.02 [application selection](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app.c#L89-L112)
starts ADC with RX/TX as digital buttons. The [ADC implementation](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c#L63-L70)
enables internal pull-ups. It [reads reverse on RX and cruise on TX](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c#L249-L293),
active-low with these flags. Cruise is disabled. Reverse follows the switch level; it is not a
toggle latched by a momentary pulse. ADC+UART uses a different button pin and would change this setup.

For this stock 75_300_R2 definition, COMM RX is **PB11** while permanent NRF51/BLE UART uses
**PC11/PC10**. `permanent_uart_enabled=1` therefore does not seize the reverse input; do not
disable it on this evidence. [Pinned pin definitions](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/hwconf/trampa/75_300/hw_75_300_core.h#L185-L201).

## Physical hardware and conditioner proposal — November 10

The owner reports the issue across **all eight karts and two switch types**. All controllers
are reported as Flipsky 75100; kart 3 is specifically **75100 Pro V2.0**. Its reported firmware
name `75_300_R2` is not by itself evidence of a wrong target: [Flipsky documents this shared
75-series target](https://flipsky.net/blogs/vesc-tool/tips-of-75-serise-esc). The Pro V2 has phase
filters according to its [manufacturer page](https://flipsky.net/products/flipsky-75100-pro-v2-0-with-aluminum-pcb-based-on-vesc-for-electric-skateboard-electric-scooter-ebike-speed-controller).
Do not change phase-filter settings based on the non-Pro model's instructions.

The supplied [Nilight maintained, illuminated SPST toggle](https://www.nilight.com/products/3pcs-blue-led-toggle-switches-12v-20a-3-pin-2-position-on-off-spst-heavy-duty-rocker-switch-for-auto-car-marine-rv-vehicles-truck-boat-dash)
is used **without its LED**, owner confirmed. Treat only its verified mechanical contact pair
as the switch; insulate the separate illumination terminal. The LED is therefore not an
established load on the existing input. No minimum reliable contact current was found in the
manufacturer information. Better behavior on short wires, if demonstrated, would support a
harness/noise investigation; it does not establish a measured cause here.

[Prototype parts list and wiring diagram](reverse-input/prototype-v1/README.md) document an
ESC-powered optocoupler loop plus MAX6817 debounce feeding **PPM/SERVO**. This is proposed,
not built or installed. It retains hardwired driver control and adds no Heltec/radio dependency.
The official [Flipsky connector drawing](https://cdn.shopify.com/s/files/1/0011/4039/1996/files/f4b3da9554de4e60ffd11b8edcb16ff8_1ad0544c-6ae8-4a5f-a8fc-43eb7fabd23d_1024x1024.jpg?v=1713419744)
labels PPM connector 3 as SERVO/5V/GND and COMM connector 6 with 3.3V/5V/GND among its pins;
physical orientation must be checked on the actual unit. PPM's 5 V power pin is not its signal.

Native `ADC and UART` starts ADC with `use_rx_tx=false`, moving the active-low reverse button
to the hardware ICU/PPM input; retain `Current Reverse Button`, no inversion and servo output
OFF. The November 5 baseline already uses that application, while kart 3 remains ADC/RX.
[Application source](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app.c),
[button source](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c).
Changing the pin alone is not a proven cure. Preserve Hall/pedal calibration and verify the
app change separately after the conditioner passes electrical testing.

The owner also asked about using the always-powered Core2/Heltec and easier Amazon modules.
A Heltec input/debounce/transistor version is possible, with Core2 display-only, but is not
approved or implemented. Its output can release on reboot and change a held reverse request
to forward. That conflicts with the standing accessory-loss requirement. Existing BLE/GPS work
can block the main loop, so direction logic would require its own bounded task; adding a poll
in `loop()` is insufficient. A generic optocoupler module alone does not provide debounce.

## Zero-braking-limit hypothesis — not a diagnosis

The tune changed `l_current_min` from -50 A to 0 A to match the no-motor-braking intent.
`cc_min_current` remains 0.05 A. Stock source shows a plausible direction-transition interaction:

- A negative relative-current request still scales by the positive motoring allowance;
  zero braking does **not** simply disable all reverse. [Relative current](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mc_interface.c#L713-L719).
- Runtime braking-side current is floored to `-cc_min_current`, approximately -0.05 A here.
  [Limit calculation](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mc_interface.c#L2406-L2415).
- When filtered q-axis modulation is positive, negative current is clamped to that braking-side
  allowance. Once modulation is nonpositive, the opposite motoring limit is available.
  [FOC limiter](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L3065-L3084).
- The undriven motor continues feeding measured q-axis voltage into the filter. Zero ERPM does
  not prove zero filtered modulation; its sign has **not been measured on this kart**.
  [Undriven path](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/motor/mcpwm_foc.c#L3191-L3220).

This can restrict reverse torque during a transition, but does not establish a sustained failure:
the current controller may change the modulation sign quickly. The owner confirms the symptom
**predates the tune**, so the newly introduced zero-braking limit does not explain the original
failure. It could still affect present behavior; retain that as a secondary hypothesis. Prioritize
RX signal quality and controller/fault/ADC telemetry before attributing the fault to wiring or limits. A supervised, bounded comparison
with a nonzero braking allowance would be a **separate proposed tune test**, requiring explicit
scope and preserving the no-regen design intent for review. No such change/test has been made.

## Next diagnostic and design choice

Keep reverse hardwired to the VESC and leave pedal calibration intact. RX-to-signal-GND is the
expected contact arrangement: closed selects reverse, open selects forward. Approximately 10 kΩ
to 3.3 V is a plausible pull-up, not proof of a stable signal. Do not raise its supply voltage.
The report does not yet isolate a bad contact, poor ground, noise, connector mapping or VESC input problem.

1. With the kart secured, wheels lifted and pedal released, measure RX relative to VESC signal GND:
   forward should be pulled high near 3.3 V and reverse held near 0 V. Check for instability while
   gently moving the switch and harness. A meter can miss fast glitches; a scope can distinguish them.
2. With power removed, inspect connector crimps and check switch/harness continuity in both positions.
   If needed, isolate the switch/harness from the input using a short known-good local contact during
   a supervised wheels-up check. Configure the test with power off; do not bridge unidentified pins.
3. If RX is unstable, repair the contact/ground/harness first. Use a maintained switch suitable for
   low-current signals, route RX and signal GND together away from phase/power wiring, and locate the
   pull-up near the VESC. Consider filtering/debounce only after measuring noise and checking input limits.
4. If RX stays solidly low during a failed reverse request from rest, inspect controller input mapping,
   faults and actual application behavior before changing ADC mode or adding a different controller.

No filter values, alternative pin, software latch or direction interlock have been commissioned.
A future VESC-local debounce/interlock could remain independent of Heltec/display connectivity, but
is separate design work. Selecting reverse while rolling is not a test of this intermittent-from-rest
failure; motor braking is configured to zero. Do direction checks only from rest with throttle released.
