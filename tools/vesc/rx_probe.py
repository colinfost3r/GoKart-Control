#!/usr/bin/env python3
"""Kart-3-only fixed Lisp diagnostics. No arbitrary expressions, reset, flash or motor commands.

--snapshot directly reads RX/TX/ADC/RPM/fault once without setvar or loops.
--inspect queries stats and fixed :ctxs; :ctxs may initialize Lisp but does not
execute stored user code. --monitor requires reviewed ownership and sends only
the SHA256-pinned committed 30-second input monitor. Input reads are read-only;
REPL itself has interpreter initialization/pause/GC/resume side effects.
"""
import argparse
import binascii
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import select
import re
import sys
import time

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / 'tools/vesc'))
from capture import PacketParser
from read_lisp import SerialConnection, require_identity

UUID = '37004e000951343037353739'
MONITOR = WORKTREE / 'firmware/vesc-lisp/reverse-input/rx-monitor-compact.repl'
MONITOR_SHA256 = '6ba5d52cec8608cf295b5a98a96b26a9bd6fea9ddd364db3dbc9a25150610e1f'
HEADINGS = ('****** Running contexts ******', '****** Blocked contexts ******',
            '****** Sleeping contexts ******')
SNAPSHOT_EXPRESSION = b"(print (list 'pins (gpio-read 'pin-rx) (gpio-read 'pin-tx) (get-adc-decoded 0) (get-rpm) (get-fault)))"
MAX_CAPTURE_BYTES = 128 * 1024


def fixed_payload(action):
    if action == 'stats':
        return bytes((134,))
    if action == 'contexts':
        return bytes((138,)) + b':ctxs\0'
    if action == 'snapshot':
        return bytes((138,)) + SNAPSHOT_EXPRESSION + b'\0'
    if action == 'monitor':
        data = MONITOR.read_bytes()
        if hashlib.sha256(data).hexdigest() != MONITOR_SHA256:
            raise ValueError('Committed monitor changed: refusing unreviewed expression')
        return bytes((138,)) + data.strip() + b'\0'
    raise ValueError('Only fixed stats, contexts, snapshot or monitor actions are allowed')


def fixed_frame(action):
    payload = fixed_payload(action)
    if not 1 <= len(payload) <= 512:
        raise ValueError('Fixed payload exceeds pinned packet ceiling')
    header = bytes((2, len(payload))) if len(payload) <= 255 else b'\x03' + len(payload).to_bytes(2, 'big')
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


def send_once(fd, action):
    frame = fixed_frame(action)
    if os.write(fd, frame) != len(frame):
        raise IOError('Partial/uncertain send; stopped without retry or append')


class Capture(list):
    def __init__(self, packets=(), *, quiet_tail_seconds=0.0, pending_bytes=0):
        super().__init__(packets)
        self.quiet_tail_seconds = quiet_tail_seconds
        self.pending_bytes = pending_bytes


def collect(fd, seconds, journal):
    """Fixed wall-clock deadline and byte budget. Capture every CRC-valid packet."""
    parser = PacketParser()
    started = time.monotonic()
    deadline = started + seconds
    last_received = started
    packets = Capture()
    seen = 0
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        ready, _, _ = select.select([fd], [], [], max(0, min(0.2, remaining)))
        if not ready:
            continue
        try:
            raw = os.read(fd, 4096)
        except BlockingIOError:
            continue
        if not raw:
            raise IOError('Serial connection closed during bounded capture')
        last_received = time.monotonic()
        seen += len(raw)
        if seen > MAX_CAPTURE_BYTES:
            raise IOError('Capture byte limit reached; stopped without another command')
        for payload in parser.feed(raw):
            packets.append(payload)
            record = {'monotonic': time.monotonic(), 'command': payload[0], 'payload_hex': payload.hex()}
            if payload[0] in (135, 138):
                record['text'] = payload[1:].rstrip(b'\0').decode('utf-8', errors='replace')
                print(record['text'], flush=True)
            journal.write(json.dumps(record) + '\n')
            journal.flush()
    packets.quiet_tail_seconds = max(0.0, time.monotonic() - last_received)
    packets.pending_bytes = len(parser.buffer)
    return packets


def printed_text(packets):
    return '\n'.join(p[1:].rstrip(b'\0').decode('utf-8', errors='replace')
                     for p in packets if p and p[0] in (135, 138))


def context_summary(packets):
    text = printed_text(packets)
    positions = [text.find(h) for h in HEADINGS]
    ordered = all(i >= 0 for i in positions) and positions == sorted(set(positions))
    quiet = getattr(packets, 'quiet_tail_seconds', 0.0) >= 0.25
    no_partial = getattr(packets, 'pending_bytes', 1) == 0
    complete = ordered and quiet and no_partial
    ids = [line.strip() for line in text.splitlines() if 'ContextID:' in line]
    return {'all_context_headings_seen_in_order': ordered, 'quiet_tail_at_least_250ms': quiet,
            'no_partial_frame': no_partial, 'context_id_lines': ids,
            'snapshot': ('contexts_present' if ids else
                         'no_contexts_reported' if complete else 'incomplete_unknown'),
            'atomic_or_future_ownership_proof': False}


def pin_snapshot_record(line):
    number = r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
    # Pinned LispBM prints floats as {0.082444}; accept only balanced wrappers.
    field = r'(?:' + number + r'|\{' + number + r'\})'
    match = re.fullmatch(r'\(pins ([01]) ([01]) (' + field + r') (' + field + r') ([0-9]+)\)', line)
    if not match:
        return None
    adc, rpm = (float(value[1:-1] if value.startswith('{') else value)
                for value in (match[3], match[4]))
    if not math.isfinite(adc) or not math.isfinite(rpm):
        return None
    return {'rx': int(match[1]), 'tx': int(match[2]), 'adc_decoded_0': adc,
            'rpm': rpm, 'fault': int(match[5])}


def run(port, output, *, inspect=False, snapshot=False, ownership_reviewed=False):
    if inspect and snapshot:
        raise ValueError("Choose either context inspection or the fixed pin snapshot")
    if not inspect and not snapshot and not ownership_reviewed:
        raise ValueError('Monitor requires explicit --ownership-reviewed after stored-code/context review')
    # Validate fixed expression before touching the port.
    action = 'contexts' if inspect else 'snapshot' if snapshot else 'monitor'
    fixed_frame(action)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'port': port, 'uuid_pin': UUID, 'firmware_pin': '6.02',
                'mode': 'inspect' if inspect else 'snapshot' if snapshot else 'monitor',
                'ownership_reviewed': ownership_reviewed,
                'monitor_file_sha256': MONITOR_SHA256, 'complete': False,
                'sent_actions': [], 'interpreter_side_effects':
                'REPL may initialize interpreter; expression evaluation may pause/GC/resume it. No reset requested.'}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    def send(fd, action):
        manifest['sent_actions'].append({'action': action, 'frame_hex': fixed_frame(action).hex()})
        save()
        send_once(fd, action)
    try:
        with SerialConnection(port) as connection, (output / 'packets.jsonl').open('x') as journal:
            identity = connection.query(0)
            (output / 'identity_before.bin').write_bytes(identity)
            manifest['identity_before'] = require_identity(identity, UUID)
            save()
            if not snapshot:
                send(connection.fd, 'stats')
                stats = collect(connection.fd, 1.0, journal)
                manifest['stats_reply_seen'] = any(p[0] == 134 for p in stats)
                manifest['stats_note'] = 'Reply proves evaluator exists, not that contexts are idle; absence is inconclusive.'
            send(connection.fd, action)
            packets = collect(connection.fd, 3.0 if inspect else 2.0 if snapshot else 35.0, journal)
            if inspect:
                manifest['contexts'] = context_summary(packets)
                if manifest['contexts']['snapshot'] == 'incomplete_unknown':
                    raise RuntimeError('Incomplete context output; ownership remains unknown')
            elif snapshot:
                lines = [line.strip() for line in printed_text(packets).splitlines()]
                records = [(line, pin_snapshot_record(line)) for line in lines]
                manifest['pin_snapshot_lines'] = [line for line, record in records if record is not None]
                manifest['pin_snapshots'] = [record for _, record in records if record is not None]
                if not manifest['pin_snapshot_lines']:
                    raise RuntimeError('No fixed pin snapshot reply within 2 seconds; no automatic resend')
            else:
                text = printed_text(packets)
                matches = [re.fullmatch(r'\(done ([0-9]+) ([0-9]+)\)', line.strip())
                           for line in text.splitlines()]
                manifest['monitor_done_seen'] = any(
                    m and 0 <= int(m[1]) <= int(m[2]) and int(m[2]) > 0 for m in matches)
                if not manifest['monitor_done_seen']:
                    raise RuntimeError('No monitor completion marker within 35 seconds; do not resend automatically')
            identity_after = connection.query(0)
            (output / 'identity_after.bin').write_bytes(identity_after)
            manifest['identity_after'] = require_identity(identity_after, UUID)
            manifest['complete'] = True
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', required=True, type=Path)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--inspect', action='store_true', help='Fixed stats + :ctxs only; does not run monitor')
    actions.add_argument('--snapshot', action='store_true', help='One fixed direct RX/TX/ADC/RPM/fault read; no loop or mutation')
    parser.add_argument('--ownership-reviewed', action='store_true', help='Required for monitor after manual preflight')
    args = parser.parse_args()
    result = run(args.port, args.out, inspect=args.inspect, snapshot=args.snapshot, ownership_reviewed=args.ownership_reviewed)
    print(json.dumps(result.get('contexts', {'pin_snapshot_lines': result.get('pin_snapshot_lines')} if args.snapshot else {'monitor_done_seen': result.get('monitor_done_seen')}), indent=2))


if __name__ == '__main__':
    main()
