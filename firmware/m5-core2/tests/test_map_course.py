"""Focused offline M5 map/provisioning checks. Never opens a hardware port."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
# Optional checkout override permits isolated staging before repository copy.
BASE=Path(os.environ.get('GOKART_SHARED_ROOT',str(ROOT)))
spec=importlib.util.spec_from_file_location('provision_course',ROOT/'tools/m5/provision_course.py')
provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)
DOC={'schema':1,'name':'Test outline','closed':True,'points':[[41.0938,-73.4163],[41.094,-73.416]]}

class Fake:
    def __init__(self,wrong=False,fail=None):self.calls=[];self.wrong=wrong;self.fail=fail
    def request(self,line,kind,action=None):
        self.calls.append(line)
        if kind=='m5_status':return {'fw':'m5-v1.5','transport':'espnow','kart':4 if self.wrong else 3,'course_proto':1}
        if self.fail==action:return {'t':'course','action':action,'ok':False,'error':'test_failure'}
        if action=='status':return {'t':'course','ok':True,'source':'internal','name':DOC['name'],'points':2,'closed':True,'record_crc32':provision.prepare(DOC)[2]}
        return {'t':'course','action':action,'ok':True}

class MapCourseTests(unittest.TestCase):
    def native(self,path):
        include=next((p for p in [Path(os.environ.get('ARDUINOJSON_DIR','/missing')),Path('/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src'),Path.home()/'Arduino/libraries/ArduinoJson/src'] if (p/'ArduinoJson.h').exists()),None)
        self.assertIsNotNone(include,'ArduinoJson headers required')
        with tempfile.TemporaryDirectory() as t:
            exe=Path(t)/'check';subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I'+str(include),'-I'+str(ROOT/'firmware/m5-core2'),'-I'+str(BASE/'firmware/libraries/M5DisplayLink'),str(path),'-o',str(exe)],check=True)
            return subprocess.run([str(exe)],check=True,capture_output=True,text=True).stdout
    def test_native_map_upload_and_storage(self):
        result=self.native(ROOT/'firmware/m5-core2/tests/map_course_test.cpp')
        self.assertIn('record_crc='+provision.prepare(DOC)[2],result)
    def test_pit_outline_contract(self):
        zones=json.loads((BASE/'pit/server/map/zones.json').read_text())
        clean,payload,crc=provision.prepare(dict(schema=1,name='Shop demonstration',**{k:v for k,v in zones['track'].items() if k in ('points','closed')}))
        self.assertEqual(len(clean['points']),len(zones['track']['points']))
        seq=list(provision.commands(payload));self.assertEqual(seq[-1],('commit','course commit'))
        chunks=[bytes.fromhex(line.split()[3]) for action,line in seq if action=='chunk'];self.assertEqual(b''.join(chunks),payload)
        self.assertTrue(all(len(x)<=128 for x in chunks));self.assertEqual(len(crc),8)
    def test_reject_invalid_without_mutation(self):
        for edit in ({'schema':True},{'closed':1},{'name':''},{'name':'x\x00bad'},{'points':[[0,0]]*129},{'points':[[91,0],[0,0]]},{'points':[[0,0],[0,0]]},{'points':[[True,0],[0,0]]},{'points':[[float('nan'),0],[0,0]]}):
            with self.subTest(edit=str(edit)),self.assertRaises(ValueError):provision.prepare(DOC|edit)
    def test_wrong_device_has_no_upload_commands(self):
        c=Fake(wrong=True)
        with self.assertRaises(ValueError):provision.upload(c,DOC,3)
        self.assertEqual(c.calls,['status'])
    def test_explicit_upload_readback(self):
        c=Fake();r=provision.upload(c,DOC,3);self.assertEqual(r['source'],'internal')
        self.assertEqual(c.calls.count('course commit'),1);self.assertEqual(c.calls[-1],'course status')
        self.assertFalse(any('reboot' in x or 'espnow' in x or 'mode ' in x for x in c.calls))
    def test_failed_upload_never_retries_or_clears(self):
        for action in ('begin','chunk','commit'):
            c=Fake(fail=action)
            with self.subTest(action=action),self.assertRaises(RuntimeError):provision.upload(c,DOC,3)
            self.assertNotIn('course clear',c.calls);self.assertLessEqual(c.calls.count('course commit'),1)
            self.assertTrue(c.calls[-1].startswith('course '+action))
    def test_default_is_offline(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'course.json';path.write_text(json.dumps(DOC))
            r=subprocess.run(['python3','-I',str(ROOT/'tools/m5/provision_course.py'),'--course',str(path)],capture_output=True,text=True,check=True)
            self.assertTrue(json.loads(r.stdout)['no_device_opened'])
    def test_map_fire_never_sends_and_dash_modes_still_work(self):
        old=BASE/'firmware/tests/test_m5_touch_request.py';tree=ast.parse(old.read_text());harness=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets) and isinstance(n.value,ast.Constant))
        source=(ROOT/'firmware/m5-core2/m5-core2.ino').read_text()
        for signature in ('static void requestWirelessMode(','void touch('):
            at=source.index(signature);end=re.search(r'^}',source[at:],re.M).end();harness+=source[at:at+end]+'\n'
        harness+='''
int main(){
 mapPage=true;ready(100);press();touch(100);held();ready(2000);touch(2000);
 assert(wireless.calls==0&&!state.pending&&heldMode==-1); // FIRE coordinates cannot reach hidden modes
 release();touch(2001);M5.Touch.detail.x=20;M5.Touch.detail.y=35;press();touch(2100);assert(!mapPage);
 release();touch(2101);M5.Touch.detail.x=40;M5.Touch.detail.y=220;ready(2200);press();touch(2200);held();ready(2850);touch(2850);assert(wireless.calls==1);
 release();touch(2851);mapPage=true;M5.Touch.detail.y=10;press();touch(3000);held();touch(4800);assert(maintenanceMenu&&wireless.calls==1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'touch.cpp';path.write_text(harness);self.native(path)
if __name__=='__main__':unittest.main()
