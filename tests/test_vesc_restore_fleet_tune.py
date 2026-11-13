"""Kart-4/5 settings restore tests with fake serial packets; never open hardware.

Captures are SYNTHETIC copies of kart-3 evidence with an invented UUID and altered limits.
"""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
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
sys.path.insert(0, str(ROOT/'tests'))
import apply_fleet_tune
import apply_tune
import prepare_fleet_kart as fleet
import restore_fleet_tune as restore
from decode import decode_payloads
from tune import motor_spans, sha256
from test_vesc_apply_tune import FakeSerial, FakeWire
from test_vesc_apply_fleet_tune import TARGET_LIMITS, motor_int
from test_vesc_prepare_fleet_kart import FAKE_UUID, SOURCE, TARGET, fixture, motor_field, uuid_field


def with_field(raw, field, value, kind='>f'):
    data = bytearray(raw)
    start, end = motor_spans(raw)[field]
    packed = struct.pack(kind, value)
    assert end - start == len(packed), field
    data[start:end] = packed
    return bytes(data)


def nudged(raw, field):
    """The same settings with one field's stored bytes changed by one count, whatever its encoding."""
    data = bytearray(raw)
    start, end = motor_spans(raw)[field]
    data[end - 1] ^= 1
    return bytes(data)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = fixture(self.base/'source', SOURCE)
        self.target = fixture(self.base/'target', TARGET)
        motor_field(self.source, 'l_current_min', -5)
        uuid_field(self.target, FAKE_UUID)
        for field, value in TARGET_LIMITS.items():
            motor_field(self.target, field, value)
        motor_int(self.target, 'm_fault_stop_time_ms', 50)
        self.package = self.base/'package'
        plan, artifacts = fleet.prepare(self.source, self.target, kart_id=4, target_uuid=FAKE_UUID, protection_limits=True)
        fleet.write_plan(plan, artifacts, self.package)
        self.bundle = apply_fleet_tune.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)
        self.original = artifacts['before']['motor_configuration']
        self.proposed = artifacts['proposed_motor']
        self.sha = sha256(self.original)
        self.changed = [p['field'] for p in plan['patches'] if p['before_hex'] != p['proposed_hex']]
        # The controller as it is today: the package applied, everything else as captured.
        self.wire = FakeWire(dict(artifacts['before'], motor_configuration=self.proposed))
        self.connection = FakeSerial(self.wire)
        self.out = self.base/'evidence'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(apply_tune.os, 'write', self.wire.write))
        self.stack.enter_context(patch.object(apply_tune.os, 'read', self.wire.read))
        self.stack.enter_context(patch.object(apply_tune.select, 'select', self.wire.select))
        self.stack.enter_context(patch.object(apply_tune.termios, 'tcflush', self.wire.flush))

    def run_restore(self, **kwargs):
        return restore.run(self.bundle, self.connection, self.out, **kwargs)

    def again(self, name, motor=None):
        self.wire.current['motor_configuration'] = self.proposed if motor is None else motor
        self.wire.sent.clear()
        self.connection = FakeSerial(self.wire)
        self.out = self.base/name

    def report(self):
        return json.loads((self.out/'restore-manifest.json').read_text())

    def ids(self):
        return [payload[0] for payload in self.wire.sent]

    def cli(self, *extra):
        return [str(self.package), '--kart-id', '4', '--expected-uuid', FAKE_UUID, *extra]

    # ---- offline
    def test_default_is_offline_and_lists_exactly_the_package_changes(self):
        with patch.object(restore, 'SerialConnection') as connection, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(restore.main(self.cli()), 0)
            connection.assert_not_called()
        plan = json.loads(out.getvalue())
        self.assertTrue(plan['offline_only'])
        self.assertEqual([r['setting'] for r in plan['restores']], self.changed)
        wanted = {r['setting']: (r['now_expected'], r['restored_to']) for r in plan['restores']}
        self.assertEqual(wanted['l_abs_current_max'], (220.0, 420.0))
        self.assertEqual(wanted['m_fault_stop_time_ms'], (500, 50))
        self.assertEqual(wanted['l_min_vin'], (60.0, 12.0))
        self.assertEqual(plan['original_motor_sha256'], self.sha)

    def test_every_apply_flag_is_required_and_the_hash_must_be_the_original(self):
        full = ['--apply', '--acknowledge-persistent-write', '--expect-original-sha256', self.sha,
                '--port', '/no-port', '--out', str(self.out)]
        for drop in ('--apply', '--acknowledge-persistent-write', '--expect-original-sha256', '--port', '--out'):
            args = list(full)
            at = args.index(drop)
            del args[at:at + (1 if drop in ('--apply', '--acknowledge-persistent-write') else 2)]
            with self.subTest(drop=drop), patch.object(restore, 'SerialConnection') as connection:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    restore.main(self.cli(*args))
                connection.assert_not_called()
        for stated in ('0' * 64, sha256(self.proposed), 'nope'):
            args = self.cli('--apply', '--acknowledge-persistent-write', '--expect-original-sha256', stated,
                            '--port', '/no-port', '--out', str(self.out))
            with self.subTest(stated=stated), patch.object(restore, 'SerialConnection') as connection:
                with self.assertRaisesRegex(ValueError, 'no device opened'):
                    restore.main(args)
                connection.assert_not_called()
        with patch.object(restore, 'SerialConnection') as connection, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                restore.main(self.cli('--port', '/no-port'))
            with self.assertRaises(SystemExit):
                restore.main([str(self.package), '--kart-id', '3', '--expected-uuid', FAKE_UUID])
            connection.assert_not_called()
        self.assertFalse(self.out.exists())

    # ---- reads
    def test_preflight_reads_four_and_sends_no_settings(self):
        result = self.run_restore()
        self.assertEqual(self.ids(), [0, 14, 17, 4])
        self.assertEqual(result['status'], 'preflight_verified_no_settings_sent')
        self.assertEqual(sorted(result['to_restore']), sorted(self.changed))
        self.assertEqual(result['mutating_write_attempts'], 0)
        self.assertEqual(result['restored_motor_sha256'], self.sha)

    # ---- the write
    def test_success_is_one_write_of_the_original_values_then_exact_readback(self):
        result = self.run_restore(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
        self.assertEqual(self.wire.sent[4], b'\r' + self.original[1:])
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        self.assertTrue(result['ack_verified'] and result['readback_verified'])
        self.assertTrue(result['measured_offsets_identical_after_write'])
        self.assertEqual(result['mutating_write_attempts'], 1)
        self.assertEqual(sorted(result['restored_settings']), sorted(self.changed))
        self.assertFalse(result['saved_flash_independently_verified'])
        after = {name: (self.out/'after'/(name + '.bin')).read_bytes()
                 for name in ('firmware', 'telemetry', 'motor_configuration', 'app_configuration')}
        values = decode_payloads(after)['motor_configuration']['values']
        for field, wanted in dict(TARGET_LIMITS, m_fault_stop_time_ms=50).items():
            self.assertEqual(values[field], wanted, field)
        self.assertEqual(after['app_configuration'], self.bundle['artifacts']['before']['app_configuration'])

    def test_offsets_measured_at_this_power_up_are_kept_not_restored(self):
        fresh = nudged(self.proposed, 'foc_offsets_voltage__0')
        self.again('offsets', fresh)
        result = self.run_restore(apply=True)
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        sent = b'\x0e' + self.wire.sent[4][1:]
        self.assertEqual(sent, nudged(self.original, 'foc_offsets_voltage__0'))
        self.assertNotEqual(sent, self.original)

    def test_an_offset_the_controller_moves_after_the_write_is_not_called_uncertain(self):
        # Kart 5's tune write on 2026-11-13: one measured offset read back one count different.
        self.wire.after_change = lambda current: current.update(
            motor_configuration=nudged(current['motor_configuration'], 'foc_offsets_voltage__0'))
        result = self.run_restore(apply=True)
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        self.assertFalse(result['measured_offsets_identical_after_write'])

    def test_settings_already_put_back_by_hand_are_left_and_the_rest_restored(self):
        partly = with_field(self.proposed, 'l_abs_current_max', 420.0)
        self.again('partly', partly)
        result = self.run_restore(apply=True)
        self.assertEqual(result['settings_now']['l_abs_current_max'], 'already_original')
        self.assertNotIn('l_abs_current_max', result['to_restore'])
        self.assertEqual(len(result['to_restore']), len(self.changed) - 1)
        self.assertEqual(self.wire.sent[4], b'\r' + self.original[1:])
        self.again('done', self.original)
        result = self.run_restore(apply=True)
        self.assertEqual(result['status'], 'nothing_to_restore_no_settings_sent')
        self.assertNotIn(13, self.ids())

    # ---- refusals
    def test_a_temporary_limit_or_any_other_changed_setting_is_refused_without_writing(self):
        cases = (('l_current_max_scale', None, 'never touched'),      # a Heltec mode in force
                 ('l_watt_max', None, 'never touched'),               # likewise
                 ('l_temp_fet_start', None, 'never touched'),         # someone changed something else
                 ('l_abs_current_max', 260.0, 'neither the package value nor the original'),
                 ('l_current_max', 130.0, 'neither the package value nor the original'))
        for index, (field, value, message) in enumerate(cases):
            fresh = nudged(self.proposed, field) if value is None else with_field(self.proposed, field, value)
            self.again('case' + str(index), fresh)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, message):
                self.run_restore(apply=True)
            self.assertNotIn(13, self.ids())
            self.assertEqual(self.report()['status'], 'rejected_no_settings_sent')

    def test_other_controllers_changed_app_or_motion_are_refused(self):
        original = self.wire.current['firmware']
        other = bytearray(original); other[original.index(0, 3) + 1] ^= 1
        for name, firmware in (('kart3', (self.source/'firmware.bin').read_bytes()), ('other', bytes(other))):
            self.again(name); self.wire.current['firmware'] = firmware
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_restore(apply=True)
            self.assertEqual(self.ids(), [0])
        self.wire.current['firmware'] = original
        app = self.wire.current['app_configuration']
        self.again('app'); self.wire.current['app_configuration'] = app[:-1] + bytes((app[-1] ^ 1,))
        with self.assertRaisesRegex(ValueError, 'app_configuration'): self.run_restore(apply=True)
        self.assertNotIn(13, self.ids())
        self.wire.current['app_configuration'] = app
        telemetry = bytearray(self.wire.current['telemetry']); telemetry[23:27] = struct.pack('>i', 60)
        self.again('moving'); self.wire.current['telemetry'] = bytes(telemetry)
        with self.assertRaisesRegex(ValueError, 'stationary'): self.run_restore(apply=True)
        self.assertNotIn(13, self.ids())

    def test_package_changed_after_validation_sends_nothing(self):
        path = self.package/'before'/'motor_configuration.bin'
        path.write_bytes(with_field(path.read_bytes(), 'l_current_max', 99.0))
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.run_restore()   # even a preflight
        self.again('apply')
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.run_restore(apply=True)
        self.assertNotIn(13, self.ids())

    # ---- uncertain outcomes
    def test_uncertain_write_is_recorded_and_never_retried(self):
        for mode in ('partial', 'exception', 'missing_ack', 'bad_ack'):
            self.again(mode); self.wire.mode = mode
            with self.subTest(mode=mode), self.assertRaises(Exception): self.run_restore(apply=True)
            self.assertEqual(self.ids().count(13), 1)
            report = self.report()
            self.assertEqual(report['status'], 'write_uncertain_do_not_retry')
            self.assertFalse(report['readback_verified'])
            try:                                        # the same connection never writes again
                restore.run(self.bundle, self.connection, self.base/(mode + '-again'), apply=True)
            except Exception:
                pass
            self.assertEqual(self.ids().count(13), 1)
        self.wire.mode = 'normal'

    def test_a_setting_that_reads_back_wrong_is_not_called_restored(self):
        self.wire.after_change = lambda current: current.update(
            motor_configuration=with_field(current['motor_configuration'], 'l_abs_current_max', 220.0))
        with self.assertRaisesRegex(ValueError, 'Readback differs'): self.run_restore(apply=True)
        report = self.report()
        self.assertEqual(report['status'], 'write_uncertain_do_not_retry')
        self.assertFalse(report['readback_verified'])
        self.assertEqual(self.ids().count(13), 1)
        self.again('app-after')
        self.wire.after_change = lambda current: current.update(
            app_configuration=current['app_configuration'][:-1] + bytes((current['app_configuration'][-1] ^ 1,)))
        with self.assertRaisesRegex(ValueError, 'app_configuration'): self.run_restore(apply=True)
        self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')


if __name__ == '__main__':
    unittest.main()
