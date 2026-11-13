#!/usr/bin/env python3
"""Read the fault log a UUID-pinned VESC 6.02 has kept since it was powered. Read-only.

Exactly two requests are sent: the identity read (command 0) and the fixed terminal command
`faults` (COMM_TERMINAL_CMD, 20), which prints each fault registered since start with the
current, voltage, duty and speed at that moment. Nothing is cleared, changed, started or
stopped, and no other terminal command can be built by this tool.

The log lives in RAM: a power cycle erases it, so read it before one. Keep every other client
(the kart's Heltec included) off the controller: 6.02 sends printed text to the interface that
spoke last, and the reply would go there instead.

  python3 tools/vesc/read_faults.py --port /dev/cu.usbmodemXXXX \\
    --expected-uuid <24 hex digits> --out /path/to/new-directory

Protocol source: vedderb/bldc release 6.02: datatypes.h (COMM_TERMINAL_CMD=20, COMM_PRINT=21),
terminal.c (`faults`).
"""
import argparse
import binascii
import json
import os
from pathlib import Path
import re
import select
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import MAX_PAYLOAD, PacketParser, receive
from read_lisp import SerialConnection, expected_uuid, query_frame, require_identity, sha256, utc_now

TERMINAL_CMD, PRINT = 20, 21
FAULTS_PAYLOAD = bytes((TERMINAL_CMD,)) + b'faults'     # the only terminal command this tool can send
QUIET_SECONDS, LIMIT_SECONDS = 0.6, 4.0


def faults_frame():
    payload = FAULTS_PAYLOAD
    return bytes((2, len(payload))) + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


def collect_prints(fd, clock=time.monotonic):
    """Printed lines until the controller has been quiet for a moment; bounded in time."""
    parser, lines = PacketParser(), []
    started = last = clock()
    while clock() - started < LIMIT_SECONDS and clock() - last < QUIET_SECONDS:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            continue
        try:
            chunk = os.read(fd, MAX_PAYLOAD)
        except BlockingIOError:
            continue
        for payload in parser.feed(chunk):
            if payload and payload[0] == PRINT:
                lines.append(payload[1:].rstrip(b'\0').decode('utf-8', errors='replace'))
                last = clock()
    return lines


def summarise(lines):
    """Fault names in the order printed, and whether the controller said there were none."""
    text = '\n'.join(lines)
    names = re.findall(r'^Fault\s*:\s*(\S+)', text, re.M)
    counts = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    return {'answered': bool(lines), 'fault_count': len(names), 'faults_by_name': counts,
            'reported_none': bool(re.search(r'No faults registered', text, re.I))}


def read(port, out, uuid, connection_factory=SerialConnection):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'started_at_utc': utc_now(), 'port': port, 'expected_uuid': uuid, 'complete': False,
                'requests_sent': [], 'scope': 'faults since this power-up only; nothing was cleared or changed'}
    try:
        with connection_factory(port) as connection:
            frame = query_frame(0)
            manifest['requests_sent'].append('identity')
            if os.write(connection.fd, frame) != len(frame):
                raise IOError('Partial identity request; nothing further sent')
            manifest['identity'] = require_identity(receive(connection.fd, 0), uuid)
            frame = faults_frame()
            manifest['requests_sent'].append('terminal: faults')
            if os.write(connection.fd, frame) != len(frame):
                raise IOError('Partial request; nothing further sent')
            lines = collect_prints(connection.fd)
        text = '\n'.join(lines) + ('\n' if lines else '')
        (out/'faults.txt').write_text(text)
        manifest.update(summarise(lines), output_sha256=sha256(text.encode()), complete=bool(lines))
        if not lines:
            manifest['note'] = ('No printed reply. Another client may have taken the reply, or this firmware '
                                'answers differently; this is not evidence of no faults.')
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        manifest['finished_at_utc'] = utc_now()
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', required=True, help='Explicit VESC USB serial port')
    parser.add_argument('--expected-uuid', required=True, help='Controller UUID of the physically labelled target')
    parser.add_argument('--out', type=Path, required=True, help='New evidence directory')
    args = parser.parse_args(argv)
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError('Evidence output must be a new directory')
    result = read(args.port, args.out, expected_uuid(args.expected_uuid))
    print(json.dumps({k: result[k] for k in ('complete', 'answered', 'fault_count', 'faults_by_name', 'reported_none')}, indent=2))
    print((args.out/'faults.txt').read_text(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
