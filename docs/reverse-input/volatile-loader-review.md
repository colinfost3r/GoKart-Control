# Fixed volatile RX-filter loader — offline review draft

This records review of the uncommissioned scratch prototype at
`/tmp/gokart-rx-filter-loader-20261111`. No loader code is included in this repository
or sent to a VESC. Physical short-harness isolation is the next hardware task.
The prototype is not an approved activation path; retain these findings before
writing a future portable loader.

## Fixed scope

- Exact candidate: `rx-filter-candidate.lisp`, **7,532 bytes**, SHA-256
  `25e2515fdeede0ce768a2d24a3e22aef413b2289d0dd5b63bd76ff07e05b0072`.
- Exact target: firmware **6.02**, UUID `37004e000951343037353739`.
- STREAM command **139**, `restart=0`, **59 sequential chunks**: 58 × 128 bytes
  and 108 final bytes. Total length is the exact file length; no NUL, marker or
  other source is appended. EOF is the stream writer close at that total.
- Allowed additional requests: identity 0, evaluator stats 134, and command 138
  with only the fixed `:ctxs` or read-only readiness expression.
- No start, stop, rollback, arbitrary REPL, reset, flash/configuration write,
  motor command or native-input operation is issued by the loader.
- Candidate source contains input-control operations inside function definitions;
  the exact reviewed top-level program defines those functions and globals only.

## Guards and evidence

Source length/hash and both explicit manual attestations are checked before opening
the serial port. The separate attestations cover runtime ownership and absence of
any previous candidate copy/C-side overrides. **Namespace absence is not machine
verified.** No verified bound?/defined? primitive was found in the pinned runtime.
An empty context snapshot cannot prove that globals or native overrides are absent.

A pinned identity, existing evaluator stats reply, and a complete empty context
snapshot are required before streaming. Every chunk gets exactly one write; the
next chunk is sent only after a CRC-valid **7-byte** ACK containing its exact offset
and result 0. Partial writes, timeouts, malformed/rejected/incorrect-offset ACKs,
queued control replies and receive limits abort without retry or cleanup.

After all ACKs, a single bounded expression reads the four lifecycle globals and
the closure tags of all six function definitions. It invokes none of the candidate
functions. The exact expected printed marker is:

```text
(gk-rx-load-ready nil nil -1 -1 closure closure closure closure closure closure)
```

This is a presence/disarmed-state check, **not function-body readback**, proof of
electrical reliability, or proof that the functions are safe to activate. Identity
is checked again after successful readiness. Any interrupted load may leave partial
definitions or evaluator changes. The tool does not attempt rollback or another load.

Each new output directory retains the exact source, manifest, identities, every
raw received byte (`rx-wire.bin`), attempted transmit frames (`tx-attempts.bin`),
and timestamped JSON wire events/CRC-valid payloads. Attempted transmit bytes are
not proof that every byte reached the controller. The host session is bounded to
180 seconds and received data to 128 KiB. Neither bound controls firmware recovery.

## Pinned source hazards

Reviewed [the pinned upstream STREAM handler](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif.c), locally saved as `/tmp/gokart-602-lispif-core.c`:

1. `restart=0` still initializes Lisp if it was not running. A stats reply is
   required first but is not an atomic guarantee against another client/reset.
2. Offset 0 can close an existing stream and pauses/GC/resumes the evaluator.
3. Streaming evaluates source; it is not a transactional RAM transfer. ACK=0 only
   means bytes entered the channel. The controller's "Stream done, starting..."
   message is not a successful-evaluation marker.
4. Several error/duplicate-offset branches send length 9 although only 7 response
   bytes were initialized. This draft rejects these replies; it never treats the
   extra two bytes as valid status data.
5. The firmware sets its channel-write timeout to 0 after any successful byte.
   If a later write hits a full buffer, decrementing from zero can run negative
   and miss the `== 0` exit. A host timeout cannot promise the firmware command
   thread has recovered. 128-byte chunks do not prove this hazard impossible.
6. Reloading the candidate resets lifecycle globals. Loading over an old active
   or stopped-but-detached copy could lose tracking of persistent C-side overrides.
   Manual absence review is mandatory; no automatic reload is provided.
7. Interruption has no automatic safe cleanup. Do not send reset/stop/rollback as
   an improvised recovery, and do not assume a failed host parse means no code ran.

## Offline checks

```sh
/Users/cofo/.platformio/penv/bin/python -I -B -m unittest discover \
  -s /tmp/gokart-rx-filter-loader-20261111 -p test_rx_filter_load.py -v
```

The initial **20 mock tests passed**. They exercise fixed source/chunk framing,
fragmented CRC ACKs, identity/refusal boundaries, partial sends, wrong ACKs,
bounded reception, raw logging, ACK-without-readiness failure and no activation.
Mocks do not establish MCU timing, buffer behavior, memory fit, or serial reliability.
The scratch tool imports existing reviewed packet/serial helpers from the project;
it is not yet packaged for another machine.
