#!/usr/bin/env python3
"""Trace VESC telemetry over USB for a supervised pedal check; read commands only.

Sends COMM_FW_VERSION (0) once to require the stated controller UUID, then COMM_GET_VALUES (4)
at a fixed rate. Both are in capture.py's read allowlist, which is the only way this tool can
build a frame: it cannot send a write, motor, reset, Lisp or configuration command. The
controller stays in charge of the driver inputs. One JSON line is appended per sample.
"""
import argparse
import json
from pathlib import Path
import re
import time

from apply_tune import SerialConnection
from capture import verified_identity
from decode import decode_telemetry

KEYS = ('erpm', 'duty', 'motor_current_a', 'battery_current_a', 'input_voltage_v', 'fault_code',
        'mosfet_temp_c', 'tachometer', 'timeout_active', 'kill_switch_active')
MAX_SECONDS = 900.0


def trace(connection, expected_uuid, log, seconds, hz=10.0, clock=time, sleep=time.sleep):
    """Run on an already-open connection. Returns the number of telemetry samples written."""
    if not isinstance(expected_uuid, str) or not re.fullmatch(r'[0-9a-f]{24}', expected_uuid):
        raise ValueError('Expected a 24-hex-digit lowercase controller UUID')
    if not 0 < seconds <= MAX_SECONDS or not 1 <= hz <= 20:
        raise ValueError('Trace length must be 0..900 s and rate 1..20 Hz')
    identity = verified_identity(connection.query(0))
    if identity.get('uuid') != expected_uuid:
        raise ValueError('Controller UUID is not the stated one; nothing traced')
    log.write(json.dumps({'t': clock.time(), 'event': 'start', 'uuid': identity['uuid'],
                          'firmware': identity['firmware'], 'commands': [0, 4]}) + '\n')
    start, count = clock.monotonic(), 0
    while clock.monotonic() - start < seconds:
        tick = clock.monotonic()
        values = decode_telemetry(connection.query(4))
        log.write(json.dumps(dict({'t': round(clock.time(), 3)}, **{k: values.get(k) for k in KEYS})) + '\n')
        count += 1
        sleep(max(0.0, 1.0 / hz - (clock.monotonic() - tick)))
    log.write(json.dumps({'t': clock.time(), 'event': 'end', 'samples': count}) + '\n')
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', required=True, help='Explicit VESC USB serial port; close other serial clients first')
    parser.add_argument('--expected-uuid', required=True, help='UUID of the physically identified controller')
    parser.add_argument('--out', type=Path, required=True, help='JSON-lines file; appended to, so reruns keep earlier traces')
    parser.add_argument('--seconds', type=float, default=120.0)
    parser.add_argument('--hz', type=float, default=10.0)
    args = parser.parse_args(argv)
    with SerialConnection(args.port) as connection, open(args.out, 'a', buffering=1) as log:
        count = trace(connection, args.expected_uuid.lower(), log, args.seconds, args.hz)
    print(f'{count} telemetry samples appended to {args.out}; read commands 0 and 4 only.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
