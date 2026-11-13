# Fixed kart-3 persistent RX filter

This procedure installs the reviewed filter only on kart 3's pinned controller
and exact settings. It is not a general Lisp uploader, firmware updater or
fleet-install procedure. It refuses any existing valid stored script, including
this filter, so it cannot be used to reinstall or update an installed copy.

The filter qualifies changes to the reverse input while leaving the physical
throttle, motor tune, Hall calibration and pedal calibration with the VESC.
Software filtering does not repair the switch circuit: a wrong electrical level
held long enough can still be accepted. Hardware diagnosis and vehicle acceptance
remain separate from successful code storage.

## Package and boundaries

The installer derives its package from the exact
[autostart source](../../firmware/vesc-lisp/reverse-input/rx-filter-autostart.lisp),
requiring source SHA-256
`30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700`.
Appending the code terminator and zero-import count yields a 3,984-byte blob,
SHA-256 `a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801`.
The complete stored image is 3,992 bytes, SHA-256
`428657a58bc6d4a2a0e85df858e36fc7d34972007d7df436ed236632a9a19495`.

The tool pins firmware 6.02 / `75_300_R2` / `no_hw_limits`, test version 0,
UUID `37004e000951343037353739`, and the complete reviewed motor/application
payloads. A mismatch requires review; the tool never adjusts settings to pass.

Only this code-storage operation is available. It does not send motor commands,
write application/motor settings, calibrate, reset the controller or activate
the script after writing. Erasing the Lisp sector does reset the Lisp runtime;
the firmware's flash helpers briefly inhibit/release motor output. Installation
is a stationary, supervised maintenance operation.

## Before applying

Read the current [handoff](../../HANDOFF.md) and retain fresh configuration and
[stored-code captures](../../tools/vesc/README.md#read-stored-lisp-code-without-executing-it).
`no_valid_blob` is not a bitwise backup of erased/blank flash. Close competing
VESC clients and pause the Heltec's VESC connection for reliable USB replies.

The driven wheels must be securely lifted, the pedal released, the original
intended switch branch connected and held in forward, and the operator beside
the physical cutoff. The installer requires RX=1, released-region ADC≤0.12,
|ERPM|≤50 and no fault. It also requires a successfully completed, reviewed
`rx_filter_control.py rollback` manifest with its raw app/motor readbacks.

If the RAM filter is active, use separate explicit **stop then rollback** steps
under the reviewed session procedure. **Stop only stops the filter worker and
holds its last direction; it is not a motor stop and does not restore raw RX.**
Rollback requires rest and the physical switch agreeing with that held direction.
Do not replace this sequence with a Lisp pause/reset or infer native attachment
from an empty context list. The native detach flag is not independently exposed.

## Commands

From the repository root, inspect the package and write plan offline first:

```sh
python3 -B tools/vesc/install_rx_filter.py
```

Applying is a separate explicit command. Substitute the confirmed device port,
the reviewed rollback evidence and a new output directory:

```sh
python3 -B tools/vesc/install_rx_filter.py \
  --apply --supervised \
  --port /dev/cu.usbmodemACTUAL_PORT \
  --rollback-manifest /absolute/path/to/rollback/manifest.json \
  --out /absolute/path/to/new/persistent-install
```

The tool repeats identity, all settings, released-input and empty-code checks.
Its final input/telemetry/empty-code checks share a bounded 750 ms window before
erase. It sends one erase, sixteen fixed body chunks, then the eight-byte header
last. It requires exact success/offset acknowledgements, reads the entire valid
blob back, and verifies every motor/application byte and identity afterward.
This ordering is not a power-loss atomicity guarantee.

Success requires `complete: true`, phase `stored_verified_not_activated`, the
expected `readback_sha256`, and `all_376_settings_preserved: true`. Keep the
manifest, raw reads, attempted TX/RX logs and exact image with the session evidence.
READ130 exposes the blob, not its header; header flags are not independently read
back. Flags are unused for startup in the pinned firmware.

Any uncertain send, missing ACK or mismatched readback stops the tool without
retry, activation, reset or automatic cleanup. Flash/runtime state may be partial.
Do not repeat the installer blindly; inspect the retained phase and raw evidence.

## Separate boot acceptance

The valid script runs on a later normal boot; a watchdog startup can suppress
Lisp execution. Native ADC control runs before Lisp, so raw RX determines direction
until the filter qualifies its input. Keep the pedal released until an active
worker and the correct applied direction have been verified. After successful
storage review, the operator separately performs the supervised physical power
cycle. The installer sends no SET_RUNNING command.

Capture status into a new directory after boot:

```sh
python3 -B tools/vesc/rx_filter_control.py status \
  --port /dev/cu.usbmodemACTUAL_PORT --out /absolute/path/to/new/boot-status
```

`complete` means the status capture succeeded, not that the filter is healthy.
Check run/active/applied state and positive matching worker-PID presence in the
context output. A missing PID in one snapshot is inconclusive; do not auto-start
or restart. Confirm the applied direction against the physical switch before any
separately authorized wheels-up throttle check. Record forward/reverse and boot
acceptance independently from code-storage success.

Stop/rollback only disables the current running filter. While its stored script
remains, a later normal reboot can start it again. Persistent removal requires a
separately reviewed maintenance procedure; this installer does not provide one.

Offline host regression command:

```sh
python3 -I -B -m unittest discover -s tests -p test_vesc_install_rx_filter.py -v
```

These tests use committed captured payloads and synthetic rollback manifests;
they never open hardware. Run the complete project test suite before publishing
changes to this tool. Pinned-interpreter boot tests are documented in the
[Lisp test guide](../../firmware/vesc-lisp/reverse-input/tests/README.md).
