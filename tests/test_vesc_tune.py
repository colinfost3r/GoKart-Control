"""Offline-only twelve-field trial preparation and preservation tests; no hardware."""
from contextlib import redirect_stderr, redirect_stdout
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/vesc'))
import tune
from capture import query_frame
from decode import decode_payloads

REFERENCE=ROOT/'hardware/vesc/baseline-kart/2026-11-05/raw'
CURRENT=ROOT/'hardware/vesc/kart3/2026-11-10/usb-before-tune/raw'
EXPECTED_FIELDS={'l_current_max','l_current_min','l_in_current_max','l_min_erpm','l_max_erpm','l_max_duty',
                 'foc_fw_current_max','foc_fw_duty_start','foc_openloop_rpm','foc_sl_erpm',
                 'cc_ramp_step_max','m_motor_temp_sens_type'}


def fixture(path,source=CURRENT):
    path.mkdir()
    for name in tune.READ_COMMANDS.values():
        shutil.copyfile(source/(name+'.bin'),path/(name+'.bin'))
    manifest=tune.manifest_path(source).read_bytes()
    (path/'manifest.json').write_bytes(manifest)
    return path


def refresh_hashes(path):
    p=path/'manifest.json';m=json.loads(p.read_text())
    for q in m['queries']:
        data=(path/(q['name']+'.bin')).read_bytes()
        q['sha256']=hashlib.sha256(data).hexdigest();q['payload_bytes']=len(data)
    # Deliberately modified fixtures are test-only; identity validation must come
    # from payload parsing and the fixed target pin, not a stale copied declaration.
    m.pop('identity',None)
    m['procedure']='TEST FIXTURE ONLY; not new hardware evidence'
    p.write_text(json.dumps(m))


class TunePreparationTests(unittest.TestCase):
    def test_exact_twelve_changes_and_all_other_values_preserved(self):
        plan,artifacts=tune.prepare(REFERENCE,CURRENT)
        self.assertEqual(set(tune.TRIAL_FIELDS),EXPECTED_FIELDS)
        self.assertEqual(len(tune.TRIAL_FIELDS),12)
        self.assertEqual(plan['summary']['actually_changed_fields'],12)
        self.assertEqual(plan['summary']['retained_value_fields'],364)
        self.assertFalse(plan['apply_supported'])
        self.assertEqual(plan['status'],'review_trial_not_applied_not_safety_certification')
        before=decode_payloads(artifacts['before'])
        proposed=dict(artifacts['before']);proposed['motor_configuration']=artifacts['proposed_motor']
        after=decode_payloads(proposed);ref=decode_payloads(artifacts['reference'])
        for name,value in before['motor_configuration']['values'].items():
            self.assertEqual(after['motor_configuration']['values'][name],
                             ref['motor_configuration']['values'][name] if name in EXPECTED_FIELDS else value,name)
        self.assertEqual(before['app_configuration'],after['app_configuration'])
        self.assertEqual(artifacts['before']['app_configuration'],proposed['app_configuration'])
        self.assertEqual(after['motor_configuration']['values']['foc_fw_current_max'],95)
        self.assertEqual(after['motor_configuration']['values']['l_current_min'],0)
        self.assertEqual(after['motor_configuration']['values']['m_motor_temp_sens_type'],8)

    def test_raw_byte_patch_is_confined_to_allowlisted_motor_spans(self):
        _,a=tune.prepare(REFERENCE,CURRENT)
        spans=tune.motor_spans(a['before']['motor_configuration'])
        allowed=set()
        for name in EXPECTED_FIELDS:
            start,end=spans[name];allowed.update(range(start,end))
            self.assertEqual(a['proposed_motor'][start:end],a['reference']['motor_configuration'][start:end])
        before=a['before']['motor_configuration']
        self.assertEqual(a['proposed_motor'][:5],before[:5])
        self.assertEqual(a['proposed_motor'][0],14)  # intentionally not a write payload
        self.assertEqual(len(a['proposed_motor']),len(before))
        for i,value in enumerate(before):
            if i not in allowed:self.assertEqual(a['proposed_motor'][i],value,i)
        preserved=['foc_hall_table__1','foc_motor_r','foc_motor_l','foc_motor_flux_linkage',
                   'foc_current_kp','foc_current_ki','foc_offsets_current__0','foc_offsets_voltage__0',
                   'foc_phase_filter_enable','p_pid_offset','si_motor_poles','si_gear_ratio','si_wheel_diameter',
                   'l_abs_current_max','l_min_vin','l_in_current_min','s_pid_allow_braking']
        for name in preserved:
            start,end=spans[name];self.assertEqual(a['proposed_motor'][start:end],before[start:end],name)

    def test_plan_contains_complete_376_field_audit_and_critical_caveats(self):
        p,_=tune.prepare(REFERENCE,CURRENT)
        rows=[r for g in p['field_audit'].values() for r in g['fields']]
        self.assertEqual(len(rows),376)
        self.assertEqual(sum(r['status']=='different' for r in rows),12)
        self.assertEqual(sum(r['trial_action']=='retain_exact_current_bytes' for r in rows),364)
        self.assertIn('NOT a temporary store=0',p['persistence_warning'])
        self.assertIn('conf_general_store_mc_configuration',p['persistence_warning'])
        text=tune.render_plan(p)
        self.assertIn('PREPARED ONLY',text)
        self.assertIn('6.33x',text)
        self.assertIn('reverse-switch',text)
        self.assertIn('2.48',text)
        self.assertIn('no retry',text)

    def test_wrong_target_uuid_hardware_or_firmware_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for part in ('uuid','hardware','firmware'):
                path=fixture(Path(tmp)/part)
                original=(path/'firmware.bin').read_bytes();value=bytearray(original)
                if part=='uuid':value[original.index(0,3)+1]^=1
                elif part=='hardware':value[3:12]=b'75_100_V2'
                else:value[2]=0  # supported decoder version, wrong fixed target
                (path/'firmware.bin').write_bytes(value);refresh_hashes(path)
                with self.subTest(part=part),self.assertRaises(ValueError):tune.prepare(REFERENCE,path)

    def test_exact_dated_reference_required_even_if_schema_and_hash_manifest_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/'reference',REFERENCE)
            data=bytearray((path/'motor_configuration.bin').read_bytes())
            start,end=tune.motor_spans(data)['l_current_max'];data[start:end]=struct.pack('>f',150)
            (path/'motor_configuration.bin').write_bytes(data);refresh_hashes(path)
            with self.assertRaisesRegex(ValueError,'exact dated'):tune.prepare(path,CURRENT)

    def test_stationary_guard_rejects_fault_motion_or_nonzero_current(self):
        _,data,_=tune.snapshot(CURRENT);telemetry=decode_payloads(data)['telemetry']
        tune.require_stationary(telemetry)  # actual idle duty is 0.002, ERPM/current zero
        for field,values in [('erpm',(1,-1)),('motor_current_a',(0.01,-0.01)),
                             ('battery_current_a',(0.01,-0.01)),('fault_code',(1,))]:
            for value in values:
                changed=dict(telemetry);changed[field]=value
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):tune.require_stationary(changed)
        for field in ('timeout_active','kill_switch_active'):
            changed=dict(telemetry);changed[field]=True
            with self.assertRaises(ValueError):tune.require_stationary(changed)
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/'moving')
            raw=bytearray((path/'telemetry.bin').read_bytes());raw[23:27]=struct.pack('>i',100)
            (path/'telemetry.bin').write_bytes(raw);refresh_hashes(path)
            with self.assertRaisesRegex(ValueError,'stationary'):tune.prepare(REFERENCE,path)

    def test_bad_configuration_schema_truncation_and_untrusted_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('motor_configuration','app_configuration'):
                for mode in ('short','extra','signature'):
                    path=fixture(Path(tmp)/(name+mode));p=path/(name+'.bin');data=p.read_bytes()
                    invalid=data[:-1] if mode=='short' else data+b'\0' if mode=='extra' else data[:1]+b'\0'*4+data[5:]
                    p.write_bytes(invalid);refresh_hashes(path)
                    with self.subTest(name=name,mode=mode),self.assertRaises(ValueError):tune.prepare(REFERENCE,path)
            path=fixture(Path(tmp)/'bad-manifest');p=path/'manifest.json';m=json.loads(p.read_text());m['capture_complete']=False;p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):tune.prepare(REFERENCE,path)

    def test_outputs_preserve_input_snapshots_and_recompute_deterministically(self):
        plan,a=tune.prepare(REFERENCE,CURRENT)
        originals={str(p):p.read_bytes() for source in (REFERENCE,CURRENT) for p in source.glob('*.bin')}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'trial';tune.write_trial(plan,a,out)
            stored=json.loads((out/'trial.json').read_text())
            self.assertEqual(stored,plan)
            self.assertEqual((out/'proposed_motor_response.bin').read_bytes(),a['proposed_motor'])
            for side in ('reference','before'):
                self.assertEqual((out/side/'manifest.json').read_bytes(),a[side+'_manifest'])
                for name,data in a[side].items():self.assertEqual((out/side/(name+'.bin')).read_bytes(),data)
            regenerated,b=tune.prepare(out/'reference',out/'before')
            self.assertEqual(b['proposed_motor'],a['proposed_motor'])
            for key in ('patches','summary','field_audit','expected_before_sha256','proposed_motor_response_sha256','allowlisted_motor_fields'):
                self.assertEqual(regenerated[key],plan[key],key)
        self.assertTrue(all(Path(p).read_bytes()==data for p,data in originals.items()))

    def test_existing_output_and_output_inside_capture_are_rejected(self):
        plan,a=tune.prepare(REFERENCE,CURRENT)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'existing';out.mkdir();marker=out/'marker';marker.write_text('keep')
            with self.assertRaises(FileExistsError):tune.write_trial(plan,a,out)
            self.assertEqual(marker.read_text(),'keep')
        with self.assertRaisesRegex(ValueError,'outside'):tune.write_trial(plan,a,CURRENT/'trial-forbidden')
        self.assertFalse((CURRENT/'trial-forbidden').exists())

    def test_cli_has_no_apply_or_port_option_and_read_allowlist_is_unchanged(self):
        with self.assertRaises(ValueError):query_frame(13)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'trial'
            args=['tune.py',str(REFERENCE),str(CURRENT),'--out',str(out)]
            with patch.object(sys,'argv',args),redirect_stdout(io.StringIO()) as log:tune.main()
            self.assertIn('OFFLINE ONLY',log.getvalue())
            for flag in ('--apply','--port'):
                with patch.object(sys,'argv',args+[flag]),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:tune.main()
                self.assertEqual(error.exception.code,2)


if __name__=='__main__':unittest.main()
