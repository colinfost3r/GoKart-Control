#!/usr/bin/env python3
"""Fixed kart-3 diagnostics only; no arbitrary commands, control, reset or writes.

Source: bldc f7c2b34e1cff2234cae98be3abf0cd50e249558f:
events.c terminal_print reads the event ring; terminal.c faults/foc_state only
print history/state; lispif_vesc_extensions.c app-is-output-disabled reads a flag.
REPL may initialize/pause/GC/resume Lisp. No Lisp reset is requested. Run only
after the pedal trace has closed its port; leave other communications clients off.
The terminal snapshots are not atomic and faults has no explicit end marker.
"""
import argparse
import binascii
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import select
import sys
import time

ROOT = Path('/Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5')
sys.path.insert(0, str(ROOT / 'tools/vesc'))
from capture import PacketParser
from read_lisp import SerialConnection, require_identity

UUID = '37004e000951343037353739'
SOURCE_COMMIT = 'f7c2b34e1cff2234cae98be3abf0cd50e249558f'
# SHA256 of the reviewed files extracted from the pinned firmware source archive.
SOURCE_HASHES = {
    'events.c': '77ee0a078ea6bca475a67808f13161b175714c954550d183d8b3fecea875de35',
    'terminal.c': '62494e533e9cce65f6cd105ae343d2d78bb4182912db3d5d878ce3f49dfeb03e',
    'lispBM/lispif_vesc_extensions.c': '702b4aeb250f87315a2a1a1a3855c15812f42b6a606df313d6a6bdd51ed6e298',
}
GETTER = b"(print (list 'gk-output-disabled (app-is-output-disabled)))"
MAX_SECONDS = 15.0
MAX_BYTES = 65536
QUIET_SECONDS = 0.35
ACTIONS = ('events', 'foc_state', 'faults', 'output-disabled')


def payload(action):
    if action == 'identity':
        return b'\0'
    if action in ('events', 'foc_state', 'faults'):
        return b'\x14' + action.encode('ascii')
    if action == 'output-disabled':
        return b'\x8a' + GETTER + b'\0'
    raise ValueError('Only fixed identity/events/foc_state/faults/output-disabled reads allowed')


def frame(action):
    data = payload(action)
    assert len(data) < 256
    return bytes((2, len(data))) + data + binascii.crc_hqx(data, 0).to_bytes(2, 'big') + b'\3'


def response_summary(action, packets):
    terminal = [p[1:].rstrip(b'\0').decode('utf-8', 'replace').strip() for p in packets if p[0] == 21]
    lisp = [p[1:].rstrip(b'\0').decode('utf-8', 'replace').strip() for p in packets if p[0] in (135, 138)]
    if action == 'events':
        matches = [re.fullmatch(r'Events total: ([0-9]+)', s) for s in terminal]
        seen = any(m for m in matches)
    elif action == 'foc_state':
        seen = 'FOC State:' in terminal and any(re.fullmatch(r'off_delay:\s*-?[0-9]+\.[0-9]+', s) for s in terminal)
    elif action == 'faults':
        seen = ('No faults registered since startup' in terminal or
                ('The following faults were registered since start:' in terminal and
                 any(s.startswith('Fault ') for s in terminal) and bool(terminal) and terminal[-1] == ''))
    elif action == 'output-disabled':
        states = [re.fullmatch(r'\(gk-output-disabled (t|nil)\)', s) for s in lisp]
        seen = any(states) and any(re.fullmatch(r'>\s*t', s) for s in lisp)
    else:
        raise ValueError('Not a fixed diagnostic action')
    result = {'expected_output_seen': bool(seen), 'terminal_lines': terminal, 'lisp_lines': lisp,
              'atomic_snapshot': False, 'protocol_end_marker_available': action != 'faults'}
    if action == 'output-disabled' and seen:
        result['app_output_disabled'] = next(m[1] == 't' for m in states if m)
    return result


class Wire:
    def __init__(self, fd, output):
        self.fd, self.output = fd, Path(output)
        self.started = time.monotonic()
        self.deadline = self.started + MAX_SECONDS
        self.parser = PacketParser()
        self.received = 0

    def record(self, **record):
        record['elapsed_s'] = time.monotonic() - self.started
        with (self.output / 'packets.jsonl').open('a') as out:
            out.write(json.dumps(record) + '\n')

    def send(self, action):
        if time.monotonic() >= self.deadline or self.parser.buffer:
            raise TimeoutError('Expired session or partial packet; no further request sent')
        raw = frame(action)
        self.record(kind='tx_attempt', action=action, frame_hex=raw.hex())
        with (self.output / 'tx-attempts.bin').open('ab') as out:
            out.write(raw)
        if time.monotonic() >= self.deadline:
            self.record(kind='not_sent', action=action, reason='deadline expired during journaling')
            raise TimeoutError('Session expired before write')
        count = os.write(self.fd, raw)
        self.record(kind='tx_return', action=action, count=count)
        if count != len(raw):
            raise IOError('Partial or uncertain send; never append or retry')

    def receive_once(self, deadline):
        deadline = min(deadline, self.deadline)
        if time.monotonic() >= deadline:
            return []
        ready, _, _ = select.select([self.fd], [], [], max(0, min(0.05, deadline - time.monotonic())))
        if not ready:
            return []
        try:
            raw = os.read(self.fd, min(4096, MAX_BYTES - self.received))
        except BlockingIOError:
            return []
        if not raw:
            raise IOError('Serial closed or capture byte budget exhausted')
        self.received += len(raw)
        with (self.output / 'rx-wire.bin').open('ab') as out:
            out.write(raw)
        packets = self.parser.feed(raw)
        for p in packets:
            row = {'kind': 'rx', 'command': p[0], 'payload_hex': p.hex()}
            if p[0] in (21, 135, 138):
                row['text'] = p[1:].rstrip(b'\0').decode('utf-8', 'replace')
                print(row['text'], flush=True)
            self.record(**row)
            if p[0] not in (0, 21, 135, 138):
                raise ValueError('Unexpected response; no further command sent')
        if self.received >= MAX_BYTES:
            raise IOError('Capture byte budget exhausted; no further request sent')
        return packets

    def identity(self, phase):
        self.send('identity')
        deadline = min(self.deadline, time.monotonic() + 2.0)
        while time.monotonic() < deadline:
            for p in self.receive_once(deadline):
                if p[0] == 0:
                    (self.output / ('identity_' + phase + '.bin')).write_bytes(p)
                    result = require_identity(p, UUID)
                    if (result.get('hardware') != '75_300_R2' or result.get('firmware_name') != 'no_hw_limits'
                            or result.get('test_version') != 0):
                        raise ValueError('Expected exact kart-3 release firmware target')
                    return result
        raise TimeoutError('No matching identity reply; no retry')

    def diagnostic(self, action):
        self.send(action)
        deadline = min(self.deadline, time.monotonic() + 2.5)
        packets = []
        last_received = time.monotonic()
        while time.monotonic() < deadline:
            old_bytes = self.received
            packets.extend(self.receive_once(deadline))
            if self.received != old_bytes:
                last_received = time.monotonic()
            summary = response_summary(action, packets)
            quiet = time.monotonic() - last_received
            if summary['expected_output_seen'] and quiet >= QUIET_SECONDS and not self.parser.buffer:
                return {**summary, 'quiet_tail_seconds': quiet, 'no_partial_frame': True}
        raise TimeoutError('Missing or incomplete fixed diagnostic output; no retry or later command')


def run(port, output, *, connection_factory=SerialConnection, wire_factory=Wire):
    for action in ('identity',) + ACTIONS:
        frame(action)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'complete': False, 'uuid_pin': UUID, 'firmware_pin': '6.02',
        'source_commit': SOURCE_COMMIT, 'reviewed_source_sha256': SOURCE_HASHES,
        'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'fixed_actions': list(ACTIONS), 'maximum_session_seconds': MAX_SECONDS,
        'maximum_receive_bytes': MAX_BYTES, 'diagnostics': {},
        'requested_motor_or_config_writes': False, 'requested_lifecycle_or_reset': False,
        'repl_side_effects': 'May initialize/pause/GC/resume interpreter; getter itself only reads application output-disabled flag.',
        'capture_limits': 'Snapshots are non-atomic; faults has no explicit completion marker. Output is accepted only after expected content and a quiet tail.'}
    def save():
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    save()
    try:
        with connection_factory(port) as connection:
            wire = wire_factory(connection.fd, output)
            manifest['identity_before'] = wire.identity('before')
            save()
            for action in ACTIONS:
                manifest['diagnostics'][action] = wire.diagnostic(action)
                save()
            manifest['identity_after'] = wire.identity('after')
            manifest['received_bytes'] = wire.received
            manifest['complete'] = True
    except BaseException as exc:
        manifest['error'] = str(exc)
        raise
    finally:
        manifest['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    return manifest


def self_test():
    """Offline only; no SerialConnection instantiated and no port opened."""
    import tempfile
    import unittest
    from unittest.mock import patch
    class Tests(unittest.TestCase):
        def test_exact_allowlist_and_crc(self):
            expected = {'identity': b'\0', 'events': b'\x14events', 'foc_state': b'\x14foc_state',
                        'faults': b'\x14faults', 'output-disabled': b'\x8a' + GETTER + b'\0'}
            for action, data in expected.items():
                parser = PacketParser()
                self.assertEqual(parser.feed(frame(action)), [data])
                self.assertFalse(parser.buffer)
            for bad in ('reboot', 'foc_dc_cal', 'drv_reset_faults', 'faults;reboot', 'app-disable-output', 'start', 133, None):
                with self.assertRaises(ValueError): payload(bad)
        def test_partial_write_once(self):
            with tempfile.TemporaryDirectory() as d, patch.object(os, 'write', return_value=1) as write:
                with self.assertRaises(IOError): Wire(99999, d).send('events')
                self.assertEqual(write.call_count, 1)
        def test_expired_no_write(self):
            with tempfile.TemporaryDirectory() as d, patch.object(os, 'write') as write:
                wire = Wire(99999, d); wire.deadline = 0
                with self.assertRaises(TimeoutError): wire.send('events')
                write.assert_not_called()
        def test_partial_packet_no_write(self):
            with tempfile.TemporaryDirectory() as d, patch.object(os, 'write') as write:
                wire = Wire(99999, d); wire.parser.buffer.extend(b'\2')
                with self.assertRaises(TimeoutError): wire.send('faults')
                write.assert_not_called()
        def test_split_mixed_packets_preserved(self):
            def pack(data):
                return bytes((2, len(data))) + data + binascii.crc_hqx(data, 0).to_bytes(2, 'big') + b'\3'
            packets = [b'\x15Events total: 0\n', b'\x87(gk-rx-filter-applied 0)']
            raw = b''.join(pack(p) for p in packets)
            with tempfile.TemporaryDirectory() as d, patch.object(select, 'select', return_value=([99999], [], [])), patch.object(os, 'read', side_effect=[raw[:3], raw[3:]]):
                wire = Wire(99999, d)
                self.assertEqual(wire.receive_once(wire.deadline), [])
                self.assertTrue(wire.parser.buffer)
                self.assertEqual(wire.receive_once(wire.deadline), packets)
                self.assertFalse(wire.parser.buffer)
                self.assertEqual((Path(d) / 'rx-wire.bin').read_bytes(), raw)
        def test_byte_budget_aborts(self):
            with tempfile.TemporaryDirectory() as d, patch.object(select, 'select', return_value=([99999], [], [])), patch.object(os, 'read', return_value=b'\2') as read:
                wire = Wire(99999, d); wire.received = MAX_BYTES - 1
                with self.assertRaisesRegex(IOError, 'byte budget'): wire.receive_once(wire.deadline)
                read.assert_called_once_with(99999, 1)
        def test_summaries(self):
            self.assertTrue(response_summary('events', [b'\x15Events total: 30\n'])['expected_output_seen'])
            self.assertFalse(response_summary('events', [b'\x15Events total: unknown'])['expected_output_seen'])
            self.assertTrue(response_summary('foc_state', [b'\x15FOC State:', b'\x15off_delay: 0.00'])['expected_output_seen'])
            self.assertTrue(response_summary('faults', [b'\x15No faults registered since startup\n'])['expected_output_seen'])
            self.assertFalse(response_summary('faults', [b'\x15The following faults were registered since start:\n'])['expected_output_seen'])
            for state, value in ((b'nil', False), (b't', True)):
                s = response_summary('output-disabled', [b'\x87(gk-output-disabled ' + state + b')', b'\x8a> t'])
                self.assertEqual(s['app_output_disabled'], value)
            self.assertFalse(response_summary('output-disabled', [b'\x87(gk-output-disabled nil)'])['expected_output_seen'])
        def test_identity_failure_prevents_diagnostics(self):
            class C:
                fd = 99999
                def __init__(self, port): pass
                def __enter__(self): return self
                def __exit__(self, *args): pass
            class W:
                def __init__(self, fd, out): pass
                def identity(self, phase): raise ValueError('wrong identity')
                def diagnostic(self, action): raise AssertionError('must not reach diagnostic')
            with tempfile.TemporaryDirectory() as d:
                out = Path(d) / 'new'
                with self.assertRaisesRegex(ValueError, 'wrong identity'):
                    run('FAKE-NO-PORT', out, connection_factory=C, wire_factory=W)
                self.assertFalse(json.loads((out / 'manifest.json').read_text())['complete'])
        def test_existing_output_refused(self):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(FileExistsError): run('FAKE-NO-PORT', d)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true', help='Offline fixed-frame and abort-path tests only')
    parser.add_argument('--port')
    parser.add_argument('--out')
    args = parser.parse_args()
    if args.self_test:
        if args.port or args.out: parser.error('--self-test takes no port/output')
        raise SystemExit(self_test())
    if not args.port or not args.out: parser.error('--port and new --out are required')
    run(args.port, args.out)
