"""Cross-language host package -> native transfer/cache/player, plus real dispatch in control runtime."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'kart/server'))
import m5_course as host
DOC={'source':'freeplay','enabled':True,'track':{'points':[[41,-73],[41.0001,-73],[41.0001,-73.0001]],'closed':True},'zones':[
 {'type':'item','shape':'circle','lat':41,'lon':-73,'r_m':4},
 {'type':'lapline','shape':'line','a':[41,-73.00005],'b':[41,-72.99995],'min_lap_s':15}]}

class GameTests(unittest.TestCase):
 def package(self,**kwargs):return host.export(DOC,host=2,instance=123,revision=1,**kwargs)
 def test_native_transfer_cache_and_player(self):
  inc=Path(os.environ.get('ARDUINOJSON_DIR','/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src'))
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp);(t/'course.bin').write_bytes(self.package())
   subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
    '-I'+str(inc),'-I'+str(ROOT/'firmware/libraries/M5Game/src'),'-I'+str(ROOT/'firmware/libraries/M5DisplayLink'),'-I'+str(ROOT/'firmware/m5-core2'),str(ROOT/'firmware/tests/m5_game.cpp'),'-o',str(t/'game')],check=True)
   subprocess.run([str(t/'game'),str(t/'course.bin')],check=True,timeout=20)
 def test_publisher_ack_pacing_and_commit(self):
  p=host.Publisher();data=self.package();p.start(data,0);now=0
  while p.phase!='ready':
   line=p.next_line(now);self.assertIsNotNone(line);self.assertIsNone(p.next_line(now+.1));action=line.split()[1]
   received=0 if action=='begin' else min(len(data),p.offset+64) if action=='chunk' else len(data)
   self.assertTrue(p.reply({'t':'share','action':action,'ok':True,'received':received,'digest':f'{p.digest:08x}'},now+.2));now+=.25
  self.assertIsNone(p.next_line(now));self.assertIsNone(p.payload)
 def test_publication_mismatch_timeout_and_no_retry(self):
  for bad in ('late','received','digest','rejected'):
   p=host.Publisher();p.start(self.package(),0);p.next_line(0)
   msg={'t':'share','action':'begin','ok':True,'received':0,'digest':f'{p.digest:08x}'}
   if bad=='received':msg['received']=1
   if bad=='digest':msg['digest']='00000000'
   if bad=='rejected':msg['ok']=False
   p.reply(msg,4 if bad=='late' else 1);self.assertEqual(p.phase,'error');self.assertIsNone(p.next_line(100))
 def test_bad_host_documents_fail_closed(self):
  for patch in ({'source':'pit'},{'enabled':False},{'track':[]},{'zones':[None]},{'zones':[{'type':'stop'}]}):
   d=dict(DOC,**patch)
   with self.subTest(patch=patch),self.assertRaises(ValueError):host.export(d,host=2,instance=1,revision=1)
 def test_host_200_point_route_simplifies_with_one_meter_bound(self):
  import math
  d=dict(DOC,track={'points':[[41+math.sin(i*2*math.pi/200)*.0005,-73+math.cos(i*2*math.pi/200)*.0005] for i in range(200)],'closed':True})
  p=host.export(d,host=2,instance=1,revision=1);self.assertLessEqual(struct.unpack_from('<H',p,16)[0],128)
 def test_host_pause_withdraws_and_waits_for_ack(self):
  import threading
  from types import SimpleNamespace
  from kart_server import App
  sent=[]
  fp=SimpleNamespace(_hosting=lambda:True,phase='ready',pause_reason=None,_my_id=lambda:2,prize_epoch=1,doc=lambda:DOC)
  app=SimpleNamespace(lock=threading.RLock(),demo=None,_connected=lambda:True,_m5_share_ready=True,_m5_was_eligible=False,_m5_withdraw=False,_m5_publish_key=None,freeplay=fp,m5_publisher=host.Publisher(),_load_json=lambda _:None,_send_text=lambda line,wait=False:sent.append(line) or True,log=SimpleNamespace(write=lambda *a,**kw:None))
  App._publish_m5_course(app,1);self.assertTrue(sent[-1].startswith('share begin'))
  fp.pause_reason='pit game';App._publish_m5_course(app,1.1);self.assertEqual(sent[-1],'share clear');self.assertTrue(app._m5_withdraw)
  app.m5_publisher.reply({'t':'share','action':'clear','ok':True},1.2);App._publish_m5_course(app,1.3);self.assertFalse(app._m5_withdraw)
  count=len(sent);App._publish_m5_course(app,2);self.assertEqual(len(sent),count)
  fp.pause_reason=None;App._publish_m5_course(app,3);self.assertTrue(sent[-1].startswith('share begin'))
 def test_course_pair_default_creates_private_plan_without_device(self):
  with tempfile.TemporaryDirectory() as tmp:
   plan=Path(tmp)/'private.json'
   result=subprocess.run([sys.executable,'-I',str(ROOT/'tools/m5/pair_course.py'),'--host-id','2','--kart-id','3','--host-mac','02:11:22:33:44:55','--core2-mac','02:66:77:88:99:aa','--plan',str(plan)],capture_output=True,text=True,check=True)
   self.assertTrue(json.loads(result.stdout)['no_device_opened']);self.assertEqual(plan.stat().st_mode&0o777,0o600);self.assertNotIn(json.loads(plan.read_text())['key'],result.stdout)
 def test_real_host_doc_has_start_finish(self):
  import kartcore
  self.assertTrue(hasattr(kartcore.FreeplayGame,'_lapline'))
  self.assertEqual(kartcore.MULTI_ITEM_TABLE[0][0],'boost')

if __name__=='__main__':unittest.main()
