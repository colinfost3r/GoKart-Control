#!/usr/bin/env python3
"""Fixed read-only kart3 mode commissioning monitor. Operator selects modes on Core2."""
import argparse,datetime,json,os,time,hashlib
from pathlib import Path
from capture import query_frame,receive
from read_lisp import SerialConnection,require_identity
from decode import decode_configuration,decode_telemetry,DEFAULT_SCHEMA
UUID='37004e000951343037353739'
FIELDS=('l_current_min','l_current_min_scale','l_current_max','l_current_max_scale','l_min_erpm','l_max_erpm','l_in_current_min')
ALLOWED_CHANGES={'l_current_max_scale','l_min_erpm','l_max_erpm'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 m={'complete':False,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host_commands':[0,4,14,17],'operator_modes_only':True,'rows':0,'observed_limits':[]}
 def query(c,cmd):
  frame=query_frame(cmd)
  if os.write(c.fd,frame)!=len(frame):raise IOError('Partial query; stop without retry')
  result=receive(c.fd,cmd)
  with (a.out/'responses.jsonl').open('a') as f:f.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'payload_hex':result.hex()})+'\n')
  return result
 try:
  with SerialConnection('/dev/cu.usbmodem3041') as c,(a.out/'samples.jsonl').open('w') as f:
   m['identity']=require_identity(query(c,0),UUID)
   motor=query(c,14);app=query(c,17);(a.out/'motor_before.bin').write_bytes(motor);(a.out/'app_before.bin').write_bytes(app)
   reference=decode_configuration(motor,DEFAULT_SCHEMA/'parameters_mcconf.xml',14)['values']
   if reference['l_current_min']!=-5 or reference['l_current_min_scale']!=1:raise ValueError('Minus5/minscale baseline missing')
   start=time.monotonic();last=None
   while time.monotonic()-start<90:
    motor=query(c,14);values=decode_configuration(motor,DEFAULT_SCHEMA/'parameters_mcconf.xml',14)['values'];t=decode_telemetry(query(c,4))
    if any(values[k]!=reference[k] for k in reference if k not in ALLOWED_CHANGES):raise ValueError('Unexpected non-mode setting change')
    if values['l_current_min']!=-5 or values['l_current_min_scale']!=1 or t['fault_code'] or t['timeout_active'] or t['kill_switch_active']:raise ValueError('Brake/fault guard failed')
    row={'seconds':time.monotonic()-start,'limits':{k:values[k] for k in FIELDS},'telemetry':t};f.write(json.dumps(row)+'\n');f.flush();m['rows']+=1
    state=(values['l_current_max_scale'],values['l_min_erpm'],values['l_max_erpm'])
    if state!=last:m['observed_limits'].append(row);print(json.dumps({'seconds':row['seconds'],'limits':row['limits'],'erpm':t['erpm']}),flush=True);last=state
    if abs(t['erpm'])>50:raise ValueError('Motion during pedal-released mode test; monitoring stopped')
    if query(c,17)!=app:raise ValueError('App setting changed')
    time.sleep(.5)
   motor=query(c,14);afterapp=query(c,17);require_identity(query(c,0),UUID)
   (a.out/'motor_after.bin').write_bytes(motor);(a.out/'app_after.bin').write_bytes(afterapp)
   if afterapp!=app:raise ValueError('App changed')
   m['complete']=True
 except BaseException as e:m['error']=repr(e);raise
 finally:m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();m['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print('Mode monitoring complete; no host settings or motor commands sent.',flush=True)
if __name__=='__main__':main()
