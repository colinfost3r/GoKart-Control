# Kart 3 guarded autostart artifact — supervised persistent trial

Prepared offline on November 11, 2026. **Not written to a controller by this preparation.**
This adds one guarded automatic startup call to the exact filter already exercised in RAM.
It is not a production or fleet reliability claim.

`rx-filter-autostart.lisp` starts with the byte-identical 3,732-byte compact candidate
`d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc`. The appended expression
requires the kart-3 UUID, firmware `(6 2 0)`, ADC application2 and control type3, then calls
`gk-rx-filter-start` once and prints its result. There is no retry loop or forced initial
direction, and no change to debounce, pedal/RPM/fault qualification, held-state stop or rollback.

The canonical `rx-filter-autostart-code.bin` is source + one NUL + big-endian uint16 zero
import count, matching VESC Tool6.02 packing. It excludes the separate eight-byte flash
size/CRC/flags header. `manifest.json` records both hashes and all14 pinned-interpreter tests;
`prepare.py` reproduces the artifacts and tests using the local pinned source fixture.

The firmware automatically evaluates valid stored Lisp on a normal boot; header flags do
not select autostart in stock6.02. Watchdog recovery can suppress Lisp startup. The native ADC
application starts before Lisp, and raw RX remains in charge until the worker qualifies and
attaches its override. The existing500ms ADC safe-start does not guarantee filter-first
startup because main already waits500ms before starting Lisp. Chatter, motion, a pressed pedal
or failure can prevent qualification indefinitely. **Keep the pedal released until active,
worker presence and the correct applied direction have been verified after each supervised
cold boot.** No automatic startup drive interlock has been added.

Only app/control type are available to the runtime configuration guard. The complete app
hash, buttons=0, servo output off, native deadband0.15, safe-start, unchanged pedal calibration
and exclusive input ownership remain installation/maintenance prerequisites; this wrapper
does not verify those fields anew on every boot.

A failed or paused worker can leave the last C-side direction override held while the wired
pedal remains usable. `stop` is not motor stop or raw-input restoration. Stored-code erase
alone does not prove removal of that live override; use the separately reviewed joined-stop
and matching-RX stationary rollback, or a controlled whole-controller power cycle after
stored-code removal. Do not reload/redefine this artifact over the active RAM copy or use a
Lisp restart as cleanup. Normal boots with this valid stored source will start it again.

Before treating persistent startup as accepted, separately verify cold boots with the
physical switch held forward and held reverse, released pedal, correct positive worker/state
proof and unchanged376 configuration fields. Verify the removal path and Heltec coexistence
separately. Do not induce a watchdog reset as an ad hoc test. The successful RAM motor trials
do not substitute for these startup/removal checks.
