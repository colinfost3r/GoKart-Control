#!/usr/bin/env python3
"""Explicit kart3-only RAM trial: l_current_min 0 -> -5A, or guarded restore -5 -> 0.
No flash store, full-config setter, motor command, lifecycle, calibration or reset.
"""
import argparse,binascii,datetime,hashlib,json,os,re,struct,time
from pathlib import Path
from unittest.mock import patch
from capture import PacketParser
from decode import decode_configuration,decode_telemetry,DEFAULT_SCHEMA
from read_lisp import SerialConnection,require_identity
from rx_filter_control import Wire as BaseWire,UUID,require_app,parse_status,at_rest
from rx_probe import printed_text
from tune import motor_spans
ROOT=Path('/Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5')
BASE=ROOT/'hardware/vesc/kart3/2026-11-11/pedal-response-03/triggered-02/motor_after.bin'
BASE_SHA='166f7e6fae318c1dd04d9adf9ebc36358ade8c92b8148574c48118c4b4dd9bee'
SOURCE='f7c2b34e1cff2234cae98be3abf0cd50e249558f'
def expression(restore=False):
    if type(restore) is not bool: raise ValueError('Fixed apply or restore only')
    old,new=('-5.0','0.0') if restore else ('0.0','-5.0')
    return ("(print (list 'gk-brake-limit-result (if (and (= (conf-get 'l-current-min) "+old+") "
      "(eq (gk-rx-filter-safe) t) (eq (gk-rx-filter-config-ok) t) gk-rx-filter-run gk-rx-filter-active "
      "(= gk-rx-filter-applied 0) (= (gpio-read 'pin-rx) 1) (<= (get-vin) 82.0)) "
      "(conf-set 'l-current-min "+new+") nil) (conf-get 'l-current-min)))").encode()
def config_frame(restore=False):
    data=b'\x8a'+expression(restore)+b'\0'
    if len(data)>512: raise ValueError('Fixed REPL over ceiling')
    header=bytes((2,len(data))) if len(data)<256 else b'\x03'+len(data).to_bytes(2,'big')
    return header+data+binascii.crc_hqx(data,0).to_bytes(2,'big')+b'\x03'
def expected_motor(temporary=False):
    original=BASE.read_bytes()
    if hashlib.sha256(original).hexdigest()!=BASE_SHA: raise ValueError('Baseline changed')
    before=decode_configuration(original,DEFAULT_SCHEMA/'parameters_mcconf.xml',14)['values']
    if before['l_current_min']!=0 or before['l_current_min_scale']!=1 or before['l_in_current_min']!=-12: raise ValueError('Unexpected baseline')
    if not temporary: return original
    a,b=motor_spans(original)['l_current_min']; changed=bytearray(original)
    if b-a!=4: raise ValueError('Not four-byte normal auto-float')
    changed[a:b]=struct.pack('>f',-5.0)
    after=decode_configuration(changed,DEFAULT_SCHEMA/'parameters_mcconf.xml',14)['values']
    if {k for k in before if before[k]!=after[k]}!={'l_current_min'} or after['l_current_min']!=-5: raise ValueError('Invalid one-field expected readback')
    return bytes(changed)
def guard_status(s):
    if not(at_rest(s) and s['run'] and s['active'] and s['pid']>=0 and s['applied']==0 and s['rx']==1): raise ValueError('Pedal/reverse/filter/rest guard failed')
def guard_values(t):
    if (abs(t['erpm'])>50 or abs(t['iq_a'])>1 or abs(t['battery_current_a'])>1 or t['fault_code'] or t['timeout_active'] or t['kill_switch_active'] or not 70<t['input_voltage_v']<=82): raise ValueError('Not stationary, fault-free or within trial voltage range')
class Wire(BaseWire):
    def __init__(self,fd,out,restore): super().__init__(fd,out); self.restore=restore
    def send(self,action):
        if action not in ('identity','telemetry','motor','app','status','contexts','brake_limit'): raise ValueError('No other command allowed')
        if action!='brake_limit': return super().send(action)
        if time.monotonic()>=self.deadline or self.queue or self.parser.buffer: raise ValueError('Expired or pending data; no mutation')
        data=config_frame(self.restore); self.record(kind='tx_attempt',action=action,frame_hex=data.hex())
        with (self.output/'tx-attempts.bin').open('ab') as f:f.write(data)
        if time.monotonic()>=self.deadline: raise TimeoutError('Expired before send')
        n=os.write(self.fd,data); self.record(kind='tx_return',count=n)
        if n!=len(data): raise IOError('Partial mutation send: outcome uncertain, no retry/cleanup')
def parse_result(packets,target):
    text=printed_text(packets)
    n=r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
    m=re.findall(r"\(gk-brake-limit-result (t|nil) (\{"+n+r"\}|"+n+r")\)",text)
    if len(m)!=1 or m[0][0]!='t' or float(m[0][1].strip('{}'))!=target: raise ValueError('No unique successful mutation result; do not resend')
    return text

def run(out,restore=False,setup_confirmed=False):
    if not setup_confirmed: raise ValueError('Supervised readiness required')
    before_expected=expected_motor(restore); after_expected=expected_motor(not restore); target=0.0 if restore else -5.0
    out.mkdir(parents=True,exist_ok=False)
    m={'complete':False,'action':'restore_zero' if restore else 'apply_minus5','target_l_current_min':target,
       'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_sha256':BASE_SHA,
       'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'firmware_source_commit':SOURCE,
       'mutation_attempted':False,'persistent_store_requested':False,'motor_or_lifecycle_or_reset_command':False,
       'scope':'RAM-only l_current_min; no conf-store. Explicit restore after rest. No retries or automatic cleanup.'}
    def save(): (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    def read(w,action,stage):
        raw=w.query(action); (out/(action+'_'+stage+'.bin')).write_bytes(raw); return raw
    save()
    try:
        with SerialConnection('/dev/cu.usbmodem3041') as c:
            w=Wire(c.fd,out,restore); ident=require_identity(read(w,'identity','before'),UUID)
            if ident['hardware']!='75_300_R2' or ident['firmware_name']!='no_hw_limits' or ident['test_version']!=0: raise ValueError('Wrong target firmware')
            m['identity_before']=ident; app_before=read(w,'app','before'); require_app(app_before)
            motor_before=read(w,'motor','before')
            if motor_before!=before_expected: raise ValueError('Full motor payload differs from exact trial predecessor; no write')
            m['status_before']=parse_status(w.expression('status')); guard_status(m['status_before'])
            m['stationary_samples']=[]
            for i in range(4):
                t=decode_telemetry(read(w,'telemetry',f'pre_{i}')); guard_values(t); m['stationary_samples'].append(t); time.sleep(.1)
            if read(w,'motor','preaction')!=motor_before or read(w,'app','preaction')!=app_before: raise ValueError('Configuration changed before mutation')
            m['status_fresh']=parse_status(w.expression('status',seconds=.2)); guard_status(m['status_fresh'])
            guard_values(decode_telemetry(read(w,'telemetry','fresh')))
            # Device-side guard rechecks pedal, motion, direction, fault, voltage and old limit at execution.
            m['mutation_attempted']=True; save()
            packets=w.expression('brake_limit',seconds=.5); m['result_text']=printed_text(packets); save()
            parse_result(packets,target)
            motor_after=read(w,'motor','after'); app_after=read(w,'app','after')
            m['motor_exact_expected']=motor_after==after_expected; m['app_identical']=app_after==app_before
            if not m['motor_exact_expected'] or not m['app_identical']: raise ValueError('Readback differs beyond approved single field; no cleanup')
            m['status_after']=parse_status(w.expression('status')); guard_status(m['status_after'])
            m['identity_after']=require_identity(read(w,'identity','after'),UUID)
            m['all_other_375_fields_preserved']=True; m['complete']=True
    except BaseException as e:
        m['error']=repr(e)
        if m['mutation_attempted']:m['failure_instruction']='May have changed. Read-only inspection first; no automatic resend, restore or reset.'
        raise
    finally:m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print(json.dumps(m,indent=2),flush=True)

def selftest():
    import tempfile
    a,b=expected_motor(False),expected_motor(True); assert a!=b
    for restore in (False,True):
        data=PacketParser().feed(config_frame(restore)); assert data==[b'\x8a'+expression(restore)+b'\0']
        assert expression(restore).count(b'conf-set')==1
        for bad in (b'conf-store',b'set-current ',b'set-rpm',b'reset',b'conf-set-pid'): assert bad not in expression(restore)
    safe={'adc':.09,'erpm':0,'fault':0,'run':True,'active':True,'pid':1507,'applied':0,'rx':1}; guard_status(safe)
    for key,value in [('adc',.5),('erpm',51),('fault',1),('run',False),('active',False),('applied',1),('rx',0)]:
        try: guard_status(dict(safe,**{key:value}))
        except ValueError: pass
        else: raise AssertionError(key)
    parse_result([b'\x87(gk-brake-limit-result t {-5.000000})'],-5)
    for p in ([b'\x87(gk-brake-limit-result nil {0.000000})'],[],[b'\x87(gk-brake-limit-result t {-3.000000})']):
        try:parse_result(p,-5)
        except ValueError:pass
        else:raise AssertionError('bad mutation reply accepted')
    with tempfile.TemporaryDirectory() as d,patch.object(os,'write',return_value=1) as write:
        w=Wire(9999,Path(d),False)
        try:w.send('brake_limit')
        except IOError:pass
        else:raise AssertionError('partial write accepted')
        assert write.call_count==1
    for action in ('start','stop','rollback','set_current','reboot'):
        try:Wire.send(None,action)
        except ValueError:pass
        else:raise AssertionError('unapproved action')
    print('One-field expected bytes, guard refusals, exact frames/results and no-retry checks passed')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=('plan','apply','restore','selftest')); p.add_argument('--setup-confirmed',action='store_true'); p.add_argument('--out',type=Path); a=p.parse_args()
    if a.action=='plan': print(json.dumps({'apply_expression':expression(False).decode(),'restore_expression':expression(True).decode(),'volatile':True,'target':-5.0},indent=2))
    elif a.action=='selftest':selftest()
    elif not a.out:p.error('--out required')
    else:run(a.out,restore=a.action=='restore',setup_confirmed=a.setup_confirmed)
