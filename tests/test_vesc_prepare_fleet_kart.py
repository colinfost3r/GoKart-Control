"""Offline fleet-plan tests. Modified captures/UUIDs are SYNTHETIC, not hardware evidence."""
from contextlib import redirect_stdout, redirect_stderr
import copy
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/vesc'))
import prepare_fleet_kart as fleet
from capture import READ_COMMANDS, query_frame
from decode import decode_payloads
from tune import snapshot, motor_spans, manifest_path, sha256

SOURCE = ROOT / 'hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01/preflight/raw'
TARGET = ROOT / 'hardware/vesc/kart3/2026-11-10/usb-before-tune/raw'
FAKE_UUID = '0102030405060708090a0b0c'


def refresh(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    manifest.pop('identity', None)
    manifest['procedure'] = 'SYNTHETIC TEST FIXTURE; altered payloads, never hardware measurements'
    for query in manifest['queries']:
        data = (path / (query['name'] + '.bin')).read_bytes()
        query.update(sha256=sha256(data), payload_bytes=len(data))
    (path / 'manifest.json').write_text(json.dumps(manifest))


def fixture(dest, source):
    dest.mkdir()
    for name in READ_COMMANDS.values():
        shutil.copyfile(source / (name + '.bin'), dest / (name + '.bin'))
    (dest / 'manifest.json').write_bytes(manifest_path(source).read_bytes())
    refresh(dest)
    return dest


def motor_field(path, field, value):
    file = path / 'motor_configuration.bin'
    data = bytearray(file.read_bytes())
    start, end = motor_spans(data)[field]
    if end - start == 2:
        assert field in ('l_current_max_scale', 'l_current_min_scale')
        encoded = struct.pack('>h', round(value * 10000))
    else:
        encoded = struct.pack('>f', value) if end - start == 4 else bytes((value,))
    data[start:end] = encoded
    file.write_bytes(data)
    refresh(path)


def uuid_field(path, uuid):
    file = path / 'firmware.bin'
    data = bytearray(file.read_bytes())
    start = data.index(0, 3) + 1
    data[start:start+12] = bytes.fromhex(uuid)
    file.write_bytes(data)
    refresh(path)


class FleetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = fixture(self.base / 'source', SOURCE)
        self.target = fixture(self.base / 'target', TARGET)
        motor_field(self.source, 'l_current_min', -5)
        uuid_field(self.target, FAKE_UUID)

    def prepare(self, **kwargs):
        options = {'kart_id': 4, 'target_uuid': FAKE_UUID}
        options.update(kwargs)
        return fleet.prepare(self.source, self.target, **options)

    def test_only_twelve_named_fields_copied_all_other_bytes_preserved(self):
        motor_field(self.target, 'foc_motor_r', .081)
        motor_field(self.target, 'foc_hall_table__1', 4)
        motor_field(self.target, 'si_wheel_diameter', .27)
        plan, artifacts = self.prepare()
        before = artifacts['before']['motor_configuration']
        after = artifacts['proposed_motor']
        spans = motor_spans(before)
        allowed = set()
        for field in fleet.TRIAL_FIELDS:
            start, end = spans[field]
            allowed.update(range(start, end))
            self.assertEqual(after[start:end], artifacts['source']['motor_configuration'][start:end], field)
        self.assertEqual(after[0], 14)
        self.assertEqual(len(after), len(before))
        for i in range(len(before)):
            if i not in allowed:
                self.assertEqual(before[i], after[i], i)
        proposed = dict(artifacts['before'], motor_configuration=after)
        decoded = decode_payloads(proposed)
        self.assertEqual(decoded['motor_configuration']['values']['l_current_min'], -5)
        self.assertEqual(decoded['motor_configuration']['values']['foc_hall_table__1'], 4)
        self.assertEqual(proposed['app_configuration'], artifacts['before']['app_configuration'])
        self.assertEqual(proposed['firmware'], artifacts['before']['firmware'])
        self.assertFalse(plan['commissioning_ready'])
        self.assertFalse(plan['apply_supported'])
        self.assertEqual(len(plan['allowlisted_motor_fields']), 12)

    def test_remaining_regen_scales_not_silently_copied_or_full_tune_match(self):
        motor_field(self.target, 'l_in_current_min', -7)
        motor_field(self.target, 'l_current_max_scale', .5)
        motor_field(self.target, 'foc_motor_r', .081)
        plan, artifacts = self.prepare()
        rows = {r['field']: r for r in plan['remaining_differences']}
        for field in ('l_in_current_min', 'l_current_max_scale'):
            self.assertTrue(rows[field]['needs_review'])
            self.assertTrue(rows[field]['must_resolve_before_commissioning'])
            self.assertEqual(rows[field]['category'], 'operating_difference')
        self.assertTrue(rows['foc_motor_r']['needs_review'])
        self.assertEqual(rows['foc_motor_r']['category'], 'target_specific_preserved')
        self.assertFalse(rows['foc_motor_r']['must_resolve_before_commissioning'])
        decoded = decode_payloads(dict(artifacts['before'], motor_configuration=artifacts['proposed_motor']))
        self.assertEqual(decoded['motor_configuration']['values']['l_in_current_min'], -7)
        self.assertEqual(decoded['motor_configuration']['values']['l_current_max_scale'], .5)
        self.assertEqual(sum(len(g['fields']) for g in plan['target_vs_proposed_all_fields'].values()), 376)
        self.assertEqual(sum(len(g['fields']) for g in plan['source_vs_proposed_all_fields'].values()), 376)

    def test_distinct_target_pedal_endpoint_and_controller_id_stay_target_specific(self):
        file = self.target / 'app_configuration.bin'
        data = bytearray(file.read_bytes())
        # Pinned fixture/schema: controller_id at5, voltage_start as int16/1000 at96.
        self.assertEqual(data[96:98], struct.pack('>h', 690))
        data[96:98] = struct.pack('>h', 710)
        data[5] = 44  # Synthetic VESC controller ID, deliberately not fleet ID4.
        file.write_bytes(data)
        refresh(self.target)
        plan, artifacts = self.prepare()
        self.assertEqual(artifacts['before']['app_configuration'], data)
        self.assertNotEqual(artifacts['source']['app_configuration'], data)
        rows = {r['field']: r for r in plan['remaining_differences']}
        self.assertEqual(rows['app_adc_conf.voltage_start']['retained_target'], .71)
        self.assertEqual(rows['controller_id']['retained_target'], 44)
        for name in ('app_adc_conf.voltage_start', 'controller_id'):
            self.assertTrue(rows[name]['needs_review'])
            self.assertEqual(rows[name]['category'], 'target_specific_preserved')

    def test_reserved_ids_uuids_and_unmatched_target_identity_rejected(self):
        for kart in (1, 2, 3, 6, 0, True, '4'):
            with self.subTest(kart=kart), self.assertRaises(ValueError):
                self.prepare(kart_id=kart)
        for uuid in ('', '0' * 24, 'zz' * 12, '1' * 22, fleet.SOURCE_UUID, '2c004c000951343037353739', 'ff' * 12):
            with self.subTest(uuid=uuid), self.assertRaises(ValueError):
                self.prepare(target_uuid=uuid)
        for kart in (4, 5):
            self.assertEqual(self.prepare(kart_id=kart)[0]['kart_id'], kart)

    def test_source_must_be_kart3_and_latest_reviewed_tune(self):
        for field, value in (('l_current_min', 0), ('l_current_max', 141), ('l_in_current_min', -5), ('l_current_max_scale', .5)):
            with self.subTest(field=field):
                original = (self.source / 'motor_configuration.bin').read_bytes()
                motor_field(self.source, field, value)
                with self.assertRaises(ValueError): self.prepare()
                (self.source / 'motor_configuration.bin').write_bytes(original)
                refresh(self.source)
        uuid_field(self.source, '22' * 12)
        with self.assertRaises(ValueError): self.prepare()

    def test_exact_firmware_build_guard(self):
        good, _, _ = snapshot(self.target)
        for field, value in (('firmware', '6.00'), ('hardware', '75_100_V2'), ('test_version', 1), ('firmware_name', 'custom')):
            identity = dict(good['identity'], **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                fleet.identity_guard(identity, FAKE_UUID)
        data = bytearray((self.target / 'firmware.bin').read_bytes())
        data[2] = 0
        (self.target / 'firmware.bin').write_bytes(data)
        refresh(self.target)
        with self.assertRaises(ValueError): self.prepare()

    def test_target_app_preconditions_rest_and_finite_fields(self):
        good, _, _ = snapshot(self.target)
        for field, expected in fleet.FILTER_PRECONDITIONS.items():
            changed = copy.deepcopy(good)
            changed['app_configuration']['values'][field] = expected + 1
            with self.subTest(field=field), self.assertRaises(ValueError): fleet.capture_guard(changed)
        for field, value in (('erpm', 51), ('motor_current_a', 1.01), ('fault_code', 1), ('timeout_active', True), ('kill_switch_active', True)):
            changed = copy.deepcopy(good)
            changed['telemetry'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): fleet.capture_guard(changed)
        changed = copy.deepcopy(good)
        changed['motor_configuration']['values']['foc_motor_r'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'Nonfinite'): fleet.capture_guard(changed)

    def test_complete_capture_and_untampered_manifest_required(self):
        f = self.target / 'motor_configuration.bin'
        original = f.read_bytes()
        f.write_bytes(original[:-1])
        with self.assertRaises(ValueError): self.prepare()
        f.write_bytes(original)
        m = json.loads((self.target / 'manifest.json').read_text())
        m['capture_complete'] = False
        (self.target / 'manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError): self.prepare()

    def test_filter_only_uuid_wrapper_changes_core_and_import_format_exact(self):
        plan, artifacts = self.prepare()
        template = fleet.FILTER_SOURCE.read_bytes()
        adapted = artifacts['filter_source']
        self.assertEqual(adapted[:3732], template[:3732])
        self.assertEqual(sha256(adapted[:3732]), fleet.FILTER_CORE_SHA)
        self.assertIn(b"'(1 2 3 4 5 6 7 8 9 10 11 12)", adapted[3732:])
        self.assertNotIn(b"'(55 0 78 0 9 81 52 48 55 53 55 57)", adapted)
        self.assertEqual(artifacts['filter_blob'], adapted + b'\0\0\0')
        self.assertEqual(sha256(artifacts['filter_blob']), plan['filter']['code_blob_sha256'])
        self.assertFalse(plan['filter']['kart3_installers_compatible'])
        self.assertIn(b"'(6 2 0)", adapted)

    def test_changed_filter_source_refused(self):
        bad = self.base / 'bad.lisp'
        bad.write_bytes(fleet.FILTER_SOURCE.read_bytes() + b'\n')
        with patch.object(fleet, 'FILTER_SOURCE', bad), self.assertRaises(ValueError): self.prepare()

    def test_output_recomputes_preserves_inputs_and_refuses_existing_or_nested(self):
        plan, artifacts = self.prepare()
        before = {str(p): p.read_bytes() for d in (self.source, self.target) for p in d.iterdir()}
        out = self.base / 'result'
        fleet.write_plan(plan, artifacts, out)
        rebuilt, data = fleet.prepare(out / 'source', out / 'before', kart_id=4, target_uuid=FAKE_UUID)
        for key in ('patches', 'summary', 'remaining_differences', 'expected_before_sha256', 'filter'):
            self.assertEqual(plan[key], rebuilt[key], key)
        self.assertEqual(data['proposed_motor'], artifacts['proposed_motor'])
        for name, data in before.items(): self.assertEqual(Path(name).read_bytes(), data)
        with self.assertRaises(FileExistsError): fleet.write_plan(plan, artifacts, out)
        for dest in (self.target / 'output', self.source / 'output'):
            with self.assertRaises(ValueError): fleet.write_plan(plan, artifacts, dest)
            self.assertFalse(dest.exists())
        self.assertIn('not the complete source tune', (out / 'README.md').read_text())

    def test_cli_offline_only_and_capture_allowlist_unchanged(self):
        argv = ['prepare_fleet_kart.py', '--source-kart3', str(self.source), '--target', str(self.target),
                '--kart-id', '4', '--target-uuid', FAKE_UUID, '--out', str(self.base / 'cli')]
        with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as out:
            fleet.main()
        self.assertIn('OFFLINE ONLY', out.getvalue())
        for option in ('--apply', '--port'):
            with patch.object(sys, 'argv', argv + [option]), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                fleet.main()
        self.assertEqual(set(READ_COMMANDS), {0, 4, 14, 17})
        with self.assertRaises(ValueError): query_frame(13)


if __name__ == '__main__':
    unittest.main()
