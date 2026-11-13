import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
import rx_filter_control as r

# Immutable, tracked kart-3 runtime fixture; app payload matches the reviewed trial.
RAW = ROOT / 'hardware/vesc/kart3/2026-11-10/usb-prewrite-connected/raw'
APP = (RAW / 'app_configuration.bin').read_bytes()
MOTOR = (RAW / 'motor_configuration.bin').read_bytes()
IDENTITY = (RAW / 'firmware.bin').read_bytes()
TELEMETRY = bytearray((RAW / 'telemetry.bin').read_bytes())
struct.pack_into('>i', TELEMETRY, 23, 0)
TELEMETRY[53] = 0
TELEMETRY = bytes(TELEMETRY)


def status(run='nil', active='nil', pid=-1, applied=-1, rx=1, adc='{0.089019}', rpm='{0.000014}', fault=0):
    return f'(gk-rx-status {run} {active} {pid} {applied} {rx} {adc} {rpm} {fault})'


def packet(text):
    return r.Capture([b'\x87' + text.encode()], quiet_tail_seconds=0.5)


class Connection:
    fd = 91
    def __init__(self, port): pass
    def __enter__(self): return self
    def __exit__(self, *unused): pass


class FakeWire:
    def __init__(self, action):
        self.action = action
        self.actions = []
        self.did_action = False
        self.initial = status() if action in ('start', 'status') else status('t' if action == 'stop' else 'nil', 't', 41 if action == 'stop' else -1, 0)
        self.identity, self.app, self.motor, self.telemetry = IDENTITY, APP, MOTOR, TELEMETRY
        self.bad_sample = None
        self.samples = 0
        self.fail_action = False
        self.missing_pid = False
        self.after_app = APP
    def query(self, action):
        self.actions.append(action)
        if action == 'identity': return self.identity
        if action == 'app': return self.after_app if self.did_action else self.app
        if action == 'motor': return self.motor
        if action == 'telemetry':
            self.samples += 1
            return self.bad_sample if self.samples == 3 and self.bad_sample is not None else self.telemetry
        raise AssertionError(action)
    def expression(self, action, seconds=1.0):
        self.actions.append(action)
        if action == 'status':
            if not self.did_action: return packet(self.initial)
            if self.action == 'start': return packet(status('t', 't', 41, 0))
            if self.action == 'stop': return packet(status('nil', 't', -1, 0))
            return packet(status())
        if action == 'contexts':
            text = '\n'.join(r.context_summary.__globals__['HEADINGS'])
            has_pid = ((not self.did_action and self.action == 'stop') or (self.did_action and self.action == 'start'))
            if has_pid and not self.missing_pid: text += '\nContextID: 41'
            return packet(text)
        if action in ('start', 'stop', 'rollback'):
            self.did_action = True
            if self.fail_action: raise IOError('Uncertain command send')
            return packet(f'(gk-rx-{action}-result {41 if action == "start" else "t"})')
        raise AssertionError(action)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'capture'
        self.hash_patch = patch.object(r, 'CANDIDATE_SHA256', 'a' * 64)
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.sleep_patch = patch.object(r.time, 'sleep')
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)
    def invoke(self, action, wire=None, **options):
        wire = wire or FakeWire(action)
        kwargs = {'setup_confirmed': True, 'loaded_reviewed': True, 'expected_rx': 1}
        kwargs.update(options)
        result = r.run('FAKE', self.out, action, connection_factory=Connection,
                       wire_factory=lambda *args: wire, **kwargs)
        return result, wire
    def test_fixed_allowlist_frames_no_motor_config_flash_reset_load(self):
        for action in tuple(r.READS) + tuple(r.EXPRESSIONS):
            self.assertEqual(r.PacketParser().feed(r.frame(action)), [r.payload(action)])
            self.assertIn(r.payload(action)[0], (0, 4, 14, 17, 138))
        for action in ('load', 'stream', 'reset', 'set-current', 'flash', 'config', 'eval'):
            with self.assertRaises(ValueError): r.payload(action)
    def test_actual_braced_status_and_invalid_values(self):
        parsed = r.parse_status(packet(status()))
        self.assertEqual(parsed['adc'], 0.089019)
        self.assertEqual(parsed['erpm'], 0.000014)
        for text in (status(adc='{nan}'), status(rpm='{1e999}'), status(adc='{0.09'), 'Error in ' + status(), status() + '\n' + status()):
            with self.assertRaises(ValueError): r.parse_status(packet(text))
    def test_real_full_application_hash_and_all_fields(self):
        result = r.require_app(APP)
        self.assertEqual(len(result['values']), 187)
        changed = bytearray(APP)
        changed[-1] ^= 1
        with self.assertRaises(ValueError): r.require_app(bytes(changed))
    def test_start_requires_explicit_setup(self):
        wire = FakeWire('start')
        with self.assertRaises(ValueError): self.invoke('start', wire, setup_confirmed=False)
        self.assertEqual(wire.actions, [])
    def test_unreviewed_load_or_pending_hash_refused(self):
        with self.assertRaises(ValueError): self.invoke('start', loaded_reviewed=False)
        with patch.object(r, 'CANDIDATE_SHA256', 'PENDING_REVIEWED_FIXES'):
            with self.assertRaises(ValueError): self.invoke('start')
    def test_wrong_identity_before_lifecycle(self):
        wire = FakeWire('start')
        raw = bytearray(IDENTITY)
        raw[2] = 0
        wire.identity = bytes(raw)
        with self.assertRaises(ValueError): self.invoke('start', wire)
        self.assertEqual(wire.actions, ['identity'])
    def test_changed_application_blocks_start(self):
        wire = FakeWire('start')
        wire.app = APP[:-1] + bytes((APP[-1] ^ 1,))
        with self.assertRaises(ValueError): self.invoke('start', wire)
        self.assertNotIn('start', wire.actions)
    def test_start_four_samples_then_verified_worker_direction(self):
        result, wire = self.invoke('start')
        self.assertTrue(result['complete'])
        self.assertEqual(wire.actions.count('telemetry'), 4)
        self.assertEqual(wire.actions.count('start'), 1)
        self.assertTrue(result['status_after']['active'])
        self.assertEqual(result['status_after']['applied'], 0)
        self.assertFalse(result['native_detach_independently_readable'])
    def test_single_bad_telemetry_sample_blocks_start(self):
        wire = FakeWire('start')
        sample = bytearray(TELEMETRY)
        struct.pack_into('>i', sample, 23, 51)
        wire.bad_sample = bytes(sample)
        with self.assertRaises(ValueError): self.invoke('start', wire)
        self.assertEqual(wire.samples, 3)
        self.assertNotIn('start', wire.actions)
    def test_pressed_pedal_or_wrong_switch_blocks_start(self):
        for index, text in enumerate((status(adc='{0.13}'), status(rx=0), status(rpm='{50.1}'), status(fault=1))):
            wire = FakeWire('start')
            wire.initial = text
            self.out = Path(self.temp.name) / str(index)
            with self.assertRaises(ValueError): self.invoke('start', wire)
            self.assertNotIn('start', wire.actions)
    def test_existing_active_filter_refuses_second_start(self):
        wire = FakeWire('start')
        wire.initial = status('t', 't', 41, 0)
        with self.assertRaises(ValueError): self.invoke('start', wire)
        self.assertNotIn('start', wire.actions)
    def test_missing_live_pid_after_start_is_uncertain_no_cleanup(self):
        wire = FakeWire('start')
        wire.missing_pid = True
        with self.assertRaises(RuntimeError): self.invoke('start', wire)
        self.assertEqual(wire.actions.count('start'), 1)
        self.assertNotIn('stop', wire.actions)
        self.assertNotIn('rollback', wire.actions)
        self.assertIn('qualify later', json.loads((self.out/'manifest.json').read_text())['start_warning'])
    def test_ambiguous_send_never_retried_or_rolled_back(self):
        wire = FakeWire('start')
        wire.fail_action = True
        with self.assertRaises(IOError): self.invoke('start', wire)
        self.assertEqual(wire.actions.count('start'), 1)
        self.assertNotIn('stop', wire.actions)
        self.assertNotIn('rollback', wire.actions)
    def test_stop_holds_direction_does_not_restore_raw(self):
        result, wire = self.invoke('stop', setup_confirmed=False, expected_rx=None)
        self.assertTrue(result['complete'])
        self.assertFalse(result['status_after']['run'])
        self.assertTrue(result['status_after']['active'])
        self.assertEqual(result['status_after']['applied'], 0)
        self.assertEqual(wire.actions.count('stop'), 1)
        self.assertNotIn('rollback', wire.actions)
    def test_rollback_requires_matching_raw_at_rest(self):
        wire = FakeWire('rollback')
        wire.initial = status('nil', 't', -1, 1, rx=1)
        with self.assertRaises(ValueError): self.invoke('rollback', wire)
        self.assertNotIn('rollback', wire.actions)
    def test_rollback_success_is_separate(self):
        result, wire = self.invoke('rollback')
        self.assertTrue(result['complete'])
        self.assertFalse(result['status_after']['active'])
        self.assertEqual(result['status_after']['applied'], -1)
        self.assertNotIn('stop', wire.actions)
    def test_after_application_drift_is_reported(self):
        wire = FakeWire('start')
        wire.after_app = APP[:-1] + bytes((APP[-1] ^ 1,))
        with self.assertRaises(ValueError): self.invoke('start', wire)
        self.assertEqual(wire.actions.count('start'), 1)
        self.assertFalse(json.loads((self.out/'manifest.json').read_text())['complete'])
    def test_status_sends_no_lifecycle_command(self):
        result, wire = self.invoke('status', loaded_reviewed=False, setup_confirmed=False)
        self.assertTrue(result['complete'])
        self.assertFalse(result['lifecycle_sent'])
        self.assertFalse(set(wire.actions) & {'start', 'stop', 'rollback'})


class WireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.wire = r.Wire(91, self.out)
    def test_partial_lifecycle_send_is_one_attempt(self):
        with patch.object(r.os, 'write', return_value=2) as write:
            with self.assertRaises(IOError): self.wire.send('start')
        write.assert_called_once_with(91, r.frame('start'))
        self.assertEqual((self.out / 'tx-attempts.bin').read_bytes(), r.frame('start'))
    def test_crc_fragmented_real_format_status_is_logged(self):
        data = b'\x87' + status().encode()
        raw = bytes((2, len(data))) + data + struct.pack('>H', r.binascii.crc_hqx(data, 0)) + b'\x03'
        with patch.object(r.select, 'select', return_value=([91], [], [])), patch.object(r.os, 'read', side_effect=[raw[:5], raw[5:]]):
            decoded = self.wire.packet(r.time.monotonic() + 1)
        self.assertEqual(r.parse_status(r.Capture([decoded]))['adc'], 0.089019)
        self.assertEqual((self.out / 'rx-wire.bin').read_bytes(), raw)
    def test_pending_data_or_expired_session_refuses_send(self):
        self.wire.parser.buffer.extend(b'\x02')
        with patch.object(r.os, 'write') as write:
            with self.assertRaises(ValueError): self.wire.send('start')
            self.wire.parser.buffer.clear()
            self.wire.deadline = 0
            with self.assertRaises(TimeoutError): self.wire.send('start')
            write.assert_not_called()


if __name__ == '__main__': unittest.main()
