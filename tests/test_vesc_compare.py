"""Offline comparison tests; synthetic 6.02 data is never claimed as kart 3 evidence."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/vesc'))
import compare
from capture import READ_COMMANDS
from decode import DEFAULT_SCHEMA, Reader

BASELINE = ROOT/'hardware/vesc/baseline-kart/2026-11-05'
RAW = BASELINE/'raw'


def field_offset(data, schema, wanted):
    """Locate a test mutation using the documented transport widths, not guessed offsets."""
    root = ET.parse(schema).getroot()
    params = {p.tag:p for p in root.find('Params')}
    reader = Reader(data, 5)
    for item in root.find('SerOrder'):
        name, param = item.text, params[item.text]
        if name == wanted:
            return reader.pos
        kind, tx = int(param.findtext('type','0')), int(param.findtext('vTx','0'))
        if kind in (4,5,6):
            reader.read('B')
        elif kind == 2:
            reader.read({1:'B',2:'b',3:'H',4:'h',5:'I',6:'i'}[tx])
        elif kind == 1:
            reader.read('H' if tx == 7 else 'I')
        elif kind == 3:
            reader.string()
        else:
            raise AssertionError(kind)
    raise AssertionError(wanted)


def fixture(directory, synthetic=False):
    directory.mkdir()
    for name in READ_COMMANDS.values():
        shutil.copyfile(RAW/(name+'.bin'), directory/(name+'.bin'))
    manifest = json.loads((BASELINE/'manifest.json').read_text())
    manifest['procedure'] = 'TEST FIXTURE ONLY; copied bytes plus synthetic mutations, not a hardware read'
    manifest['controller_assignment'] = 'TEST FIXTURE ONLY; not a live kart identity'
    if synthetic:
        # Deliberately unrelated UUID so this can never be mistaken for real kart 3 evidence.
        old = (directory/'firmware.bin').read_bytes()
        tail = old[old.index(0,3)+1:]
        identity = b'\0\x06\x02TEST_FIXTURE_HW\0' + bytes.fromhex('1234567890abcdef12345678') + tail[12:]
        (directory/'firmware.bin').write_bytes(identity)
        motor = bytearray((directory/'motor_configuration.bin').read_bytes())
        pos = field_offset(motor, DEFAULT_SCHEMA/'parameters_mcconf.xml', 'l_current_max')
        motor[pos:pos+4] = struct.pack('>f', 120.0)
        (directory/'motor_configuration.bin').write_bytes(motor)
        app = bytearray((directory/'app_configuration.bin').read_bytes())
        pos = field_offset(app, DEFAULT_SCHEMA/'parameters_appconf.xml', 'controller_id')
        app[pos] = 3
        (directory/'app_configuration.bin').write_bytes(app)
    (directory/'manifest.json').write_text(json.dumps(manifest))
    refresh_hashes(directory)
    return directory


def refresh_hashes(directory):
    path = directory/'manifest.json'
    manifest = json.loads(path.read_text())
    for query in manifest['queries']:
        data = (directory/(query['name']+'.bin')).read_bytes()
        query['payload_bytes'] = len(data)
        query['sha256'] = hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(manifest))


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.candidate = fixture(self.root/'synthetic-candidate', synthetic=True)

    def report(self):
        return compare.build_report(RAW, self.candidate)

    def test_real_kart3_usb_capture_is_complete_and_distinct_from_baseline(self):
        # Immutable real 6.02 bytes, captured read-only on November 10. No device access.
        candidate = ROOT/'hardware/vesc/kart3/2026-11-10/usb-before-tune/raw'
        report = compare.build_report(RAW, candidate)
        self.assertEqual(report['candidate']['identity']['uuid'], '37004e000951343037353739')
        self.assertEqual(report['candidate']['identity']['hardware'], '75_300_R2')
        self.assertEqual(report['candidate']['identity']['firmware'], '6.02')
        self.assertEqual(report['summary'], {'field_count':376, 'equal_count':326, 'different_count':50})
        motor = report['configurations']['motor_configuration']
        app = report['configurations']['app_configuration']
        self.assertEqual((motor['different_count'], app['different_count']), (40, 10))
        values = {row['field']:row['candidate'] for row in motor['fields']}
        self.assertEqual(values['l_current_min'], -50.0)
        self.assertEqual(values['foc_fw_current_max'], 15.0)
        self.assertEqual(values['m_motor_temp_sens_type'], 0)
        self.assertEqual(values['foc_phase_filter_enable'], 1)
        self.assertTrue(report['candidate']['provenance']['payload_hashes_verified'])
        self.assertTrue(report['candidate']['provenance']['manifest_identity_verified'])

    def test_every_field_and_expected_changes_are_recorded(self):
        report = self.report()
        self.assertEqual(report['summary'], {'field_count':376,'equal_count':374,'different_count':2})
        fields = [row for group in report['configurations'].values() for row in group['fields']]
        changed = [row for row in fields if row['status'] == 'different']
        self.assertEqual([(row['field'],row['reference'],row['candidate']) for row in changed],
                         [('l_current_max',140.0,120.0),('controller_id',69,3)])
        self.assertEqual(len(fields), 376)
        self.assertEqual(len({(name,r['field']) for name,g in report['configurations'].items() for r in g['fields']}), 376)
        self.assertEqual(report['reference']['identity']['firmware'], '6.00')
        self.assertEqual(report['candidate']['identity']['firmware'], '6.02')
        self.assertEqual(report['candidate']['identity']['hardware'], 'TEST_FIXTURE_HW')
        self.assertEqual(report['operation'], 'offline_compare_only')
        markdown = compare.render_markdown(report)
        for row in fields:
            self.assertIn('| '+row['field']+' | ', markdown)
        self.assertIn('TEST FIXTURE ONLY', markdown)
        self.assertIn('2.48', markdown)
        self.assertIn('speedcal to 1.0 without', markdown)
        self.assertNotIn('recommended_value', json.dumps(report))

    def test_identical_capture_reports_all_equal_without_omission(self):
        report = compare.build_report(RAW, RAW)
        self.assertEqual(report['summary'], {'field_count':376,'equal_count':376,'different_count':0})
        self.assertEqual(len(report['configurations']['motor_configuration']['fields']),189)
        self.assertEqual(len(report['configurations']['app_configuration']['fields']),187)

    def test_dates_hashes_identity_and_runtime_scope_retained(self):
        report = self.report()
        provenance = report['reference']['provenance']
        self.assertEqual(provenance['capture_date'], '2026-11-05')
        self.assertEqual(provenance['scope'], compare.SCOPE)
        self.assertTrue(provenance['payload_hashes_verified'])
        self.assertIsNone(provenance['manifest_identity_verified'])
        self.assertEqual(provenance['queries'][0]['timestamp_basis'],'capture_file_mtime')
        self.assertEqual(provenance['queries'][0]['captured_at'],'2026-11-05T13:13:30.294726-05:00')
        self.assertEqual(provenance['manifest_sha256'], hashlib.sha256((BASELINE/'manifest.json').read_bytes()).hexdigest())
        self.assertEqual(report['reference']['identity']['uuid'],'2c004c000951343037353739')
        self.assertFalse(report['reference']['telemetry']['motor_temp_valid'])

    def test_zero_bitfields_are_not_mislabeled_as_enabled(self):
        report = self.report()
        fields = {row['field']:row for row in report['configurations']['app_configuration']['fields']}
        for name in ('app_adc_conf.buttons','can_status_msgs_r2'):
            self.assertNotIn('enum_labels', fields[name])
            self.assertEqual(fields[name]['bitfield_labels'], {'reference':[],'candidate':[]})
            self.assertIn('bits: []', compare.display_value(fields[name], 'reference'))

    def test_untrusted_hash_and_incomplete_manifest_rejected(self):
        path = self.candidate/'manifest.json'
        original = json.loads(path.read_text())
        for edit in ('hash','incomplete','scope','duplicate','crc','date','identity'):
            manifest = copy.deepcopy(original)
            if edit == 'hash': manifest['queries'][0]['sha256'] = '0'*64
            elif edit == 'incomplete': manifest['capture_complete'] = False
            elif edit == 'scope': manifest['scope'] = 'saved_flash_backup'
            elif edit == 'duplicate': manifest['queries'][1] = manifest['queries'][0]
            elif edit == 'crc': manifest['queries'][0]['crc_verified_on_receipt'] = False
            elif edit == 'date': manifest['queries'][0]['captured_at'] = '2026-11-10T15:00:00'
            elif edit == 'identity': manifest['identity'] = {'firmware':'6.00','hardware':'wrong','uuid':'0'*24}
            path.write_text(json.dumps(manifest))
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                self.report()
        path.write_text(json.dumps(original))

    def test_bad_signatures_truncated_and_trailing_payloads_rejected_even_with_matching_hash(self):
        for name in ('motor_configuration','app_configuration'):
            path = self.candidate/(name+'.bin')
            original = path.read_bytes()
            for value in (original[:-1], original+b'\x00', original[:1]+b'\x00'*4+original[5:]):
                path.write_bytes(value)
                refresh_hashes(self.candidate)
                with self.subTest(name=name,size=len(value)), self.assertRaises(ValueError):
                    self.report()
            path.write_bytes(original)
            refresh_hashes(self.candidate)
        path = self.candidate/'telemetry.bin'
        path.write_bytes(path.read_bytes()[:-1])
        refresh_hashes(self.candidate)
        with self.assertRaises(ValueError):
            self.report()

    def test_missing_or_replaced_field_rejected_even_if_counts_match(self):
        reference = compare.load_capture(RAW)
        candidate = compare.load_capture(self.candidate)
        for name in compare.CONFIGURATIONS:
            for replacement in (False,True):
                changed = copy.deepcopy(candidate)
                values = changed[name]['values']
                key = next(iter(values))
                value = values.pop(key)
                if replacement: values['unknown_new_field'] = value
                with self.subTest(name=name,replacement=replacement), self.assertRaises(ValueError):
                    compare.compare_decoded(reference,changed)

    def test_manifests_require_explicit_resolution_when_ambiguous(self):
        raw = self.root/'older'/'raw'
        raw.parent.mkdir()
        shutil.copytree(self.candidate,raw)
        shutil.copyfile(raw/'manifest.json',raw.parent/'manifest.json')
        with self.assertRaises(ValueError):
            compare.load_capture(raw)
        capture = compare.load_capture(raw, raw/'manifest.json')
        self.assertEqual(capture['identity']['firmware'],'6.02')
        (raw/'manifest.json').unlink()
        (raw.parent/'manifest.json').unlink()
        with self.assertRaises(ValueError):
            compare.load_capture(raw)

    def test_report_creation_is_new_and_cli_is_offline(self):
        out = self.root/'report'
        args = ['compare.py',str(RAW),str(self.candidate),'--out',str(out)]
        with patch.object(sys,'argv',args), redirect_stdout(io.StringIO()) as stdout:
            compare.main()
        self.assertIn('376 settings',stdout.getvalue())
        data = (out/'comparison.json').read_bytes()
        self.assertEqual(json.loads(data)['summary']['different_count'],2)
        self.assertIn('l_current_max',(out/'comparison.md').read_text())
        with patch.object(sys,'argv',args), self.assertRaises(FileExistsError):
            compare.main()
        self.assertEqual((out/'comparison.json').read_bytes(),data)
        with self.assertRaises(FileExistsError):
            compare.write_report(self.report(),out)

    def test_invalid_cli_input_creates_no_report(self):
        path = self.candidate/'motor_configuration.bin'
        path.write_bytes(path.read_bytes()[:-1])
        refresh_hashes(self.candidate)
        out = self.root/'invalid-report'
        with patch.object(sys,'argv',['compare.py',str(RAW),str(self.candidate),'--out',str(out)]), self.assertRaises(ValueError):
            compare.main()
        self.assertFalse(out.exists())

    def test_markdown_cells_escape_external_text(self):
        self.assertEqual(compare.cell('one|two\n<script>'), 'one&#124;two<br>&lt;script&gt;')


if __name__ == '__main__':
    unittest.main()
