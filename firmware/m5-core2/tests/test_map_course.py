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
            exe=Path(t)/'check';subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g','-I'+str(include),'-I'+str(ROOT/'firmware/m5-core2'), '-I'+str(ROOT/'firmware/libraries/M5Game/src'),'-I'+str(BASE/'firmware/libraries/M5DisplayLink'),str(path),'-o',str(exe)],check=True)
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
    def test_native_renderer_shows_demo_and_restrictions(self):
        # Compile the actual shared renderer, then inspect its emitted SVG at 320x240.
        import xml.etree.ElementTree as ET
        include=Path(os.environ.get('ARDUINOJSON_DIR','/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src'))
        with tempfile.TemporaryDirectory() as t:
            exe=Path(t)/'render'
            subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(include),'-I'+str(ROOT/'firmware/m5-core2'), '-I'+str(ROOT/'firmware/libraries/M5Game/src'),'-I'+str(BASE/'firmware/libraries/M5DisplayLink'),str(ROOT/'firmware/m5-core2/tests/render_driver.cpp'),'-o',str(exe)],check=True)
            for page in ('map','dash'):
                for scene in ('startup','invite','invitation','joined','download','ready','used','download-error','host-lost','gps-lost','link-lost','no-course','fault','stopped','slow','live'):
                    svg=subprocess.check_output([str(exe),scene,page],text=True);doc=ET.fromstring(svg)
                    labels=[e for e in doc if e.tag.endswith('text')]
                    text=' '.join(e.text or '' for e in labels)
                    self.assertNotIn('KART 03',text)
                    if scene=='startup':
                        self.assertIn('OpenStreetMap',text)
                        continue
                    self.assertNotIn('OpenStreetMap',text)
                    if scene=='fault':self.assertIn('VESC FAULT 5',text)
                    if scene=='stopped':self.assertIn('PIT STOP ACTIVE',text)
                    if scene=='slow':self.assertIn('PIT SLOW / 5 MPH',text)
                    if page=='map' and scene=='live':self.assertNotIn('SHELL',text)
                    if page=='map':
                        if scene!='live':self.assertIn('DEMO',text)
                        self.assertNotIn('N UP',text)
                        self.assertNotIn('20m /',text)
                        self.assertIn('-- V' if scene=='link-lost' else '79.4 V',text)
                        if scene=='ready':
                            self.assertIn('S/F',text)
                            self.assertNotIn('OpenStreetMap contributors',text)
                        if scene in ('live','no-course'):self.assertNotIn('S/F',text)
                    for e in labels:
                        self.assertLessEqual(float(e.attrib['x'])+float(e.attrib['textLength']),320)
                        self.assertLessEqual(float(e.attrib['y']),240)
    def test_native_startup_and_navigation_timers(self):
        self.assertIn('startup/page hold passed',self.native(ROOT/'firmware/m5-core2/tests/screen_lifecycle_test.cpp'))
    def test_startup_press_cannot_become_a_mode_request(self):
        old=BASE/'firmware/tests/test_m5_touch_request.py';tree=ast.parse(old.read_text());harness=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets) and isinstance(n.value,ast.Constant))
        source=(ROOT/'firmware/m5-core2/m5-core2.ino').read_text()
        for signature in ('static void requestWirelessMode(','void touch('):
            at=source.index(signature);end=re.search(r'^}',source[at:],re.M).end();harness+=source[at:at+end]+'\n'
        harness+=r"""
int main(){
 startupScreen.begin(100);ready(100);press();touch(100);held();ready(5000);touch(5000);
 assert(wireless.calls==0);ready(5200);touch(5200);ready(7000);touch(7000);
 assert(wireless.calls==0&&!state.pending); // A held startup press is not a fresh intent.
 release();touch(7001);ready(7100);press();touch(7100);held();ready(7750);touch(7750);
 assert(wireless.calls==1);
 release();touch(7800);M5.Touch.detail.x=280;M5.Touch.detail.y=20;press();touch(7900);
 held();touch(9699);assert(!maintenanceMenu);touch(9700);assert(maintenanceMenu);
 assert(wireless.calls==1);return 0;
}
"""
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'startup_touch.cpp';p.write_text(harness);self.native(p)
    def test_maintenance_back_cannot_send_a_mode(self):
        old=BASE/'firmware/tests/test_m5_touch_request.py';tree=ast.parse(old.read_text());harness=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets) and isinstance(n.value,ast.Constant))
        source=(ROOT/'firmware/m5-core2/m5-core2.ino').read_text()
        for signature in ('static void requestWirelessMode(','void touch('):
            at=source.index(signature);end=re.search(r'^}',source[at:],re.M).end();harness+=source[at:at+end]+'\n'
        harness+=r"""
int main(){
 for(int x:{40,150,250}){
  release();touch(100);maintenanceMenu=true;mapPage=false;M5.Touch.detail.x=x;M5.Touch.detail.y=220;
  ready(200);press();touch(200);assert(!maintenanceMenu);
  held();ready(1000);touch(1000);ready(3000);touch(3000);
  assert(wireless.calls==0&&!state.pending&&heldMode==-1);
 }
 release();touch(3100);M5.Touch.detail.x=40;ready(3200);press();touch(3200);held();ready(3850);touch(3850);
 assert(wireless.calls==1);return 0;
}
"""
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'maintenance_back.cpp';p.write_text(harness);self.native(p)
    def test_native_display_metrics(self):
        self.assertIn('stale telemetry passed',self.native(ROOT/'firmware/m5-core2/tests/display_metrics_test.cpp'))
    def test_player_preview_states(self):
        self.assertIn('timer wrap passed',self.native(ROOT/'firmware/m5-core2/tests/player_preview_test.cpp'))
    def test_demo_touch_cannot_request_modes_or_double_fire(self):
        old=BASE/'firmware/tests/test_m5_touch_request.py';tree=ast.parse(old.read_text());harness=next(n.value.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='harness' for t in n.targets) and isinstance(n.value,ast.Constant))
        harness=harness.replace('#define M5_USE_ESPNOW 1','#define M5_USE_ESPNOW 0').replace('#define M5_DEMO 0','#define M5_DEMO 1')
        harness+='m5dash::PlayerPreview playerPreview;\n'
        source=(ROOT/'firmware/m5-core2/m5-core2.ino').read_text();at=source.index('void touch(');end=re.search(r'^}',source[at:],re.M).end();harness+=source[at:at+end]
        harness+=r'''
int main(){
 ready(100);press();touch(100);held();ready(1000);touch(1000);assert(!state.pending&&wireless.calls==0);
 release();touch(1001);M5.Touch.detail.x=234;M5.Touch.detail.y=40;press();touch(1100);assert(playerPreview.overlay);
 release();touch(1101);M5.Touch.detail.x=200;M5.Touch.detail.y=160;press();touch(1200);playerPreview.tick(4200);
 assert(playerPreview.stage==m5dash::PlayerPreview::Stage::Ready&&!playerPreview.overlay);
 held();mapPage=true;M5.Touch.detail.x=280;M5.Touch.detail.y=220;touch(4300);assert(playerPreview.fired==0);
 release();touch(4301);press();touch(4400);held();touch(5000);assert(playerPreview.fired==1&&wireless.calls==0&&!state.pending);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'demo_touch.cpp';p.write_text(harness);self.native(p)
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
 release();touch(2001);M5.Touch.detail.x=280;M5.Touch.detail.y=35;press();touch(2100);assert(!mapPage);
 release();touch(2101);M5.Touch.detail.x=40;M5.Touch.detail.y=220;ready(2200);press();touch(2200);held();ready(2850);touch(2850);assert(wireless.calls==1);
 release();touch(2851);mapPage=true;M5.Touch.detail.x=280;M5.Touch.detail.y=20;press();touch(3000);held();touch(4800);assert(maintenanceMenu&&wireless.calls==1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'touch.cpp';path.write_text(harness);self.native(path)
if __name__=='__main__':unittest.main()
