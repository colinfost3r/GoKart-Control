import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import rx_probe as r


def identity(uuid=r.UUID, minor=2):
    return bytes((0, 6, minor)) + b'75_300_R2\0' + bytes.fromhex(uuid) + bytes(8) + b'no_hw_limits\0'


def contexts(extra=''):
    return r.Capture([bytes((135,)) + (heading + '\n').encode() for heading in r.HEADINGS] + ([bytes((135,)) + extra.encode()] if extra else []), quiet_tail_seconds=0.5)


class FakeConnection:
    fd = 12345
    def __init__(self, reply=None):
        self.reply = identity() if reply is None else reply
        self.queries = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def query(self, command):
        self.queries.append(command)
        return self.reply


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gk-rx-tests-', dir='/tmp/gokart-rx-session-20261111')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'capture'

    def test_exact_monitor_long_frame_and_fragmented_parse(self):
        payload = r.fixed_payload('monitor')
        self.assertEqual(len(payload), 405)
        self.assertEqual(payload[0], 138)
        self.assertEqual(payload[-1], 0)
        frame = r.fixed_frame('monitor')
        self.assertEqual(frame[:3], b'\x03\x01\x95')
        parser = r.PacketParser()
        packets = []
        for value in frame:
            packets += parser.feed(bytes((value,)))
        self.assertEqual(packets, [payload])

    def test_corrupt_crc_rejected(self):
        frame = bytearray(r.fixed_frame('monitor'))
        frame[-2] ^= 1
        self.assertEqual(r.PacketParser().feed(frame), [])

    def test_only_fixed_actions(self):
        for action in ('reset', 'stop', 'flash', 'eval', 5, 131, 133, 139, '(set-current 1)'):
            with self.assertRaises(ValueError): r.fixed_payload(action)
        self.assertEqual(r.fixed_payload('contexts'), b'\x8a:ctxs\0')
        self.assertEqual(r.fixed_payload('stats'), b'\x86')

    def test_changed_monitor_rejected_before_port(self):
        source = Path(self.temp.name) / 'changed.repl'
        source.write_text('(set-current 1)')
        with patch.object(r, 'MONITOR', source), patch.object(r, 'SerialConnection') as connection:
            with self.assertRaises(ValueError):
                r.run('fake', self.out, ownership_reviewed=True)
            connection.assert_not_called()

    def test_partial_write_never_retried(self):
        with patch.object(r.os, 'write', return_value=3) as write:
            with self.assertRaises(IOError): r.send_once(12345, 'monitor')
            write.assert_called_once_with(12345, r.fixed_frame('monitor'))

    def test_unknown_runtime_monitor_refused_before_port(self):
        with patch.object(r, 'SerialConnection') as connection:
            with self.assertRaises(ValueError): r.run('fake', self.out)
            connection.assert_not_called()

    def test_wrong_uuid_no_diagnostic_send(self):
        connection = FakeConnection(identity('17004e000951343037353739'))
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send:
            with self.assertRaises(ValueError): r.run('fake', self.out, inspect=True)
            send.assert_not_called()
            self.assertEqual(connection.queries, [0])

    def test_wrong_firmware_no_diagnostic_send(self):
        connection = FakeConnection(identity(minor=0))
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send:
            with self.assertRaises(ValueError): r.run('fake', self.out, inspect=True)
            send.assert_not_called()

    def test_inspect_only_contexts_and_rechecks_identity(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', side_effect=[[], contexts()]):
            result = r.run('fake', self.out, inspect=True)
            self.assertEqual([x.args[1] for x in send.call_args_list], ['stats', 'contexts'])
            self.assertEqual(connection.queries, [0, 0])
            self.assertEqual(result['contexts']['snapshot'], 'no_contexts_reported')
            self.assertTrue(result['complete'])

    def test_incomplete_contexts_never_report_empty(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once'), patch.object(r, 'collect', side_effect=[[], contexts()[:2]]):
            with self.assertRaises(RuntimeError): r.run('fake', self.out, inspect=True)
        self.assertEqual(r.context_summary([])['snapshot'], 'incomplete_unknown')

    def test_contexts_last_moment_or_partial_unknown(self):
        for quiet, pending in ((0.01, 0), (0.5, 1)):
            packets = contexts()
            packets.quiet_tail_seconds, packets.pending_bytes = quiet, pending
            self.assertEqual(r.context_summary(packets)['snapshot'], 'incomplete_unknown')
        self.assertEqual(r.context_summary(r.Capture(reversed(contexts()), quiet_tail_seconds=1))['snapshot'], 'incomplete_unknown')

    def test_contexts_present_detected(self):
        result = r.context_summary(contexts('ContextID: 42\nStack SP: 5'))
        self.assertEqual(result['snapshot'], 'contexts_present')
        self.assertEqual(result['context_id_lines'], ['ContextID: 42'])

    def test_monitor_completion_and_identity_recheck(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', side_effect=[[], [b'\x87(done 4 15000)']]):
            result = r.run('fake', self.out, ownership_reviewed=True)
            self.assertEqual([x.args[1] for x in send.call_args_list], ['stats', 'monitor'])
            self.assertEqual(connection.queries, [0, 0])
            self.assertTrue(result['monitor_done_seen'])

    def test_monitor_quoted_or_malformed_completion_rejected(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once'), patch.object(r, 'collect', side_effect=[[], [b'\x87Error in (done 4 15000)', b'\x87(done error 15000)', b'\x87(done 4 0)']]):
            with self.assertRaises(RuntimeError): r.run('fake', self.out, ownership_reviewed=True)

    def test_monitor_missing_completion_not_retried(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', side_effect=[[], []]):
            with self.assertRaises(RuntimeError): r.run('fake', self.out, ownership_reviewed=True)
            self.assertEqual([x.args[1] for x in send.call_args_list], ['stats', 'monitor'])

    def test_bounded_deadline_no_input(self):
        ticks = iter(i / 10 for i in range(100))
        with patch.object(r.time, 'monotonic', side_effect=lambda: next(ticks)), patch.object(r.select, 'select', return_value=([], [], [])) as select, patch.object(r.os, 'read') as read:
            self.assertEqual(r.collect(12345, 1, io.StringIO()), [])
            read.assert_not_called()
            self.assertTrue(all(0 <= call.args[3] <= 0.2 for call in select.call_args_list))

    def test_capture_byte_bound(self):
        with patch.object(r, 'MAX_CAPTURE_BYTES', 8), patch.object(r.time, 'monotonic', return_value=0), patch.object(r.select, 'select', return_value=([12345], [], [])), patch.object(r.os, 'read', return_value=b'x' * 9):
            with self.assertRaises(IOError): r.collect(12345, 1, io.StringIO())

    def test_eof_refused(self):
        with patch.object(r.time, 'monotonic', return_value=0), patch.object(r.select, 'select', return_value=([12345], [], [])), patch.object(r.os, 'read', return_value=b''):
            with self.assertRaises(IOError): r.collect(12345, 1, io.StringIO())


if __name__ == '__main__': unittest.main()
