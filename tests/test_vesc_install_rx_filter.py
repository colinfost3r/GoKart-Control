import binascii
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
import install_rx_filter as r

# Immutable committed successful RAM-trial payloads. Rollback evidence below is synthetic.
RAW = ROOT / 'hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/preflight/raw'
APP = (RAW / 'app_configuration.bin').read_bytes()
MOTOR = (RAW / 'motor_configuration.bin').read_bytes()
IDENTITY = (RAW / 'firmware.bin').read_bytes()
TELEMETRY = bytearray((RAW/'telemetry.bin').read_bytes())
struct.pack_into('>i', TELEMETRY, 23, 0)
TELEMETRY[53] = 0
TELEMETRY = bytes(TELEMETRY)


class Connection:
    fd = 91
    def __init__(self, port): pass
    def __enter__(self): return self
    def __exit__(self, *unused): pass


class FakeWire:
    def __init__(self):
        self.actions = []
        self.flash = bytearray(b'\xff' * r.SECTOR_BYTES)
        self.erased = False
        self.identity, self.app, self.motor = IDENTITY, APP, MOTOR
        self.status = '(gk-rx-status nil nil -1 -1 1 {0.0871} {0.000000} 0)'
        self.context_active = False
        self.existing = False
        self.fail_action = None
        self.fail_offset = None
        self.bad_ack_offset = None
        self.corrupt_readback = False
        self.status_count = 0
        self.unsafe_final = False
        self.final_status = None
        self.delay_final_empty = False
        self.clock = 1000.0
    def blob(self):
        if self.existing: return b'existing code'
        length, crc, flags = struct.unpack('>IHH', self.flash[:8])
        if length <= 0 or length > r.SECTOR_BYTES-8: return b''
        result = bytes(self.flash[8:8+length])
        return result if binascii.crc_hqx(bytes(self.flash[6:8]) + result, 0) == crc else b''
    def query(self, action, offset=0, length=0):
        self.actions.append((action, offset, length))
        if action == self.fail_action and (self.fail_offset is None or offset == self.fail_offset):
            raise IOError('Uncertain serial delivery')
        if action == 'identity': return self.identity
        if action == 'app': return self.app
        if action == 'motor': return self.motor
        if action == 'telemetry': return TELEMETRY
        if action == 'read':
            if self.delay_final_empty and not self.erased: self.clock += 1.0
            blob = self.blob()
            data = blob[offset:offset+length]
            if length and self.corrupt_readback:
                data = bytes((data[0] ^ 1,)) + data[1:]
            return b'\x82' + struct.pack('>ii', len(blob), offset if blob else 0) + data
        if action == 'erase':
            self.flash[:] = b'\xff' * r.SECTOR_BYTES
            self.erased = True
            return b'\x84\x01'
        if action == 'write':
            command = r.payload('write', offset)
            self.flash[offset:offset+len(command[5:])] = command[5:]
            return b'\x83\x01' + struct.pack('>I', self.bad_ack_offset if self.bad_ack_offset is not None else offset)
        raise AssertionError(action)
    def expression(self, action, seconds=1.0):
        self.actions.append((action, 0, 0))
        if self.erased: raise AssertionError('No globals/REPL after erase')
        if action == 'status':
            self.status_count += 1
            if self.final_status is not None and self.status_count == 5:
                return r.control.Capture([b'\x87' + self.final_status.encode()], quiet_tail_seconds=0.3)
            if self.unsafe_final and self.status_count == 5:
                return r.control.Capture([b'\x87(gk-rx-status nil nil -1 -1 0 {0.0871} {0.0} 0)'], quiet_tail_seconds=0.5)
        text = self.status if action == 'status' else '\n'.join(r.control.context_summary.__globals__['HEADINGS'])
        if action == 'contexts' and self.context_active: text += '\nContextID: 41'
        return r.control.Capture([b'\x87' + text.encode()], quiet_tail_seconds=0.5)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'capture'
        self.wire = FakeWire()
        self.rollback = Path(self.temp.name) / 'synthetic-rollback'
        self.rollback.mkdir()
        identity = r.require_target(IDENTITY)
        manifest = {'test_fixture': 'synthetic rollback; no physical action',
                    'action': 'rollback', 'complete': True, 'lifecycle_sent': True,
                    'status_after': {'run': False, 'active': False, 'pid': -1, 'applied': -1, 'rx': 1},
                    'identity_before': identity, 'identity_after': identity,
                    'finished_utc': '2026-11-11T00:00:00+00:00'}
        (self.rollback/'manifest.json').write_text(json.dumps(manifest))
        (self.rollback/'app_after.bin').write_bytes(APP)
        (self.rollback/'motor_after.bin').write_bytes(MOTOR)
    def invoke(self, **overrides):
        kwargs = {'apply': True, 'supervised': True, 'connection_factory': Connection,
                  'wire_factory': lambda *args: self.wire}
        kwargs.update(overrides)
        return r.install('FAKE', self.out, self.rollback/'manifest.json', **kwargs)
    def test_exact_canonical_package_header_crc_hash(self):
        image = r.package()
        self.assertEqual(len(image), 3992)
        self.assertEqual(image[:8].hex(), '00000f90af410000')
        self.assertEqual(r.digest(image), r.IMAGE_SHA256)
        self.assertEqual(r.digest(image[8:]), r.BLOB_SHA256)
        self.assertEqual(image[-3:], b'\0\0\0')
    def test_offline_default_never_opens_port(self):
        result = self.invoke(apply=False, connection_factory=lambda port: self.fail('opened'))
        self.assertTrue(result['offline_only'])
        self.assertFalse(self.out.exists())
        self.assertEqual(self.wire.actions, [])
    def test_supervised_flag_required_before_hardware(self):
        with self.assertRaises(ValueError): self.invoke(supervised=False)
        self.assertEqual(self.wire.actions, [])
    def test_exact_fixed_payload_bounds_and_no_activation(self):
        self.assertEqual(r.payload('erase'), bytes.fromhex('8400000f98'))
        self.assertEqual(r.payload('write', 0), b'\x83' + bytes(4) + r.package()[:8])
        for offset in r.WRITE_OFFSETS:
            data = r.payload('write', offset)
            self.assertLessEqual(len(data[5:]), 256)
            self.assertLessEqual(offset + len(data[5:]), r.SECTOR_BYTES)
            self.assertEqual(r.control.PacketParser().feed(r.frame('write', offset)), [data])
        for action in ('activate', 'set-running', 'start', 'stop', 'rollback', 'reset', 'set-current', 'set-config'):
            with self.assertRaises(ValueError): r.payload(action)
        for offset in (-1, 1, 2, 4, 7, 9, 131072, True):
            with self.assertRaises(ValueError): r.payload('write', offset)
    def test_read_bounds(self):
        for offset, length in ((-1, 1), (0, -1), (0, 257), (3984, 1), (1, 0), (False, 0)):
            with self.assertRaises(ValueError): r.payload('read', offset, length)
    def test_changed_package_refused_before_hardware(self):
        bad = Path(self.temp.name)/'bad.bin'
        original = r.SOURCE.read_bytes()
        for changed in (original[:-1], original[:-1] + bytes((original[-1] ^ 1,))):
            bad.write_bytes(changed)
            with patch.object(r, 'SOURCE', bad):
                with self.assertRaises(ValueError): self.invoke()
            self.assertEqual(self.wire.actions, [])
    def test_rollback_manifest_must_show_completed_restore(self):
        bad = Path(self.temp.name)/'bad.json'
        bad.write_text(json.dumps({'action': 'stop', 'complete': True}))
        with self.assertRaises(ValueError): r.require_rollback(bad)
    def test_wrong_identity_no_erase(self):
        bad = bytearray(IDENTITY)
        bad[2] = 0
        self.wire.identity = bytes(bad)
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.wire.actions, [('identity', 0, 0)])
    def test_wrong_build_or_test_firmware_no_erase(self):
        wrong_name = IDENTITY.replace(b'no_hw_limits', b'no_hw_limitx')
        wrong_test = bytearray(IDENTITY)
        name_end = IDENTITY.index(b'\0', 3)
        wrong_test[name_end + 1 + 12 + 1] = 1
        for index, data in enumerate((wrong_name, bytes(wrong_test))):
            self.wire = FakeWire()
            self.wire.identity = data
            self.out = Path(self.temp.name)/('build'+str(index))
            with self.assertRaises(ValueError): self.invoke()
            self.assertEqual(self.wire.actions, [('identity', 0, 0)])
    def test_final_raw_check_change_refuses_erase(self):
        self.wire.unsafe_final = True
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.wire.status_count, 5)
        self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_final_pedal_or_active_change_refuses_erase(self):
        for index, text in enumerate(('(gk-rx-status nil nil -1 -1 1 {0.13} {0.0} 0)',
                                     '(gk-rx-status t t 41 0 1 {0.0871} {0.0} 0)')):
            self.wire = FakeWire()
            self.wire.final_status = text
            self.out = Path(self.temp.name)/('final'+str(index))
            with self.assertRaises(ValueError): self.invoke()
            self.assertEqual(self.wire.status_count, 5)
            self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_delayed_final_empty_read_refuses_erase(self):
        self.wire.delay_final_empty = True
        with patch.object(r.time, 'monotonic', side_effect=lambda: self.wire.clock):
            with self.assertRaises(TimeoutError): self.invoke()
        self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_changed_app_or_motor_no_erase(self):
        for field in ('app', 'motor'):
            self.wire = FakeWire()
            original = getattr(self.wire, field)
            setattr(self.wire, field, original[:-1] + bytes((original[-1] ^ 1,)))
            self.out = Path(self.temp.name)/field
            with self.assertRaises(ValueError): self.invoke()
            self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_active_wrong_raw_or_pressed_pedal_no_erase(self):
        for index, text in enumerate(('(gk-rx-status t t 41 0 1 {0.087} {0.0} 0)',
                                     '(gk-rx-status nil nil -1 -1 0 {0.087} {0.0} 0)',
                                     '(gk-rx-status nil nil -1 -1 1 {0.13} {0.0} 0)')):
            self.wire = FakeWire()
            self.wire.status = text
            self.out = Path(self.temp.name)/str(index)
            with self.assertRaises(ValueError): self.invoke()
            self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_contexts_or_existing_code_refuse_erase(self):
        for field in ('context_active', 'existing'):
            self.wire = FakeWire()
            setattr(self.wire, field, True)
            self.out = Path(self.temp.name)/field
            with self.assertRaises(ValueError): self.invoke()
            self.assertFalse(any(action == 'erase' for action, _, _ in self.wire.actions))
    def test_success_body_then_header_exact_readback_no_activation(self):
        result = self.invoke()
        writes = [offset for action, offset, _ in self.wire.actions if action == 'write']
        self.assertEqual(writes, list(r.BODY_OFFSETS) + [0])
        self.assertEqual(self.wire.actions.count(('erase', 0, 0)), 1)
        self.assertEqual(self.wire.flash[:3992], r.package())
        self.assertEqual((self.out/'code-readback.bin').read_bytes(), r.package()[8:])
        self.assertTrue(result['complete'])
        self.assertFalse(result['activation_sent'])
        self.assertFalse(result['settings_written'])
        self.assertTrue(result['all_376_settings_preserved'])
        self.assertEqual(result['phase'], 'stored_verified_not_activated')
    def test_ack_requires_exact_status_length_offset(self):
        r.check_ack('erase', b'\x84\x01')
        r.check_ack('write', b'\x83\x01' + struct.pack('>I', 8), 8)
        for action, ack, offset in (('erase', b'\x84\x00', 0), ('erase', b'\x84\x01\x00', 0),
                                    ('write', b'\x83\x00' + struct.pack('>I', 8), 8),
                                    ('write', b'\x83\x01' + struct.pack('>I', 0), 8)):
            with self.assertRaises(ValueError): r.check_ack(action, ack, offset)
    def test_uncertain_erase_or_write_never_retried(self):
        for action, offset in (('erase', None), ('write', 8), ('write', 0)):
            self.wire = FakeWire()
            self.wire.fail_action, self.wire.fail_offset = action, offset
            self.out = Path(self.temp.name)/(action+str(offset))
            with self.assertRaises(IOError): self.invoke()
            self.assertEqual(self.wire.actions[-1], (action, offset or 0, 0))
            self.assertEqual(self.wire.actions.count((action, offset or 0, 0)), 1)
            self.assertFalse(json.loads((self.out/'manifest.json').read_text())['complete'])
    def test_wrong_write_ack_stops_before_next_chunk(self):
        self.wire.bad_ack_offset = 264
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.wire.actions[-1], ('write', 8, 0))
    def test_corrupt_readback_never_activates_or_cleans_up(self):
        self.wire.corrupt_readback = True
        with self.assertRaises(ValueError): self.invoke()
        result = json.loads((self.out/'manifest.json').read_text())
        self.assertFalse(result['complete'])
        self.assertFalse(result['activation_sent'])
        self.assertEqual(self.wire.actions.count(('erase', 0, 0)), 1)


class WireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.wire = r.Wire(91, self.out)
    def test_partial_write_once_full_attempt_journal(self):
        with patch.object(r.os, 'write', return_value=3) as write:
            with self.assertRaises(IOError): self.wire.send('write', 8)
        write.assert_called_once_with(91, r.frame('write', 8))
        self.assertEqual((self.out/'tx-attempts.bin').read_bytes(), r.frame('write', 8))
    def test_crc_fragmented_ack_retained(self):
        data = b'\x83\x01' + struct.pack('>I', 8)
        response = bytes((2, len(data))) + data + struct.pack('>H', binascii.crc_hqx(data, 0)) + b'\x03'
        with patch.object(r.os, 'write', side_effect=lambda fd, data: len(data)), patch.object(r.control.select, 'select', return_value=([91], [], [])), patch.object(r.os, 'read', side_effect=[response[:3], response[3:]]):
            answer = self.wire.query('write', 8)
        r.check_ack('write', answer, 8)
        self.assertEqual((self.out/'rx-wire.bin').read_bytes(), response)


if __name__ == '__main__': unittest.main()
