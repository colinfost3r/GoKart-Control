"""Guarded persistent tune tests with fake serial packets; never open hardware."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import binascii
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/vesc'))
import apply_tune as apply
import tune
from capture import PacketParser, query_frame

REFERENCE = ROOT/'hardware/vesc/baseline-kart/2026-11-05/raw'
CURRENT = ROOT/'hardware/vesc/kart3/2026-11-10/usb-prewrite-connected/raw'


def packet(payload):
    length = len(payload)
    header = bytes([2, length]) if length < 256 else b'\x03' + length.to_bytes(2, 'big')
    return header + payload + binascii.crc_hqx(payload, 0).to_bytes(2, 'big') + b'\x03'


class FakeWire:
    """Drive the real SerialConnection read/write/parser paths using mocked fd calls."""
    def __init__(self, payloads):
        self.before = dict(payloads)
        self.current = dict(payloads)
        self.pending = bytearray()
        self.sent = []
        self.mode = 'normal'
        self.after_change = None
        self.short_query = None
        self.missing_query_once = None

    def flush(self, fd, which):
        self.pending.clear()

    def write(self, fd, frame):
        payloads = PacketParser().feed(frame)
        assert len(payloads) == 1
        payload = payloads[0]
        command = payload[0]
        self.sent.append(payload)
        if command == 13:
            if self.mode == 'partial':
                return len(frame)-1
            if self.mode == 'exception':
                raise OSError('Unknown number of bytes delivered')
            self.current['motor_configuration'] = b'\x0e' + payload[1:]
            if self.after_change:
                self.after_change(self.current)
            if self.mode != 'missing_ack':
                self.pending.extend(packet(b'\r\x00' if self.mode == 'bad_ack' else b'\r'))
        else:
            assert command in (0, 4, 14, 17), command
            if self.short_query == command:
                return len(frame)-1
            if self.missing_query_once == command:
                self.missing_query_once = None
                return len(frame)
            self.pending.extend(packet(self.current[apply.READ_COMMANDS[command]]))
        return len(frame)

    def read(self, fd, size):
        # Fragment frames to exercise stream parsing, including config payloads.
        chunk = bytes(self.pending[:31])
        del self.pending[:31]
        return chunk

    def select(self, fds, write, error, timeout):
        return (fds if self.pending else [], [], [])


class FakeSerial(apply.SerialConnection):
    def __init__(self, wire):
        super().__init__('FAKE-NO-HARDWARE')
        self.fd = 77
        self.wire = wire

    def receive(self, command, timeout=3.0):
        # Avoid a real five-second test wait; actual parser/ACK validation still run.
        if not self.wire.pending:
            raise TimeoutError('Fake CRC-valid reply missing; no retry')
        return super().receive(command, timeout=.1)


class ApplyTuneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.artifacts = tune.prepare(REFERENCE, CURRENT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.trial = self.base/'trial'
        tune.write_trial(self.plan, self.artifacts, self.trial)
        self.bundle = apply.validate_trial(self.trial)
        self.wire = FakeWire(self.artifacts['before'])
        self.connection = FakeSerial(self.wire)
        self.out = self.base/'evidence'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(apply.os, 'write', self.wire.write))
        self.stack.enter_context(patch.object(apply.os, 'read', self.wire.read))
        self.stack.enter_context(patch.object(apply.select, 'select', self.wire.select))
        self.stack.enter_context(patch.object(apply.termios, 'tcflush', self.wire.flush))

    def run_trial(self, **kwargs):
        return apply.run(self.bundle, self.connection, self.out, **kwargs)

    def report(self):
        return json.loads((self.out/'apply-manifest.json').read_text())

    def ids(self):
        return [payload[0] for payload in self.wire.sent]

    def test_default_is_offline_and_explicit_persistence_flag_is_required(self):
        with patch.object(apply, 'SerialConnection') as connection, redirect_stdout(io.StringIO()):
            self.assertEqual(apply.main([str(self.trial)]), 0)
            connection.assert_not_called()
        for args in (['--apply'], ['--acknowledge-persistent-write'],
                     ['--apply', '--acknowledge-persistent-write'], ['--port', '/no-port']):
            with self.subTest(args=args), patch.object(apply, 'SerialConnection') as connection:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    apply.main([str(self.trial)] + args)
                connection.assert_not_called()
        with self.assertRaises(ValueError):
            query_frame(13)  # Existing read-only capture allowlist remains unchanged.

    def test_preflight_reads_exactly_four_with_telemetry_last_and_no_settings(self):
        result = self.run_trial()
        self.assertEqual(self.ids(), [0, 14, 17, 4])
        self.assertEqual(result['status'], 'preflight_verified_no_settings_sent')
        self.assertEqual(result['mutating_write_attempts'], 0)
        self.assertTrue(json.loads((self.out/'before/manifest.json').read_text())['capture_complete'])

    def test_success_is_one_persistent_write_then_ack_and_complete_376_field_readback(self):
        result = self.run_trial(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
        self.assertEqual(self.wire.sent[4], b'\r' + self.artifacts['proposed_motor'][1:])
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        self.assertEqual(result['verified_total_fields'], 376)
        self.assertTrue(result['ack_verified'])
        self.assertTrue(result['readback_verified'])
        self.assertEqual(result['mutating_write_attempts'], 1)
        self.assertFalse(result['saved_flash_independently_verified'])
        self.assertEqual((self.out/'after/app_configuration.bin').read_bytes(), self.artifacts['before']['app_configuration'])
        self.assertEqual((self.out/'after/motor_configuration.bin').read_bytes(), self.artifacts['proposed_motor'])
        self.assertEqual(apply.PacketParser().feed((self.out/'set_mcconf_frame.bin').read_bytes()), [self.wire.sent[4]])
        audit = json.loads((self.out/'field-audit.json').read_text())
        self.assertEqual(sum(len(group['fields']) for group in audit.values()), 376)

    def test_wrong_uuid_hardware_or_firmware_rejected_before_configuration_reads(self):
        original = self.wire.current['firmware']
        for field in ('uuid', 'hardware', 'firmware'):
            raw = bytearray(original)
            if field == 'uuid': raw[original.index(0, 3)+1] ^= 1
            elif field == 'hardware': raw[3] = ord('X')
            else: raw[2] = 0
            self.wire.current['firmware'] = bytes(raw)
            self.out = self.base/field
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_trial(apply=True)
            self.assertEqual(self.ids()[-1], 0)
            self.assertNotIn(13, self.ids())
            self.assertFalse(json.loads((self.out/'before/manifest.json').read_text())['capture_complete'])

    def test_changed_fresh_motor_app_or_firmware_flags_never_write(self):
        for name in ('motor_configuration', 'app_configuration', 'firmware'):
            self.wire.current = dict(self.artifacts['before'])
            raw = bytearray(self.wire.current[name])
            raw[-2 if name == 'firmware' else 9] ^= 1
            self.wire.current[name] = bytes(raw)
            self.out = self.base/name
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_trial(apply=True)
            self.assertNotIn(13, self.ids())
            self.assertEqual(self.report()['status'], 'rejected_no_settings_sent')

    def test_motion_current_fault_timeout_or_kill_rejected(self):
        # Raw packet offsets from the fixed 74-byte GET_VALUES schema.
        variants = [(23, struct.pack('>i', 1)), (5, struct.pack('>i', 1)),
                    (9, struct.pack('>i', -1)), (53, b'\x01'), (73, b'\x01'), (73, b'\x02')]
        for i, (offset, replacement) in enumerate(variants):
            self.wire.current = dict(self.artifacts['before'])
            raw = bytearray(self.wire.current['telemetry'])
            raw[offset:offset+len(replacement)] = replacement
            self.wire.current['telemetry'] = bytes(raw)
            self.out = self.base/('moving'+str(i))
            with self.subTest(offset=offset, value=replacement), self.assertRaises(ValueError): self.run_trial(apply=True)
            self.assertNotIn(13, self.ids())

    def test_partial_or_exception_write_sends_nothing_further_and_never_retries(self):
        for mode in ('partial', 'exception'):
            self.wire.mode = mode
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/mode
            with self.subTest(mode=mode), self.assertRaises(OSError): self.run_trial(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13])
            self.assertEqual(self.report()['mutating_write_attempts'], 1)
            self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')
            self.assertIn('recovery_skipped', self.report())
            self.assertFalse(self.connection.safe_for_queries)
            with self.assertRaises(RuntimeError): self.connection.query(0)
            with self.assertRaises(RuntimeError): self.connection.set_motor_once(apply.motor_frame(self.artifacts['proposed_motor']), float('inf'))

    def test_missing_or_malformed_ack_allows_only_readonly_recovery_and_never_success(self):
        for mode in ('missing_ack', 'bad_ack'):
            self.wire.mode = mode
            self.wire.current = dict(self.artifacts['before'])
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/mode
            with self.subTest(mode=mode), self.assertRaises((TimeoutError, ValueError)): self.run_trial(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
            self.assertEqual(self.report()['mutating_write_attempts'], 1)
            self.assertTrue(self.report()['recovery_matches_proposal'])
            self.assertFalse(self.report()['ack_verified'])
            self.assertFalse(self.report()['readback_verified'])
            self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')

    def test_readback_motor_or_app_mismatch_never_succeeds_or_rolls_back(self):
        for name in ('motor_configuration', 'app_configuration'):
            self.wire.current = dict(self.artifacts['before'])
            def corrupt(payloads, key=name):
                raw = bytearray(payloads[key]); raw[9] ^= 1; payloads[key] = bytes(raw)
            self.wire.after_change = corrupt
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/('bad-after-'+name)
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_trial(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
            self.assertTrue(self.report()['ack_verified'])
            self.assertFalse(self.report()['readback_verified'])
            self.assertFalse(self.report()['rollback_performed'])

    def test_incomplete_readback_retains_failure_even_if_recovery_matches(self):
        def after_change(_):
            self.wire.missing_query_once = 14
        self.wire.after_change = after_change
        with self.assertRaises(TimeoutError): self.run_trial(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 0, 14, 17, 4])
        self.assertEqual(self.report()['mutating_write_attempts'], 1)
        self.assertTrue(self.report()['ack_verified'])
        self.assertFalse(self.report()['readback_verified'])
        self.assertTrue(self.report()['recovery_matches_proposal'])
        self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')
        self.assertFalse(json.loads((self.out/'after/manifest.json').read_text())['capture_complete'])

    def test_bad_crc_ack_is_not_accepted_as_success(self):
        self.wire.mode = 'missing_ack'
        def wrong_ack(_):
            self.wire.pending.extend(b'\x02\x01\r\x00\x00\x03')
        self.wire.after_change = wrong_ack
        with self.assertRaises(TimeoutError): self.run_trial(apply=True)
        self.assertFalse(self.report()['ack_verified'])
        self.assertFalse(self.report()['readback_verified'])
        self.assertEqual(self.ids().count(13), 1)

    def test_expired_telemetry_rejected_without_even_attempting_write(self):
        with patch.object(apply, 'MAX_TELEMETRY_AGE_S', -1):
            with self.assertRaisesRegex(ValueError, 'expired'): self.run_trial(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4])
        self.assertEqual(self.report()['mutating_write_attempts'], 0)

    def test_expired_whole_capture_rejected_even_with_new_telemetry(self):
        with patch.object(apply, 'MAX_CAPTURE_AGE_S', -1):
            with self.assertRaisesRegex(ValueError, 'expired'): self.run_trial(apply=True)
        self.assertNotIn(13, self.ids())

    def test_trial_tampering_and_postvalidation_changes_fail_closed(self):
        path = self.trial/'proposed_motor_response.bin'
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, 'independently rebuilt'): apply.validate_trial(self.trial)
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.run_trial(apply=True)
        self.assertNotIn(13, self.ids())
        path.write_bytes(original)
        plan_path = self.trial/'trial.json'
        plan = json.loads(plan_path.read_text()); plan['allowlisted_motor_fields'].append('si_motor_poles')
        plan_path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'recomputation'): apply.validate_trial(self.trial)

    def test_partial_read_frame_aborts_without_recovery_or_configuration_write(self):
        self.wire.short_query = 14
        with self.assertRaisesRegex(OSError, 'Partial read-query'): self.run_trial(apply=True)
        self.assertEqual(self.ids(), [0, 14])
        self.assertEqual(self.report()['mutating_write_attempts'], 0)
        self.assertFalse(json.loads((self.out/'before/manifest.json').read_text())['capture_complete'])

    def test_existing_evidence_or_trial_destination_rejected_before_open(self):
        self.out.mkdir()
        for out in (self.out, self.trial/'new-evidence'):
            with patch.object(apply, 'SerialConnection') as connection, self.assertRaises((ValueError, FileExistsError)):
                apply.main([str(self.trial), '--preflight-only', '--port', '/no-port', '--out', str(out)])
            connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
