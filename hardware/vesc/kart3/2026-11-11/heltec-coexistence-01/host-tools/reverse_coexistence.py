#!/usr/bin/env python3
"""Bounded60s read-only kart3 pedal capture while Heltec owns BLE; no Lisp polling."""
import argparse,datetime,hashlib,json,time
from pathlib import Path
from pedal_trace_180s import Link,adc
from read_lisp import SerialConnection,require_identity
from rx_filter_control import UUID,require_app
from decode import decode_telemetry,decode_configuration,DEFAULT_SCHEMA
class ReadOnly(Link):
 def request(self,payload):
  if payload not in (b'\0',b'\x04',b'\x0e',b'\x11',b'\x20'):raise ValueError('Only five fixed getters; REPL is excluded')
  return super().request(payload)
def run(out):
 out.mkdir(parents=True,exist_ok=False);m={'complete':False,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':[0,4,14,17,32],'host_motor_config_reset_lifecycle_commands':False,'lisp_polled':False,'sample_seconds':60,'rows':0,'stall_candidates':[]}
 try:
  with SerialConnection('/dev/cu.usbmodem3041') as c:
   w=ReadOnly(c.fd,out);m['identity']=require_identity(w.request(b'\0'),UUID)
   before={'motor':w.request(b'\x0e'),'app':w.request(b'\x11')};require_app(before['app'])
   for name,data in before.items():(out/(name+'_before.bin')).write_bytes(data)
   conf=decode_configuration(before['motor'],DEFAULT_SCHEMA/'parameters_mcconf.xml',14)['values'];m['limits_before']={k:conf[k] for k in ('l_current_min','l_current_min_scale','l_current_max_scale','l_min_erpm','l_max_erpm')}
   if conf['l_current_min']!=-5 or conf['l_current_min_scale']!=1:raise ValueError('Brake limit changed')
   m['preflight']=[]
   for i in range(3):
    a=adc(w.request(b'\x20'));t=decode_telemetry(w.request(b'\x04'));m['preflight'].append({'adc':a,'telemetry':t})
    if not(0<=a['decoded1']<=.12 and abs(t['erpm'])<=50 and abs(t['iq_a'])<=1 and t['fault_code']==0 and not t['timeout_active'] and not t['kill_switch_active']):raise ValueError('Need released pedal, stopped wheels, nofault before recording')
    time.sleep(.1)
   print('RECORDING STARTED:60 seconds; operator wired pedal only; Heltec remains online.',flush=True)
   start=time.monotonic();nextconf=2;nextprint=0;candidate=None;reported=False;previous_cycle=None
   with (out/'samples.jsonl').open('w') as f:
    while time.monotonic()-start<60:
     cycle=time.monotonic();a=w.request(b'\x20');at=time.monotonic();v=w.request(b'\x04');vt=time.monotonic();t=decode_telemetry(v);decoded=adc(a)
     row={'seconds':at-start,'adc_at_monotonic':at-start,'values_at_monotonic':vt-start,'adc':decoded,'telemetry':t,'adc_hex':a.hex(),'values_hex':v.hex()};f.write(json.dumps(row)+'\n');f.flush();m['rows']+=1
     if t['fault_code'] or t['timeout_active'] or t['kill_switch_active']:raise ValueError('Fault/timeout/kill observed: releasepedal; no host cleanup')
     if previous_cycle is not None and cycle-previous_cycle>.35:candidate=None;reported=False
     previous_cycle=cycle
     qualified=decoded['decoded1']>.2 and abs(t['erpm'])<=50 and abs(t['iq_a'])<8
     if qualified:
      if candidate is None:candidate=cycle
      if not reported and cycle-candidate>=.2:
       m['stall_candidates'].append(row);print('POSSIBLE MISSED START '+json.dumps(row),flush=True);reported=True
     else:candidate=None;reported=False
     if cycle-start>=nextconf:
      if w.request(b'\x0e')!=before['motor']:raise ValueError('Motor settings changed during fixed-mode pedal test')
      nextconf=cycle-start+2
     if cycle-start>=nextprint:
      print(json.dumps({'seconds':round(row['seconds'],1),'pedal':decoded['decoded1'],'erpm':t['erpm'],'iq_a':t['iq_a'],'fault':t['fault_code']}),flush=True);nextprint=cycle-start+20
     time.sleep(max(0,.1-(time.monotonic()-cycle)))
   for name,cmd in (('motor',b'\x0e'),('app',b'\x11')):
    data=w.request(cmd);(out/(name+'_after.bin')).write_bytes(data)
    if data!=before[name]:raise ValueError(name+' settings changed')
   require_identity(w.request(b'\0'),UUID);m['complete']=True
 except BaseException as e:m['error']=repr(e);raise
 finally:
  m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();m['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print('RECORDING COMPLETE: releasepedal, stop wheels and return forward.',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
