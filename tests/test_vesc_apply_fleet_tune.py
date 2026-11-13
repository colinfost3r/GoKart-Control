"""Guarded kart-4/5 tune writer tests with fake serial packets; never open hardware.

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
import apply_fleet_tune as apply
import apply_tune
import prepare_fleet_kart as fleet
from capture import query_frame
from decode import decode_payloads
from tune import motor_spans
from test_vesc_apply_tune import FakeSerial, FakeWire
from test_vesc_prepare_fleet_kart import FAKE_UUID, SOURCE, TARGET, fixture, motor_field, refresh, uuid_field

OTHER_UUID = '0c0b0a090807060504030201'
TARGET_LIMITS = {'l_in_current_min': -200.0, 'l_abs_current_max': 420.0, 'l_min_vin': 12.0, 'l_max_vin': 84.0}


def motor_int(path, field, value):
    file = path/'motor_configuration.bin'
    data = bytearray(file.read_bytes())
    start, end = motor_spans(data)[field]
    assert end - start == 4
    data[start:end] = struct.pack('>i', value)
    file.write_bytes(data)
    refresh(path)


class FleetApplyTests(unittest.TestCase):
    limits = True

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
        self.plan, self.artifacts = fleet.prepare(self.source, self.target, kart_id=4, target_uuid=FAKE_UUID,
                                                  protection_limits=self.limits)
        fleet.write_plan(self.plan, self.artifacts, self.package)
        self.bundle = apply.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)
        self.sha = self.plan['proposed_motor_response_sha256']
        self.wire = FakeWire(self.artifacts['before'])
        self.connection = FakeSerial(self.wire)
        self.out = self.base/'evidence'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(apply_tune.os, 'write', self.wire.write))
        self.stack.enter_context(patch.object(apply_tune.os, 'read', self.wire.read))
        self.stack.enter_context(patch.object(apply_tune.select, 'select', self.wire.select))
        self.stack.enter_context(patch.object(apply_tune.termios, 'tcflush', self.wire.flush))

    def run_package(self, **kwargs):
        return apply.run(self.bundle, self.connection, self.out, **kwargs)

    def report(self):
        return json.loads((self.out/'apply-manifest.json').read_text())

    def ids(self):
        return [payload[0] for payload in self.wire.sent]

    def cli(self, *extra):
        return [str(self.package), '--kart-id', '4', '--expected-uuid', FAKE_UUID, *extra]

    def test_default_is_offline_and_every_apply_flag_is_required(self):
        with patch.object(apply, 'SerialConnection') as connection, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(apply.main(self.cli()), 0)
            connection.assert_not_called()
        self.assertIn(self.sha, out.getvalue())
        full = ['--apply', '--acknowledge-persistent-write', '--expect-proposed-sha256', self.sha,
                '--port', '/no-port', '--out', str(self.out)]
        for drop in ('--apply', '--acknowledge-persistent-write', '--expect-proposed-sha256', '--port', '--out'):
            args = list(full)
            at = args.index(drop)
            del args[at:at + (1 if drop in ('--apply', '--acknowledge-persistent-write') else 2)]
            with self.subTest(drop=drop), patch.object(apply, 'SerialConnection') as connection:
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    apply.main(self.cli(*args))
                connection.assert_not_called()
        with patch.object(apply, 'SerialConnection') as connection, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                apply.main(self.cli('--port', '/no-port'))
            connection.assert_not_called()
        with self.assertRaises(ValueError):
            query_frame(13)  # The read-only capture allowlist remains unchanged.

    def test_stated_hash_must_be_this_packages_proposed_bytes(self):
        for stated in ('0' * 64, self.sha[:-1], 'not-a-hash'):
            args = self.cli('--apply', '--acknowledge-persistent-write', '--expect-proposed-sha256', stated,
                            '--port', '/no-port', '--out', str(self.out))
            with self.subTest(stated=stated), patch.object(apply, 'SerialConnection') as connection:
                with self.assertRaisesRegex(ValueError, 'no device opened'):
                    apply.main(args)
                connection.assert_not_called()
            self.assertFalse(self.out.exists())

    def test_package_is_bound_to_its_kart_id_and_uuid_and_never_kart_3(self):
        with self.assertRaisesRegex(ValueError, 'different kart ID'):
            apply.validate_package(self.package, kart_id=5, expected_uuid=FAKE_UUID)
        with self.assertRaisesRegex(ValueError, 'different controller UUID'):
            apply.validate_package(self.package, kart_id=4, expected_uuid=OTHER_UUID)
        for uuid in sorted(fleet.RESERVED_UUIDS):
            with self.subTest(uuid=uuid), self.assertRaisesRegex(ValueError, 'reserved'):
                apply.validate_package(self.package, kart_id=4, expected_uuid=uuid)
        for kart in (1, 2, 3, 6, True, '4'):
            with self.subTest(kart=kart), self.assertRaises(ValueError):
                apply.validate_package(self.package, kart_id=kart, expected_uuid=FAKE_UUID)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            apply.main([str(self.package), '--kart-id', '3', '--expected-uuid', FAKE_UUID])

    def test_preflight_reads_exactly_four_with_telemetry_last_and_no_settings(self):
        result = self.run_package()
        self.assertEqual(self.ids(), [0, 14, 17, 4])
        self.assertEqual(result['status'], 'preflight_verified_no_settings_sent')
        self.assertEqual(result['mutating_write_attempts'], 0)
        self.assertEqual(result['expected_identity']['uuid'], FAKE_UUID)
        self.assertTrue(json.loads((self.out/'before/manifest.json').read_text())['capture_complete'])

    def test_success_is_one_persistent_write_then_ack_and_complete_376_field_readback(self):
        result = self.run_package(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
        self.assertEqual(self.wire.sent[4], b'\r' + self.artifacts['proposed_motor'][1:])
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        self.assertEqual(result['verified_total_fields'], 376)
        self.assertTrue(result['ack_verified'] and result['readback_verified'])
        self.assertEqual(result['mutating_write_attempts'], 1)
        self.assertFalse(result['saved_flash_independently_verified'])
        self.assertEqual(result['kart_id'], 4)
        self.assertTrue(result['protection_limits_copied'])
        self.assertEqual(len(result['allowlisted_motor_fields']), 17)
        for field in list(TARGET_LIMITS) + ['m_fault_stop_time_ms', 'l_current_max']:
            self.assertIn(field, result['changed_motor_fields'])
        after = {name: (self.out/'after'/(name + '.bin')).read_bytes()
                 for name in ('firmware', 'telemetry', 'motor_configuration', 'app_configuration')}
        self.assertEqual(after['app_configuration'], self.artifacts['before']['app_configuration'])
        self.assertEqual(after['motor_configuration'], self.artifacts['proposed_motor'])
        values = decode_payloads(after)['motor_configuration']['values']
        for field, wanted in dict(fleet.PROTECTION_LIMITS, l_current_max=140.0, l_current_min=-5.0).items():
            self.assertEqual(values[field], wanted, field)
        audit = json.loads((self.out/'field-audit.json').read_text())
        self.assertEqual(sum(len(group['fields']) for group in audit.values()), 376)

    def test_kart_3_or_any_other_controller_on_the_wire_is_rejected_before_configuration_reads(self):
        original = self.wire.current['firmware']
        variants = {'kart3': (self.source/'firmware.bin').read_bytes()}
        for field in ('uuid', 'hardware', 'firmware'):
            raw = bytearray(original)
            if field == 'uuid': raw[original.index(0, 3)+1] ^= 1
            elif field == 'hardware': raw[3] = ord('X')
            else: raw[2] = 0
            variants[field] = bytes(raw)
        for name, firmware in variants.items():
            self.wire.current['firmware'] = firmware
            self.out = self.base/name
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_package(apply=True)
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
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_package(apply=True)
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
            with self.subTest(offset=offset, value=replacement), self.assertRaises(ValueError): self.run_package(apply=True)
            self.assertNotIn(13, self.ids())

    def test_partial_or_exception_write_sends_nothing_further_and_never_retries(self):
        for mode in ('partial', 'exception'):
            self.wire.mode = mode
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/mode
            with self.subTest(mode=mode), self.assertRaises(OSError): self.run_package(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13])
            self.assertEqual(self.report()['mutating_write_attempts'], 1)
            self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')
            self.assertIn('recovery_skipped', self.report())
            with self.assertRaises(RuntimeError): self.connection.query(0)

    def test_missing_or_malformed_ack_allows_only_readonly_recovery_and_never_success(self):
        for mode in ('missing_ack', 'bad_ack'):
            self.wire.mode = mode
            self.wire.current = dict(self.artifacts['before'])
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/mode
            with self.subTest(mode=mode), self.assertRaises((TimeoutError, ValueError)): self.run_package(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
            self.assertEqual(self.report()['mutating_write_attempts'], 1)
            self.assertTrue(self.report()['recovery_matches_proposal'])
            self.assertFalse(self.report()['ack_verified'])
            self.assertFalse(self.report()['readback_verified'])
            self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')

    def test_readback_motor_app_or_firmware_mismatch_never_succeeds_or_rolls_back(self):
        # The firmware variant flips the pairing flag right after the UUID: no decoded
        # configuration field or identity check covers it, only the exact byte comparison.
        for name in ('motor_configuration', 'app_configuration', 'firmware'):
            self.wire.current = dict(self.artifacts['before'])
            def corrupt(payloads, key=name):
                raw = bytearray(payloads[key])
                raw[raw.index(0, 3) + 13 if key == 'firmware' else 9] ^= 1
                payloads[key] = bytes(raw)
            self.wire.after_change = corrupt
            self.connection = FakeSerial(self.wire)
            self.wire.sent.clear()
            self.out = self.base/('bad-after-'+name)
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_package(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
            self.assertTrue(self.report()['ack_verified'])
            self.assertFalse(self.report()['readback_verified'])
            self.assertFalse(self.report()['rollback_performed'])
            self.assertEqual(self.ids().count(13), 1)

    def test_motion_or_fault_reported_after_the_write_is_never_success(self):
        def moving(payloads):
            raw = bytearray(payloads['telemetry']); raw[23:27] = struct.pack('>i', 1); payloads['telemetry'] = bytes(raw)
        self.wire.after_change = moving
        with self.assertRaisesRegex(ValueError, 'stationary'): self.run_package(apply=True)
        self.assertEqual(self.ids().count(13), 1)
        self.assertTrue(self.report()['ack_verified'])
        self.assertFalse(self.report()['readback_verified'])
        self.assertEqual(self.report()['status'], 'write_uncertain_do_not_retry')

    def test_expired_telemetry_or_capture_rejected_without_attempting_write(self):
        for constant in ('MAX_TELEMETRY_AGE_S', 'MAX_CAPTURE_AGE_S'):
            self.wire.sent.clear()
            self.connection = FakeSerial(self.wire)
            self.out = self.base/constant
            with self.subTest(constant=constant), patch.object(apply, constant, -1):
                with self.assertRaisesRegex(ValueError, 'expired'): self.run_package(apply=True)
            self.assertEqual(self.ids(), [0, 14, 17, 4])
            self.assertEqual(self.report()['mutating_write_attempts'], 0)

    def test_package_tampering_and_postvalidation_changes_fail_closed(self):
        path = self.package/'proposed_motor_response.bin'
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(ValueError, 'independently rebuilt'):
            apply.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)
        with self.assertRaisesRegex(ValueError, 'changed after validation'): self.run_package(apply=True)
        self.assertNotIn(13, self.ids())
        path.write_bytes(original)
        plan_path = self.package/'plan.json'
        good = plan_path.read_text()

        def tampered(change, pattern):
            plan = json.loads(good)
            change(plan)
            plan_path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, pattern):
                apply.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)
            plan_path.write_text(good)

        tampered(lambda p: p['allowlisted_motor_fields'].append('si_motor_poles'), 'recomputation')
        tampered(lambda p: p['protection_limits'].update(copied=not self.limits), 'recomputation')
        tampered(lambda p: p['protection_limits'].pop('copied'), 'does not state')
        tampered(lambda p: p['patches'][0].update(proposed_hex='00000000'), 'recomputation')
        tampered(lambda p: p.update(kart_id=5), 'different kart ID')
        tampered(lambda p: p['filter'].update(target_uuid=OTHER_UUID), 'different controller UUID')
        apply.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)
        before = self.package/'before/motor_configuration.bin'
        raw = bytearray(before.read_bytes()); raw[40] ^= 1
        before.write_bytes(bytes(raw))
        with self.assertRaises(ValueError):
            apply.validate_package(self.package, kart_id=4, expected_uuid=FAKE_UUID)

    def test_package_changed_between_the_fresh_read_and_the_write_sends_nothing(self):
        path = self.package/'proposed_motor_response.bin'
        real = apply.motor_frame

        def tamper_then_frame(payload):
            raw = path.read_bytes()
            path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            return real(payload)

        with patch.object(apply, 'motor_frame', tamper_then_frame):
            with self.assertRaisesRegex(ValueError, 'changed after validation'): self.run_package(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4])
        self.assertEqual(self.report()['mutating_write_attempts'], 0)
        self.assertEqual(self.report()['status'], 'rejected_no_settings_sent')

    def test_existing_evidence_or_package_or_capture_destination_rejected_before_open(self):
        self.out.mkdir()
        for out in (self.out, self.package/'new-evidence', self.target/'new-evidence', self.source/'new-evidence'):
            with self.subTest(out=out), patch.object(apply, 'SerialConnection') as connection:
                with self.assertRaises((ValueError, FileExistsError)):
                    apply.main(self.cli('--preflight-only', '--port', '/no-port', '--out', str(out)))
                connection.assert_not_called()


class FleetApplyWithoutLimitsTests(FleetApplyTests):
    """The same guards hold for a twelve-field package; target protection limits then stay."""
    limits = False

    def test_success_is_one_persistent_write_then_ack_and_complete_376_field_readback(self):
        result = self.run_package(apply=True)
        self.assertEqual(self.ids(), [0, 14, 17, 4, 13, 0, 14, 17, 4])
        self.assertEqual(result['status'], 'acknowledged_runtime_readback_verified')
        self.assertFalse(result['protection_limits_copied'])
        self.assertEqual(len(result['allowlisted_motor_fields']), 12)
        after = {name: (self.out/'after'/(name + '.bin')).read_bytes()
                 for name in ('firmware', 'telemetry', 'motor_configuration', 'app_configuration')}
        values = decode_payloads(after)['motor_configuration']['values']
        for field, kept in dict(TARGET_LIMITS, m_fault_stop_time_ms=50).items():
            self.assertEqual(values[field], kept, field)
            self.assertNotIn(field, result['changed_motor_fields'])
            self.assertIn('motor_configuration / ' + field, result['retained_operating_differences'])
        self.assertEqual(values['l_current_max'], 140.0)


if __name__ == '__main__':
    unittest.main()
