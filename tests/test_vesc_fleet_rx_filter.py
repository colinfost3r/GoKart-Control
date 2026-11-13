"""Kart-4/5 reverse-filter tool tests with a fake wire; never open hardware.

Captures are SYNTHETIC copies of kart-3 evidence with an invented UUID and altered limits.
"""
import binascii
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
sys.path.insert(0, str(ROOT / 'tests'))
import fleet_rx_filter as flt
import prepare_fleet_kart as fleet
from rx_probe import Capture, HEADINGS
from test_vesc_prepare_fleet_kart import FAKE_UUID, SOURCE, TARGET, fixture, motor_field, uuid_field

OTHER_UUID = '0c0b0a090807060504030201'
REST = '(pins 1 1 {0.0871} {0.000000} 0)'
ARMED = '(gk-rx-status t t 1507 0 1 {0.0871} {0.000000} 0)'


class Connection:
    fd = 91
    def __init__(self, port): pass
    def __enter__(self): return self
    def __exit__(self, *unused): pass


class FakeWire:
    def __init__(self, bundle):
        self.package = bundle['package']
        self.actions = []
        self.flash = bytearray(b'\xff' * flt.SECTOR_BYTES)
        self.erased = False
        self.identity = bundle['artifacts']['before']['firmware']
        self.app = bundle['artifacts']['before']['app_configuration']
        self.motor = bundle['artifacts']['proposed_motor']
        self.telemetry = bundle['artifacts']['before']['telemetry']
        self.snapshots = []          # consumed first; then self.snapshot repeats
        self.snapshot = REST
        self.statuses = []           # consumed first; then self.status repeats
        self.status = ARMED
        self.erase_does_nothing = False
        self.app_changes_after_erase = False
        self.slow_telemetry_from = None   # index of the first telemetry read that takes a second
        self.context_active = False
        self.existing = False
        self.fail_action = None
        self.fail_offset = None
        self.bad_ack_offset = None
        self.corrupt_readback = False
        self.delay_final_empty = False
        self.clock = 1000.0
        self.erase_deadline = None

    def store(self):
        self.flash[:len(self.package.image)] = self.package.image

    def blob(self):
        if self.existing: return b'existing code'
        length, crc, flags = struct.unpack('>IHH', self.flash[:8])
        if length <= 0 or length > flt.SECTOR_BYTES - 8: return b''
        result = bytes(self.flash[8:8 + length])
        return result if binascii.crc_hqx(bytes(self.flash[6:8]) + result, 0) == crc else b''

    def query(self, action, offset=0, length=0):
        self.actions.append((action, offset, length))
        self.package.payload(action, offset, length)   # every request must be one the tool can build
        if action == self.fail_action and (self.fail_offset is None or offset == self.fail_offset):
            raise IOError('Uncertain serial delivery')
        if action == 'identity': return self.identity
        if action == 'app':
            if self.erased and self.app_changes_after_erase: return self.app[:-1] + bytes((self.app[-1] ^ 1,))
            return self.app
        if action == 'motor': return self.motor
        if action == 'telemetry':
            if self.slow_telemetry_from is not None and len(self.sent('telemetry')) > self.slow_telemetry_from:
                self.clock += 1.0
            return self.telemetry
        if action == 'read':
            if self.delay_final_empty and not self.erased: self.clock += 1.0
            blob = self.blob()
            data = blob[offset:offset + length]
            if length and self.corrupt_readback:
                data = bytes((data[0] ^ 1,)) + data[1:]
            return b'\x82' + struct.pack('>ii', len(blob), offset if blob else 0) + data
        if action == 'erase':
            if not self.erase_does_nothing: self.flash[:] = b'\xff' * flt.SECTOR_BYTES
            self.erased = True
            return b'\x84\x01'
        if action == 'write':
            command = self.package.payload('write', offset)
            self.flash[offset:offset + len(command[5:])] = command[5:]
            return b'\x83\x01' + struct.pack('>I', self.bad_ack_offset if self.bad_ack_offset is not None else offset)
        raise AssertionError(action)

    def expression(self, action, seconds=1.0):
        self.actions.append((action, 0, 0))
        self.package.payload(action)
        if self.erased and action != 'status': raise AssertionError('No REPL between erase and the end of an install')
        if action == 'snapshot':
            text = self.snapshots.pop(0) if self.snapshots else self.snapshot
        elif action == 'status':
            if self.erased: raise AssertionError('No REPL after an erase: it could start the interpreter again')
            text = self.statuses.pop(0) if self.statuses else self.status
        else:
            text = '\n'.join(HEADINGS) + ('\nContextID: 41' if self.context_active else '')
        return Capture([b'\x87' + text.encode()], quiet_tail_seconds=0.5)

    def sent(self, name):
        return [a for a in self.actions if a[0] == name]


class FleetFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_class = tempfile.TemporaryDirectory()
        base = Path(cls.temp_class.name)
        cls.source = fixture(base / 'source', SOURCE)
        cls.target = fixture(base / 'target', TARGET)
        motor_field(cls.source, 'l_current_min', -5)
        uuid_field(cls.target, FAKE_UUID)
        for field, value in (('l_in_current_min', -200.0), ('l_max_vin', 84.0)):
            motor_field(cls.target, field, value)
        cls.plan, cls.artifacts = fleet.prepare(cls.source, cls.target, kart_id=4, target_uuid=FAKE_UUID, protection_limits=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_class.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.package_dir = self.base / 'package'
        fleet.write_plan(self.plan, self.artifacts, self.package_dir)
        self.bundle = flt.load_package(self.package_dir, kart_id=4, expected_uuid=FAKE_UUID)
        self.package = self.bundle['package']
        self.sha = flt.sha256(self.package.blob)
        self.wire = FakeWire(self.bundle)
        self.out = self.base / 'evidence'

    def factories(self):
        return {'connection_factory': Connection, 'wire_factory': lambda *args: self.wire}

    def install(self, **overrides):
        kwargs = {'apply': True, 'supervised': True, **self.factories()}
        kwargs.update(overrides)
        return flt.install('FAKE', self.out, self.bundle, **kwargs)

    def manifest(self):
        return json.loads((self.out / 'manifest.json').read_text())

    def fresh(self, name):
        self.wire = FakeWire(self.bundle)
        self.out = self.base / name
        return self.wire

    def cli(self, action, *extra):
        return [action, str(self.package_dir), '--kart-id', '4', '--expected-uuid', FAKE_UUID, *extra]

    # ---- the package and what the tool can send
    def test_script_is_the_tested_core_with_only_this_controllers_uuid(self):
        template = fleet.FILTER_SOURCE.read_bytes()
        blob, image = self.package.blob, self.package.image
        self.assertEqual(blob[:fleet.FILTER_CORE_BYTES], template[:fleet.FILTER_CORE_BYTES])
        self.assertIn(b"'(1 2 3 4 5 6 7 8 9 10 11 12)", blob)
        self.assertNotIn(b"'(55 0 78 0 9 81 52 48 55 53 55 57)", blob)
        self.assertEqual(blob[-3:], b'\0\0\0')
        self.assertEqual(image[:8], struct.pack('>IH', len(blob), binascii.crc_hqx(b'\0\0' + blob, 0)) + b'\0\0')
        self.assertEqual(self.sha, self.plan['filter']['code_blob_sha256'])
        self.assertEqual(self.package.write_offsets[-1], 0)

    def test_only_fixed_frames_can_be_built_and_none_activates(self):
        self.assertEqual(self.package.payload('erase'), b'\x84' + struct.pack('>i', len(self.package.image)))
        self.assertEqual(self.package.payload('write', 0), b'\x83' + bytes(4) + self.package.image[:8])
        for offset in self.package.write_offsets:
            data = self.package.payload('write', offset)
            self.assertLessEqual(len(data[5:]), 256)
            self.assertEqual(flt.control.PacketParser().feed(self.package.frame('write', offset)), [data])
        for action in ('activate', 'set-running', 'start', 'stop', 'rollback', 'reset', 'set-current', 'set-config', 'monitor'):
            with self.subTest(action=action), self.assertRaises(ValueError): self.package.payload(action)
        for offset in (-1, 1, 2, 4, 7, 9, 131072, True):
            with self.subTest(offset=offset), self.assertRaises(ValueError): self.package.payload('write', offset)
        for offset, length in ((-1, 1), (0, -1), (0, 257), (len(self.package.blob), 1), (1, 0), (False, 0)):
            with self.subTest(read=(offset, length)), self.assertRaises(ValueError): self.package.payload('read', offset, length)
        for name in ('snapshot', 'contexts', 'status'):
            self.assertEqual(self.package.payload(name)[0], 0x8a)
        self.assertNotIn(b'gk-rx-filter-start', b''.join(flt.EXPRESSIONS.values()))
        self.assertNotIn(b'setvar', b''.join(flt.EXPRESSIONS.values()))

    def test_ack_requires_exact_status_length_offset(self):
        flt.check_ack('erase', b'\x84\x01')
        flt.check_ack('write', b'\x83\x01' + struct.pack('>I', 8), 8)
        for action, ack, offset in (('erase', b'\x84\x00', 0), ('erase', b'\x84\x01\x00', 0),
                                    ('write', b'\x83\x00' + struct.pack('>I', 8), 8),
                                    ('write', b'\x83\x01' + struct.pack('>I', 0), 8), ('read', b'\x84\x01', 0)):
            with self.subTest(ack=ack), self.assertRaises(ValueError): flt.check_ack(action, ack, offset)

    # ---- binding
    def test_package_is_bound_to_its_kart_uuid_and_exact_script(self):
        with self.assertRaisesRegex(ValueError, 'different kart ID'):
            flt.load_package(self.package_dir, kart_id=5, expected_uuid=FAKE_UUID)
        with self.assertRaisesRegex(ValueError, 'different controller UUID'):
            flt.load_package(self.package_dir, kart_id=4, expected_uuid=OTHER_UUID)
        for uuid in sorted(fleet.RESERVED_UUIDS):
            with self.subTest(uuid=uuid), self.assertRaisesRegex(ValueError, 'reserved'):
                flt.load_package(self.package_dir, kart_id=4, expected_uuid=uuid)
        for name in ('rx-filter-codeblob.bin', 'rx-filter-autostart.lisp'):
            path = self.package_dir / name
            original = path.read_bytes()
            path.write_bytes(original.replace(b'0.12', b'0.92', 1))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'independently rebuilt'):
                flt.load_package(self.package_dir, kart_id=4, expected_uuid=FAKE_UUID)
            path.write_bytes(original)
        flt.load_package(self.package_dir, kart_id=4, expected_uuid=FAKE_UUID)

    def test_package_changed_after_validation_sends_nothing(self):
        path = self.package_dir / 'rx-filter-codeblob.bin'
        path.write_bytes(path.read_bytes().replace(b'0.12', b'0.92', 1))
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.install()
        self.assertEqual(self.wire.actions, [])
        self.assertFalse(self.out.exists())

    # ---- command line
    def test_plan_is_offline_and_install_needs_every_flag(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(flt.main(self.cli('plan')), 0)
        plan = json.loads(out.getvalue())
        self.assertTrue(plan['offline_only'])
        self.assertEqual(plan['blob_sha256'], self.sha)
        self.assertFalse(plan['activation_command_available'])
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(flt.main(self.cli('install')), 0)
        self.assertTrue(json.loads(out.getvalue())['offline_only'])
        bad = (('install', '--apply', '--supervised', '--port', '/no-port', '--out', str(self.out)),
               ('install', '--expect-blob-sha256', self.sha),
               ('install', '--apply', '--supervised', '--expect-blob-sha256', self.sha, '--port', '/no-port'),
               ('plan', '--port', '/no-port'), ('plan', '--apply'), ('observe',), ('status', '--port', '/no-port', '--out', str(self.out)))
        for args in bad:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                flt.main(self.cli(*args))
        for stated in ('0' * 64, 'nope'):
            with self.subTest(stated=stated), self.assertRaisesRegex(ValueError, 'no device opened'):
                flt.main(self.cli('install', '--apply', '--supervised', '--expect-blob-sha256', stated,
                                  '--port', '/no-port', '--out', str(self.out)))
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            flt.main(['plan', str(self.package_dir), '--kart-id', '3', '--expected-uuid', FAKE_UUID])
        self.assertFalse(self.out.exists())

    def test_evidence_must_be_new_and_outside_the_package(self):
        self.out.mkdir()
        for out in (self.out, self.package_dir / 'new', self.target / 'new'):
            with self.subTest(out=out), self.assertRaises((ValueError, FileExistsError)):
                flt.main(self.cli('observe', '--port', '/no-port', '--out', str(out)))

    def test_supervised_flag_required_before_hardware(self):
        with self.assertRaises(ValueError): self.install(supervised=False)
        self.assertEqual(self.wire.actions, [])
        result = self.install(apply=False, connection_factory=lambda port: self.fail('opened'))
        self.assertTrue(result['offline_only'])
        self.assertFalse(self.out.exists())

    # ---- install refusals
    def test_kart_3_or_any_other_controller_on_the_wire_is_refused_at_identity(self):
        wrong_build = self.wire.identity.replace(b'no_hw_limits', b'no_hw_limitx')
        other = bytearray(self.wire.identity); other[other.index(0, 3) + 1] ^= 1
        for name, identity in (('kart3', (self.source / 'firmware.bin').read_bytes()), ('other', bytes(other)), ('build', wrong_build)):
            self.fresh(name).identity = identity
            with self.subTest(name=name), self.assertRaises(ValueError): self.install()
            self.assertEqual(self.wire.actions, [('identity', 0, 0)])

    def test_changed_app_or_missing_tune_no_erase(self):
        app = self.wire.app
        self.fresh('app').app = app[:-1] + bytes((app[-1] ^ 1,))
        with self.assertRaisesRegex(ValueError, 'Application settings differ'): self.install()
        self.assertFalse(self.wire.sent('erase'))
        self.fresh('motor').motor = self.bundle['artifacts']['before']['motor_configuration']
        with self.assertRaisesRegex(ValueError, 'prepared tune is not on this controller'): self.install()
        self.assertFalse(self.wire.sent('erase'))

    def motor_with(self, **fields):
        raw = bytearray(self.bundle['artifacts']['proposed_motor'])
        spans = flt.fleet.motor_spans(bytes(raw))
        for field, value in fields.items():
            start, end = spans[field]
            raw[start:end] = struct.pack('>f', value)
        return bytes(raw)

    def test_runtime_erpm_limits_may_be_tighter_than_the_tune_but_never_looser(self):
        # A Heltec mode write narrows the ERPM limits until the next power-up (ECO here).
        self.wire.motor = self.motor_with(l_min_erpm=-15163.127, l_max_erpm=15163.127)
        self.assertTrue(self.install()['complete'])
        for index, fields in enumerate(({'l_max_erpm': 150001.0}, {'l_min_erpm': -150001.0}, {'l_max_erpm': 0.0},
                                        {'l_max_erpm': -15163.0}, {'l_min_erpm': 15163.0}, {'l_min_erpm': 0.0},
                                        {'l_current_max': 139.0}, {'l_max_vin': 84.0})):
            self.fresh('erpm' + str(index)).motor = self.motor_with(**fields)
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, 'prepared tune is not on this controller'):
                self.install()
            self.assertFalse(self.wire.sent('erase'))

    def test_reverse_selected_pedal_motion_or_fault_no_erase(self):
        for index, text in enumerate(('(pins 0 1 {0.0871} {0.0} 0)', '(pins 1 1 {0.13} {0.0} 0)',
                                      '(pins 1 1 {0.0871} {51.0} 0)', '(pins 1 1 {0.0871} {0.0} 3)',
                                      '(pins 1 1 {-0.01} {0.0} 0)', 'garbage', REST + '\n' + REST)):
            self.fresh('pins' + str(index)).snapshot = text
            with self.subTest(text=text), self.assertRaises(ValueError): self.install()
            self.assertFalse(self.wire.sent('erase'))
        for index, (offset, value) in enumerate(((23, struct.pack('>i', 60)), (53, b'\x01'))):
            raw = bytearray(self.wire.telemetry); raw[offset:offset + len(value)] = value
            self.fresh('telemetry' + str(index)).telemetry = bytes(raw)
            with self.subTest(offset=offset), self.assertRaises(ValueError): self.install()
            self.assertFalse(self.wire.sent('erase'))

    def test_contexts_or_existing_code_refuse_erase(self):
        for field in ('context_active', 'existing'):
            setattr(self.fresh(field), field, True)
            with self.subTest(field=field), self.assertRaises(ValueError): self.install()
            self.assertFalse(self.wire.sent('erase'))

    def test_change_at_the_final_check_refuses_erase(self):
        for index, text in enumerate(('(pins 0 1 {0.0871} {0.0} 0)', '(pins 1 1 {0.2} {0.0} 0)')):
            self.fresh('final' + str(index)).snapshots = [REST] * 4 + [text]
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'Final check'): self.install()
            self.assertEqual(len(self.wire.sent('snapshot')), 5)
            self.assertFalse(self.wire.sent('erase'))

    def test_delayed_final_read_refuses_erase(self):
        self.wire.delay_final_empty = True
        with patch.object(flt.time, 'monotonic', side_effect=lambda: self.wire.clock):
            with self.assertRaises(TimeoutError): self.install()
        self.assertFalse(self.wire.sent('erase'))

    # ---- install
    def test_success_body_then_header_exact_readback_no_activation(self):
        result = self.install()
        writes = [offset for action, offset, _ in self.wire.actions if action == 'write']
        self.assertEqual(writes, list(self.package.body_offsets) + [0])
        self.assertEqual(len(self.wire.sent('erase')), 1)
        self.assertEqual(self.wire.flash[:len(self.package.image)], self.package.image)
        self.assertEqual((self.out / 'code-readback.bin').read_bytes(), self.package.blob)
        self.assertEqual((self.out / 'planned-image.bin').read_bytes(), self.package.image)
        self.assertTrue(result['complete'])
        self.assertFalse(result['activation_sent'])
        self.assertFalse(result['settings_written'])
        self.assertTrue(result['all_376_settings_preserved'])
        self.assertEqual(result['phase'], 'stored_verified_not_activated')
        self.assertEqual(result['readback_sha256'], self.sha)
        self.assertEqual(result['kart_id'], 4)
        self.assertEqual(result['target_uuid'], FAKE_UUID)
        self.assertEqual({a for a, _, _ in self.wire.actions},
                         {'identity', 'app', 'motor', 'telemetry', 'snapshot', 'contexts', 'read', 'erase', 'write'})
        self.assertFalse(self.wire.sent('status'))
        erase_at = self.wire.actions.index(('erase', 0, 0))
        self.assertEqual(self.wire.actions[erase_at - 1], ('read', 0, 0))

    def test_uncertain_erase_or_write_never_retried(self):
        for action, offset in (('erase', None), ('write', 8), ('write', 0)):
            wire = self.fresh(action + str(offset))
            wire.fail_action, wire.fail_offset = action, offset
            with self.subTest(action=action, offset=offset), self.assertRaises(IOError): self.install()
            self.assertEqual(self.wire.actions[-1], (action, offset or 0, 0))
            self.assertEqual(self.wire.actions.count((action, offset or 0, 0)), 1)
            self.assertFalse(self.manifest()['complete'])
            self.assertIn('No further sends', self.manifest()['failure_policy'])

    def test_wrong_write_ack_stops_before_next_chunk(self):
        self.wire.bad_ack_offset = 264
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(self.wire.actions[-1], ('write', 8, 0))

    def test_corrupt_readback_never_completes_or_cleans_up(self):
        self.wire.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, 'differs from the exact package script'): self.install()
        self.assertFalse(self.manifest()['complete'])
        self.assertFalse(self.manifest()['activation_sent'])
        self.assertEqual(len(self.wire.sent('erase')), 1)

    # ---- observe
    def test_observe_only_reads_and_reports_the_switch_either_way(self):
        result = flt.observe('FAKE', self.out, self.bundle, samples=3, pause=0, **self.factories())
        self.assertTrue(result['complete'] and result['all_at_rest'])
        self.assertEqual(result['rx_levels_seen'], [1])
        self.assertEqual(result['stored_code_bytes'], 0)
        self.assertEqual(result['contexts']['snapshot'], 'no_contexts_reported')
        self.assertEqual({a for a, _, _ in self.wire.actions}, {'identity', 'app', 'motor', 'telemetry', 'snapshot', 'contexts', 'read'})
        self.assertEqual(self.wire.sent('read'), [('read', 0, 0)])
        wire = self.fresh('reverse')
        wire.snapshots = ['(pins 0 1 {0.0871} {0.0} 0)', REST, '(pins 0 1 {0.31} {0.0} 0)']
        result = flt.observe('FAKE', self.out, self.bundle, samples=3, pause=0, **self.factories())
        self.assertEqual(result['rx_levels_seen'], [0, 1])
        self.assertFalse(result['all_at_rest'])
        self.assertTrue(result['complete'])
        self.assertFalse(self.wire.sent('erase') or self.wire.sent('write') or self.wire.sent('status'))

    def test_observe_refuses_other_controllers_and_changed_settings(self):
        self.wire.identity = (self.source / 'firmware.bin').read_bytes()
        with self.assertRaises(ValueError): flt.observe('FAKE', self.out, self.bundle, pause=0, **self.factories())
        self.assertEqual(self.wire.actions, [('identity', 0, 0)])
        for samples in (0, 41, True, 2.0):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                flt.observe('FAKE', self.base / ('n' + str(samples)), self.bundle, samples=samples, **self.factories())

    # ---- status after a power-up
    def status(self, expected_rx=1):
        return flt.status('FAKE', self.out, self.bundle, expected_rx=expected_rx, **self.factories())

    def test_status_verifies_stored_bytes_and_an_armed_worker(self):
        self.wire.store()
        result = self.status()
        self.assertTrue(result['complete'] and result['armed'])
        self.assertEqual(result['applied_direction'], 'forward')
        self.assertEqual(result['readback_sha256'], self.sha)
        self.assertFalse(self.wire.sent('erase') or self.wire.sent('write') or self.wire.sent('snapshot'))
        wire = self.fresh('reverse'); wire.store()
        wire.status = '(gk-rx-status t t 1507 1 0 {0.0871} {0.000000} 0)'
        self.assertEqual(self.status(expected_rx=0)['applied_direction'], 'reverse')

    def test_status_never_calls_a_wrong_state_armed(self):
        cases = (('(gk-rx-status nil nil -1 -1 1 {0.0871} {0.0} 0)', RuntimeError, 'not armed'),
                 ('(gk-rx-status t nil 1507 -1 1 {0.0871} {0.0} 0)', RuntimeError, 'not armed'),
                 ('(gk-rx-status t t 1507 1 1 {0.0871} {0.0} 0)', RuntimeError, 'does not match the switch'),
                 ('(gk-rx-status t t 1507 1 0 {0.0871} {0.0} 0)', ValueError, 'not the stated position'),
                 ('(gk-rx-status t t 1507 0 1 {0.4} {0.0} 0)', ValueError, 'Not at rest'),
                 ('unbound variable gk-rx-filter-run', ValueError, 'No unique complete'))
        for index, (text, error, message) in enumerate(cases):
            wire = self.fresh('state' + str(index)); wire.store(); wire.status = text
            with self.subTest(text=text), self.assertRaisesRegex(error, message): self.status()
            self.assertFalse(self.manifest()['complete'])
            self.assertFalse(self.wire.sent('erase') or self.wire.sent('write'))
        wire = self.fresh('empty')
        with self.assertRaisesRegex(ValueError, 'unexpected length'): self.status()
        wire = self.fresh('corrupt'); wire.store(); wire.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, 'differs from the exact package script'): self.status()
        for value in (None, 2, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                flt.status('FAKE', self.base / ('rx' + str(value)), self.bundle, expected_rx=value, **self.factories())


    # ---- remove
    def remove(self, **overrides):
        kwargs = {'apply': True, 'supervised': True, **self.factories()}
        kwargs.update(overrides)
        return flt.remove('FAKE', self.out, self.bundle, **kwargs)

    def test_remove_erases_exactly_the_package_script_once_and_writes_nothing(self):
        self.wire.store()
        result = self.remove()
        self.assertEqual(len(self.wire.sent('erase')), 1)
        self.assertFalse(self.wire.sent('write') or self.wire.sent('snapshot') or self.wire.sent('contexts'))
        self.assertEqual(self.wire.blob(), b'')
        self.assertTrue(result['complete'])
        self.assertEqual(result['phase'], 'erased_power_cycle_required')
        self.assertEqual(result['stored_before_sha256'], self.sha)
        self.assertIn('forward, held', result['direction_until_power_cycle'])
        self.assertIn('power cycle', result['boot_acceptance'])
        self.assertFalse(result['activation_sent'] or result['settings_written'])
        self.assertTrue(result['all_376_settings_preserved'])
        self.assertEqual({a for a, _, _ in self.wire.actions}, {'identity', 'app', 'motor', 'telemetry', 'status', 'read', 'erase'})
        erase_at = self.wire.actions.index(('erase', 0, 0))
        # The last thing before the erase is the fresh rest check; after it, flash-level reads only.
        self.assertEqual(self.wire.actions[erase_at - 2:erase_at], [('status', 0, 0), ('telemetry', 0, 0)])
        self.assertEqual([a for a, _, _ in self.wire.actions[erase_at + 1:]], ['read', 'app', 'motor', 'identity'])
        self.assertEqual(len(self.wire.sent('status')), 5)
        # Afterwards the ordinary read-only observation sees an empty controller.
        self.wire.erased = False
        self.out = self.base / 'after'
        seen = flt.observe('FAKE', self.out, self.bundle, samples=1, pause=0, **self.factories())
        self.assertEqual((seen['stored_code_bytes'], seen['contexts']['snapshot']), (0, 'no_contexts_reported'))

    def test_remove_when_the_filter_never_took_over_the_switch(self):
        self.wire.store()
        self.wire.status = '(gk-rx-status nil nil -1 -1 1 {0.0871} {0.0} 0)'
        result = self.remove()
        self.assertTrue(result['complete'])
        self.assertIn('raw switch', result['direction_until_power_cycle'])

    def test_remove_refuses_anything_but_this_package_script(self):
        with self.assertRaisesRegex(ValueError, 'unexpected length'): self.remove()       # nothing stored
        self.assertFalse(self.wire.sent('erase') or self.wire.sent('status'))
        wire = self.fresh('other'); wire.existing = True                                  # someone else's code
        with self.assertRaisesRegex(ValueError, 'unexpected length'): self.remove()
        self.assertFalse(self.wire.sent('erase'))
        wire = self.fresh('edited'); wire.store(); wire.corrupt_readback = True
        with self.assertRaisesRegex(ValueError, 'differs from the exact package script'): self.remove()
        self.assertFalse(self.wire.sent('erase'))

    def test_remove_refuses_reverse_held_reverse_selected_motion_pedal_or_fault(self):
        cases = (('(gk-rx-status t t 1507 1 0 {0.0871} {0.0} 0)', 'not reading forward'),     # reverse selected and applied
                 ('(gk-rx-status t t 1507 0 0 {0.0871} {0.0} 0)', 'not reading forward'),     # switch just moved to reverse
                 ('(gk-rx-status t t 1507 1 1 {0.0871} {0.0} 0)', 'holding reverse'),         # frozen in reverse
                 ('(gk-rx-status nil t -1 1 1 {0.0871} {0.0} 0)', 'holding reverse'),         # stopped worker, reverse held
                 ('(gk-rx-status t t 1507 -1 1 {0.0871} {0.0} 0)', 'no applied direction'),
                 ('(gk-rx-status t t 1507 0 1 {0.13} {0.0} 0)', 'not at rest'),
                 ('(gk-rx-status t t 1507 0 1 {0.0871} {51.0} 0)', 'not at rest'),
                 ('(gk-rx-status t t 1507 0 1 {0.0871} {0.0} 3)', 'not at rest'),
                 ('unbound variable gk-rx-filter-run', 'No unique complete'))
        for index, (text, message) in enumerate(cases):
            wire = self.fresh('state' + str(index)); wire.store(); wire.status = text
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, message): self.remove()
            self.assertFalse(self.wire.sent('erase'))
            self.assertEqual(self.wire.blob(), self.package.blob)
            self.assertFalse(self.manifest()['complete'])
        for index, (offset, value) in enumerate(((23, struct.pack('>i', 60)), (53, b'\x01'))):
            wire = self.fresh('telemetry' + str(index)); wire.store()
            raw = bytearray(wire.telemetry); raw[offset:offset + len(value)] = value; wire.telemetry = bytes(raw)
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'not at rest'): self.remove()
            self.assertFalse(self.wire.sent('erase'))

    def test_remove_refuses_a_change_at_the_final_check_or_a_slow_one(self):
        for index, text in enumerate(('(gk-rx-status t t 1507 0 0 {0.0871} {0.0} 0)', '(gk-rx-status t t 1507 0 1 {0.2} {0.0} 0)',
                                      '(gk-rx-status t t 1507 1 1 {0.0871} {0.0} 0)')):
            wire = self.fresh('final' + str(index)); wire.store(); wire.statuses = [ARMED] * 4 + [text]
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'Final check'): self.remove()
            self.assertEqual(len(self.wire.sent('status')), 5)
            self.assertFalse(self.wire.sent('erase'))
        wire = self.fresh('slow'); wire.store(); wire.slow_telemetry_from = 4     # the final telemetry read takes a second
        with patch.object(flt.time, 'monotonic', side_effect=lambda: self.wire.clock):
            with self.assertRaises(TimeoutError): self.remove()
        self.assertFalse(self.wire.sent('erase'))
        self.assertEqual(self.wire.blob(), self.package.blob)

    def test_remove_refuses_other_controllers_changed_settings_and_missing_supervision(self):
        self.wire.store(); self.wire.identity = (self.source / 'firmware.bin').read_bytes()
        with self.assertRaises(ValueError): self.remove()
        self.assertEqual(self.wire.actions, [('identity', 0, 0)])
        wire = self.fresh('app'); wire.store(); wire.app = wire.app[:-1] + bytes((wire.app[-1] ^ 1,))
        with self.assertRaisesRegex(ValueError, 'Application settings differ'): self.remove()
        self.assertFalse(self.wire.sent('erase'))
        wire = self.fresh('unsupervised'); wire.store()
        with self.assertRaises(ValueError): self.remove(supervised=False)
        self.assertEqual(self.wire.actions, [])
        plan = self.remove(apply=False, connection_factory=lambda port: self.fail('opened'))
        self.assertTrue(plan['offline_only'])
        self.assertEqual((plan['flash_requests'], plan['writes'], plan['removes_blob_sha256']), (['erase'], 0, self.sha))
        path = self.package_dir / 'rx-filter-codeblob.bin'
        path.write_bytes(path.read_bytes().replace(b'0.12', b'0.92', 1))
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.remove()
        self.assertEqual(self.wire.actions, [])

    def test_remove_uncertain_or_ineffective_erase_is_never_retried(self):
        self.wire.store(); self.wire.fail_action = 'erase'
        with self.assertRaises(IOError): self.remove()
        self.assertEqual(self.wire.actions[-1], ('erase', 0, 0))
        self.assertEqual(len(self.wire.sent('erase')), 1)
        self.assertFalse(self.manifest()['complete'])
        self.assertIn('No further sends', self.manifest()['failure_policy'])
        wire = self.fresh('noop'); wire.store(); wire.erase_does_nothing = True
        with self.assertRaisesRegex(ValueError, 'Code reported after erase'): self.remove()
        self.assertEqual(len(self.wire.sent('erase')), 1)
        self.assertFalse(self.manifest()['complete'])
        # Settings that differ afterwards are reported, never called a clean removal.
        wire = self.fresh('settings'); wire.store(); wire.app_changes_after_erase = True
        with self.assertRaisesRegex(ValueError, 'Configuration changed during removal'): self.remove()
        self.assertEqual(len(self.wire.sent('erase')), 1)
        self.assertFalse(self.manifest()['complete'])

    def test_remove_command_line_is_offline_without_apply_and_needs_every_flag(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(flt.main(self.cli('remove')), 0)
        plan = json.loads(out.getvalue())
        self.assertTrue(plan['offline_only'])
        self.assertEqual(plan['removes_blob_sha256'], self.sha)
        bad = (('remove', '--apply', '--supervised', '--port', '/no-port', '--out', str(self.out)),
               ('remove', '--expect-blob-sha256', self.sha),
               ('remove', '--apply', '--supervised', '--expect-blob-sha256', self.sha, '--port', '/no-port'),
               ('remove', '--port', '/no-port'), ('observe', '--apply'), ('status', '--supervised', '--expected-rx', '1'))
        for args in bad:
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                flt.main(self.cli(*args))
        with self.assertRaisesRegex(ValueError, 'no device opened'):
            flt.main(self.cli('remove', '--apply', '--supervised', '--expect-blob-sha256', '0' * 64,
                              '--port', '/no-port', '--out', str(self.out)))
        self.assertFalse(self.out.exists())


class WireTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        source = fleet.FILTER_SOURCE.read_bytes()
        self.package = flt.Package(source + b'\0\0\0')
        self.wire = flt.Wire(91, self.out, self.package)

    def test_partial_write_once_full_attempt_journal(self):
        with patch.object(flt.os, 'write', return_value=3) as write:
            with self.assertRaises(IOError): self.wire.send('write', 8)
        write.assert_called_once_with(91, self.package.frame('write', 8))
        self.assertEqual((self.out / 'tx-attempts.bin').read_bytes(), self.package.frame('write', 8))

    def test_erase_needs_a_fresh_window_and_is_never_sent_late(self):
        with patch.object(flt.os, 'write') as write:
            with self.assertRaises(TimeoutError): self.wire.send('erase')
            self.wire.erase_deadline = flt.time.monotonic() - 1
            with self.assertRaises(TimeoutError): self.wire.send('erase')
        write.assert_not_called()

    def test_crc_fragmented_ack_retained(self):
        data = b'\x83\x01' + struct.pack('>I', 8)
        response = bytes((2, len(data))) + data + struct.pack('>H', binascii.crc_hqx(data, 0)) + b'\x03'
        with patch.object(flt.os, 'write', side_effect=lambda fd, data: len(data)), \
             patch.object(flt.control.select, 'select', return_value=([91], [], [])), \
             patch.object(flt.os, 'read', side_effect=[response[:3], response[3:]]):
            answer = self.wire.query('write', 8)
        flt.check_ack('write', answer, 8)
        self.assertEqual((self.out / 'rx-wire.bin').read_bytes(), response)

    def test_malformed_blob_is_not_a_package(self):
        source = fleet.FILTER_SOURCE.read_bytes()
        for blob in (source, source + b'\0\0', source[:100] + b'\0' + source[100:] + b'\0\0\0', b'short\0\0\0'):
            with self.subTest(size=len(blob)), self.assertRaises(ValueError): flt.Package(blob)


if __name__ == '__main__':
    unittest.main()
