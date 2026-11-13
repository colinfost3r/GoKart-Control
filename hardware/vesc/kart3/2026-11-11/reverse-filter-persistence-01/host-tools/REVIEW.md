# Fixed persistent RX filter installer — reviewed scratch artifact

No hardware or repository changes were made by this author. The root operator
owns all live actions and fresh physical readiness. Default execution prints an
offline plan; applying requires explicit `--apply --supervised`, port/output, and
the completed root-operated stop/rollback manifest. There is no activation option.

Frozen installer SHA-256:
`81e449b70d9b1cbd1e9d7617125850dc0b2e789bf7fc7e4ddee5f06127001b72`.
Frozen tests SHA-256:
`da948fc97dbfcf270f2247773453385658863c05c684d840e8af975be5fad89e`.
All **22 mock tests passed**, independently rerun by both protocol and lifecycle
reviewers against these exact hashes. Neither reviewer changed code or used hardware.

## Exact package and protocol

Audited firmware commit: `f7c2b34e1cff2234cae98be3abf0cd50e249558f`.
Target is UUID `37004e000951343037353739`, 6.02, `75_300_R2`, release test_version=0,
firmware_name=`no_hw_limits`. The exact full application and motor payloads are pinned:

- App: `2f666b2e9eb8130251b6ba3a6aea3da28f5416e3d3e3ec56883507f65abf185d`.
- Motor: `ab486bff0406bd7b84c0932160a4387e6862b7dee754ed38f4cc5dc7515a7b71`.

Source 3,981 bytes plus NUL and zero import count gives the fixed 3,984-byte code
blob `a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801`.
The 8-byte header is `00000f90af410000`: payload length, CRC16 over flags+payload,
then flags=0. Complete image: 3,992 bytes, SHA-256
`428657a58bc6d4a2a0e85df858e36fc7d34972007d7df436ed236632a9a19495`.

Requests are limited to fixed preflight reads, READ130, ERASE132 and WRITE131.
No SET_RUNNING133 exists. Erase is sent once; sixteen body chunks are written at
offsets 8..3848, followed by the exact full header once at offset 0. Every write
has a strict six-byte success/offset ACK; erase requires exactly `[132,1]`.
All chunks are ≤256 bytes, within the fixed image and 128 KiB sector bounds.
The exact header's partial byte prefixes were independently checked as invalid;
this does not make flash programming atomic or prove physical power-loss recovery.

## Preconditions and failure behavior

Successful stop/rollback evidence is mandatory. Repeated live checks require
run=false, active=false, PID=-1, applied=-1, raw RX=1, released-region ADC≤0.12,
|ERPM|≤50 and fault=0, with no reported Lisp contexts. The final 0.3-second status
capture, telemetry and empty-code read share a 750 ms window, checked again just
before the erase write. Native button-detach flags are not independently readable;
this depends on the root's verified rollback and exclusive supervised session.

Any existing valid stored code refuses installation. `no_valid_blob` is not a
bitwise backup of erased/blank flash. ERASE132 internally resets Lisp without
loading stored code, so stop and raw rollback must precede it. Firmware flash
helpers briefly inhibit/release motor output during programming. No application,
motor, Hall or pedal configuration write is sent by this installer.

After erase, no candidate-global/status expression is used. After writing, the
entire READ130 blob must exactly match the package; all 376 motor/app settings and
identity are read back unchanged. The header itself is not exposed by READ130;
the tool records that flags were not independently read back. Flags are unused
for normal startup in this pinned firmware: a valid stored script runs at normal
boot, except watchdog startup can suppress it.

All TX attempts, raw RX bytes, CRC-valid packets, source image, ACKs, readback and
phase/error manifests are retained. A partial/uncertain write, bad ACK, timeout,
changed settings or mismatched readback stops without retry, reset, cleanup or
activation. Firmware/runtime/flash may then be partial. The root must inspect
the evidence before deciding any recovery. First activation is a separately
supervised owner-controlled physical power cycle, followed by read-only acceptance.

## Offline reproduction

```sh
python3 -I -B -m unittest discover \
  -s /tmp/gokart-rx-filter-persist-20261111 -p test_install_rx_filter.py -v
python3 -B /tmp/gokart-rx-filter-persist-20261111/install_rx_filter.py
```

These are scratch paths. The prototype imports the previously reviewed scratch
lifecycle transport/helpers and immutable repository fixtures. It is not yet
packaged as a portable repository tool.
