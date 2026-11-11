import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
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
        self.temp = tempfile.TemporaryDirectory(prefix='gk-rx-tests-')
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

    def test_snapshot_fixed_expression_no_mutation_or_loop(self):
        expression = b"(print (list 'pins (gpio-read 'pin-rx) (gpio-read 'pin-tx) (get-adc-decoded 0) (get-rpm) (get-fault)))"
        self.assertEqual(r.fixed_payload('snapshot'), b'\x8a' + expression + b'\0')
        self.assertEqual(r.PacketParser().feed(r.fixed_frame('snapshot')), [b'\x8a' + expression + b'\0'])
        for forbidden in (b'setvar', b'loop', b'set-', b'conf-', b'detach', b'override', b'gpio-configure'):
            self.assertNotIn(forbidden, expression)

    def test_snapshot_only_single_read_expression_and_identity_rechecks(self):
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', return_value=[b'\x87(pins 0 1 0.09 0 0)']) as collect:
            result = r.run('fake', self.out, snapshot=True)
            self.assertEqual([x.args[1] for x in send.call_args_list], ['snapshot'])
            self.assertEqual(collect.call_args.args[1], 2.0)
            self.assertEqual(connection.queries, [0, 0])
            self.assertEqual(result['pin_snapshot_lines'], ['(pins 0 1 0.09 0 0)'])
            self.assertEqual(result['pin_snapshots'], [
                {'rx': 0, 'tx': 1, 'adc_decoded_0': 0.09, 'rpm': 0.0, 'fault': 0}])
            self.assertTrue(result['complete'])
        self.assertEqual(r.pin_snapshot_record('(pins 0 1 0.089019 0.000014 0)'),
                         {'rx': 0, 'tx': 1, 'adc_decoded_0': 0.089019, 'rpm': 0.000014, 'fault': 0})
        self.assertEqual(r.pin_snapshot_record('(pins 1 0 +.09 -1.4e-5 3)'),
                         {'rx': 1, 'tx': 0, 'adc_decoded_0': 0.09, 'rpm': -0.000014, 'fault': 3})

    def test_snapshot_actual_lispbm_braced_float_packet(self):
        # Exact printed payload observed on kart 3, 2026-11-11 (command 135).
        payload = b'\x87(pins 0 1 {0.082444} {0.000007} 0)'
        connection = FakeConnection()
        with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', return_value=[payload]):
            result = r.run('fake', self.out, snapshot=True)
        self.assertEqual(result['pin_snapshot_lines'], [payload[1:].decode()])
        self.assertEqual(result['pin_snapshots'], [
            {'rx': 0, 'tx': 1, 'adc_decoded_0': 0.082444, 'rpm': 0.000007, 'fault': 0}])
        self.assertTrue(result['complete'])
        self.assertEqual([call.args[1] for call in send.call_args_list], ['snapshot'])
        self.assertEqual(connection.queries, [0, 0])
        self.assertEqual(r.pin_snapshot_record('(pins 0 1 {0.089019} {0.000014} 0)'),
                         {'rx': 0, 'tx': 1, 'adc_decoded_0': 0.089019, 'rpm': 0.000014, 'fault': 0})
        self.assertEqual(r.pin_snapshot_record('(pins 1 0 {+.09} {-1.4e-5} 3)'),
                         {'rx': 1, 'tx': 0, 'adc_decoded_0': 0.09, 'rpm': -0.000014, 'fault': 3})

    def test_snapshot_wrong_identity_refused(self):
        for label, reply in (('uuid', identity('17004e000951343037353739')),
                             ('firmware', identity(minor=0))):
            with self.subTest(label=label):
                connection = FakeConnection(reply)
                with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect') as collect:
                    with self.assertRaises(ValueError): r.run('fake', self.out / label, snapshot=True)
                    send.assert_not_called()
                    collect.assert_not_called()
                    self.assertEqual(connection.queries, [0])

    def test_snapshot_missing_or_error_reply_never_retried(self):
        invalid = ('Error in (pins 0 1 0.09 0 0)', '(pins 0 1 error 0 0)',
                   '(pins 0 1 0.09 0)', '(pins 0 1 0.09 0 0 extra)',
                   '(pins 0 1 nan 0 0)', '(pins 0 1 0.09 inf 0)',
                   '(pins 0 1 1e999 0 0)', '(pins 0 1 0.09 -1e999 0)',
                   '(pins 2 1 0.09 0 0)', '(pins 0 1 0.09 0 0.5)',
                   '(pins 0 1 0.09 0 -1)', '(pins 0 1 {0.09 0 0)',
                   '(pins 0 1 0.09} 0 0)', '(pins 0 1 {{0.09}} 0 0)',
                   '(pins 0 1 {nan} 0 0)', '(pins 0 1 0.09 {inf} 0)',
                   '(pins 0 1 {1e999} 0 0)', '(pins 0 1 0.09 {-1e999} 0)')
        for text in invalid:
            self.assertIsNone(r.pin_snapshot_record(text))
        for label, packets in (('missing', []), ('invalid', [b'\x87' + text.encode() for text in invalid])):
            with self.subTest(label=label):
                connection = FakeConnection()
                with patch.object(r, 'SerialConnection', return_value=connection), patch.object(r, 'send_once') as send, patch.object(r, 'collect', return_value=packets):
                    with self.assertRaises(RuntimeError): r.run('fake', self.out / label, snapshot=True)
                    self.assertEqual([x.args[1] for x in send.call_args_list], ['snapshot'])
                    self.assertEqual(connection.queries, [0])

    def test_snapshot_inspect_conflict_refused(self):
        with patch.object(r, 'SerialConnection') as connection:
            with self.assertRaises(ValueError): r.run('fake', self.out, inspect=True, snapshot=True)
            connection.assert_not_called()

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
