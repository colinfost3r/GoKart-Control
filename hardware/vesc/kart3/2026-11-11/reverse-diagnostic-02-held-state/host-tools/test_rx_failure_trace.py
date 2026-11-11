import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import rx_failure_trace as t

VALUES = bytes((4,)) + bytes(73)


def packet(payload):
    header = bytes((2, len(payload))) if len(payload) <= 255 else b'\x03' + len(payload).to_bytes(2, 'big')
    return header + payload + t.binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


def identity(uuid=t.probe.UUID, minor=2):
    return bytes((0, 6, minor)) + b'75_300_R2\0' + bytes.fromhex(uuid) + bytes(8) + b'no_hw_limits\0'


class SimulatedLink:
    def __init__(self, *, replies=True, done=True):
        self.now = 0.0
        self.sent = []
        self.pending = False
        self.replies, self.done = replies, done
        self.done_sent = False
    def clock(self): return self.now
    def send(self, action):
        if action == 'values':
            assert not self.pending, 'more than one query outstanding'
            self.pending = True
        self.sent.append((self.now, action))
    def receive(self, wait):
        self.now += max(0.001, wait)
        result = []
        if self.pending and self.replies:
            self.pending = False
            result += [b'\x87(1 0 0 500 0.2 -10 0)', VALUES]
        if self.done and not self.done_sent and self.now >= 2.8:
            result.append(b'\x87(done 2 13400)')
            self.done_sent = True
        return result


class TraceTests(unittest.TestCase):
    def test_only_fixed_command_frames(self):
        self.assertEqual(t.frame_for('identity'), packet(b'\0'))
        self.assertEqual(t.frame_for('values'), packet(b'\x04'))
        frame = t.frame_for('monitor')
        self.assertEqual(frame[:3], b'\x03\x01\x95')
        self.assertEqual(len(t.PacketParser().feed(frame)[0]), 405)
        for action in ('current', 'pwm', 'config', 'reset', 'faults', 'eval', 5):
            with self.assertRaises(ValueError): t.frame_for(action)

    def test_one_write_no_append_retry(self):
        link = t.Link(12345, io.StringIO())
        with patch.object(t.os, 'write', return_value=1) as write:
            with self.assertRaises(IOError): link.send('monitor')
            write.assert_called_once_with(12345, t.frame_for('monitor'))

    def test_mixed_fragmented_135_and_4_preserved(self):
        first, last = b'\x87(1 0 0 500 0.2 -10 0)', b'\x87(done 2 13400)'
        a, b, c = packet(first), packet(VALUES), packet(last)
        journal = io.StringIO()
        link = t.Link(12345, journal)
        chunks = [a[:8], a[8:] + b[:20], b[20:] + c]
        result = []
        with patch.object(t.select, 'select', return_value=([12345], [], [])), patch.object(t.os, 'read', side_effect=chunks), patch('builtins.print'):
            for _ in chunks: result.extend(link.receive(.05))
        self.assertEqual(result, [first, VALUES, last])
        records = [json.loads(line) for line in journal.getvalue().splitlines()]
        self.assertEqual([record['command'] for record in records], [135, 4, 135])
        self.assertIn('iq_a', records[1]['values'])
        self.assertEqual(link.parser.buffer, b'')

    def test_telemetry_timeout_stops_without_resend(self):
        link = SimulatedLink(replies=False, done=False)
        with self.assertRaises(TimeoutError): t.capture_loop(link, clock=link.clock, duration=3)
        self.assertEqual([action for _, action in link.sent], ['monitor', 'values'])
        self.assertLessEqual(link.now, 1.06)

    def test_success_one_pending_query_and_fixed_deadline(self):
        link = SimulatedLink()
        result = t.capture_loop(link, clock=link.clock, duration=3)
        self.assertEqual([a for _, a in link.sent].count('monitor'), 1)
        self.assertGreater(result['telemetry_replies'], 10)
        self.assertEqual(result['telemetry_replies'], [a for _, a in link.sent].count('values'))
        polls = [when for when, action in link.sent if action == 'values']
        self.assertTrue(all(b-a >= .09999 for a, b in zip(polls, polls[1:])))
        self.assertTrue(result['monitor_done_seen'])
        self.assertGreaterEqual(link.now, 3)
        self.assertLess(link.now, 3.01)

    def test_missing_completion_does_not_resend(self):
        link = SimulatedLink(done=False)
        with self.assertRaises(RuntimeError): t.capture_loop(link, clock=link.clock, duration=3)
        self.assertEqual([a for _, a in link.sent].count('monitor'), 1)
        self.assertLess(link.now, 3.01)

    def test_unexpected_values_refused(self):
        link = SimulatedLink()
        old = link.receive
        def receive(wait): return old(wait) + [VALUES]
        link.receive = receive
        with self.assertRaises(RuntimeError): t.capture_loop(link, clock=link.clock, duration=3)

    def test_identity_mismatch_stops_before_monitor(self):
        class WrongIdentity:
            def __init__(self): self.sent=[]
            def send(self, action): self.sent.append(action)
            def receive(self, wait): return [identity('17004e000951343037353739')]
        link=WrongIdentity()
        with self.assertRaises(ValueError): t.identity_query(link)
        self.assertEqual(link.sent, ['identity'])

    def test_wrong_firmware_refused(self):
        class WrongFirmware:
            def send(self, action): pass
            def receive(self, wait): return [identity(minor=0)]
        with self.assertRaises(ValueError): t.identity_query(WrongFirmware())

    def test_byte_budget_and_eof(self):
        for raw in (b'', b'123456'):
            with patch.object(t, 'MAX_BYTES', 5), patch.object(t.select, 'select', return_value=([12345], [], [])), patch.object(t.os, 'read', return_value=raw):
                with self.assertRaises(IOError): t.Link(12345, io.StringIO()).receive(.05)

    def test_completion_requires_exact_numeric_line(self):
        self.assertTrue(t.completion_seen('(done 2 13400)'))
        for value in ('Error in (done 2 13400)', '(done a b)', '(done 2 0)', '(done 100 2)'):
            self.assertFalse(t.completion_seen(value))


if __name__ == '__main__': unittest.main()
