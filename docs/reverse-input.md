# Kart 3 reverse input — wiring investigation

Final owner clarification, November 10: **throttle on ADC1; reverse switch on TX**. Earlier
statements putting the switch on ADC1/ADC2 were corrected. Mechanical/plain-contact versus
powered electronic switch construction and the exact commercial ESC connector pinout are not yet
verified. No wire or input setting has been changed by the agent.

The complete USB capture reports `app_to_use=2` (ADC), `app_adc_conf.ctrl_type=3`
(Current Reverse Button) and `app_adc_conf.buttons=0` (no cruise/inversion bits).
ADC1 throttle calibration remains 0.69–2.67 V. This calibration is retained.

In pinned stock VESC 6.02 source, ADC starts with RX/TX as digital buttons:
[application selection](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app.c#L89-L112).
[ADC implementation](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/applications/app_adc.c#L249-L293)
reads reverse from RX and cruise from TX, active-low by default, with internal pull-ups.
Cruise is disabled by the captured button flags. Therefore TX wiring is a likely explanation
for an unresponsive reverse request; physical connector labeling/custom board differences still
need confirmation. ADC+UART uses a different button pin, so copying that baseline app selection
would not be a neutral tune change.

For a confirmed plain contact switch and verified connector labels, the intended ADC reverse
input is **RX to signal GND** (closed requests reverse, open requests forward). Power off before
changing wiring. A powered electronic switch needs its output level/type checked first; do not
assume its output is equivalent to a contact closure. Leave ADC1 throttle wiring and its calibration
unchanged. Keep direction switching hardwired to the VESC, independent of display/Heltec/radio.

Commission with wheels lifted: verify released-throttle behavior and switch state before a gentle
observed direction test. Do not request direction changes while rolling or with throttle applied.
If the correct input still behaves intermittently, inspect connector/ground integrity and switch
bounce; consider debounce and an explicit zero-throttle/near-zero-speed direction interlock as
separate work. No such interlock is claimed to be installed by this investigation.

The prepared tune trial changes motor settings only and preserves every application byte,
including this ADC mode. A tune change does not repair an incorrectly wired direction switch.
