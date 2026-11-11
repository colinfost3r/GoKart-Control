#!/usr/bin/env python3
"""One guarded persistent kart3 l_current_min 0 -> -5 A save. No app/motor/reset commands."""
import argparse,datetime,hashlib,json,os,time
from pathlib import Path
from unittest.mock import patch
import temporary_brake5 as trial
from capture import PacketParser
from decode import decode_telemetry,decode_payloads
from read_lisp import SerialConnection,require_identity
from rx_filter_control import Wire as BaseWire,parse_status,require_app,UUID
from apply_tune import motor_frame,capture_four,write_json
from compare import compare_decoded
PIN='7c5a83712e53d9fbe7e31631f87897bd6e3ab65ce1257781a7a0e3befd1f25a7'
IDENTITY={'uuid':UUID,'firmware':'6.02','hardware':'75_300_R2'}

def prepared():
    if hashlib.sha256(Path(trial.__file__).read_bytes()).hexdigest()!=PIN: raise ValueError('Reviewed trial helper changed')
    before,after=trial.expected_motor(False),trial.expected_motor(True)
    data=motor_frame(after); parsed=PacketParser().feed(data)
    if len(parsed)!=1 or parsed[0]!=b'\x0d'+after[1:]: raise ValueError('Wrong fixed persistent frame')
    return before,after,data
class Wire(BaseWire):
    def __init__(self,fd,out):super().__init__(fd,out);self.mutations=0
    def send(self,action):
        if action not in ('identity','motor','app','telemetry','status','contexts'): raise ValueError('Only pre/post inspection allowed here')
        return super().send(action)
    def save_motor_once(self,latest):
        if self.mutations or self.queue or self.parser.buffer or time.monotonic()>=min(latest,self.deadline): raise ValueError('Unsafe/stale/duplicate persistent write')
        raw=prepared()[2]
        self.record(kind='tx_attempt',action='SET_MCCONF_ONE_FIELD',frame_hex=raw.hex())
        with (self.output/'tx-attempts.bin').open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if time.monotonic()>=min(latest,self.deadline): raise TimeoutError('Fresh guard expired before mutation')
        self.mutations=1; n=os.write(self.fd,raw); self.record(kind='tx_return',count=n)
        if n!=len(raw): raise IOError('Partial persistent send; outcome uncertain, no retry or further commands')
    def ack(self):
        until=time.monotonic()+5
        while time.monotonic()<until:
            p=self.packet(until)
            if p is None:break
            if p==b'\x0d':return
            if p[0] not in (21,135,138):raise ValueError('Unexpected or malformed ACK')
        raise TimeoutError('No exact SET_MCCONF ACK; no retry/rollback')
class Reads:
    port='/dev/cu.usbmodem3041'
    def __init__(self,w):self.w=w
    def query(self,command):
        names={0:'identity',4:'telemetry',14:'motor',17:'app'}
        if command not in names:raise ValueError('Only fixed four-command capture')
        return self.w.query(names[command])
def run(out,setup=False):
    if not setup:raise ValueError('Supervised stationary setup required')
    old,new,frame=prepared();out.mkdir(parents=True,exist_ok=False)
    m={'complete':False,'operation':'persistent_motor_limit_zero_to_minus5','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'trial_helper_sha256':PIN,
       'firmware_source_commit':trial.SOURCE,'write_command':13,'mutation_attempted':False,'ack_verified':False,
       'runtime_readback_verified':False,'powercycle_persistence_verified':False,
       'persistence_caveat':'Command13 stores full motor config then applies it; its ACK does not report flash-store success. Verify by normal cold boot.',
       'motor_output_app_calibration_reset_commands':False,'setting_changes':{'l_current_min':{'before':0,'after':-5}},
       'no_retry_or_automatic_rollback':True}
    def save():write_json(out/'manifest.json',m)
    save()
    try:
        with SerialConnection('/dev/cu.usbmodem3041') as c:
            w=Wire(c.fd,out); reads=Reads(w)
            before=capture_four(reads,out/'before',IDENTITY)
            ident=before['decoded']['identity']
            if ident['firmware_name']!='no_hw_limits' or ident['test_version']!=0:raise ValueError('Unexpected exact firmware')
            if before['payloads']['motor_configuration']!=old:raise ValueError('Full motor baseline differs; stopped')
            app=before['payloads']['app_configuration'];require_app(app)
            m['status_before']=parse_status(w.expression('status'));trial.guard_status(m['status_before'])
            m['stationary_samples']=[]
            for i in range(4):
                t=decode_telemetry(w.query('telemetry'));trial.guard_values(t);m['stationary_samples'].append(t);time.sleep(.1)
            if w.query('motor')!=old or w.query('app')!=app:raise ValueError('Configuration changed')
            final_gate_started=time.monotonic()
            m['status_fresh']=parse_status(w.expression('status',seconds=.2));trial.guard_status(m['status_fresh'])
            t=decode_telemetry(w.query('telemetry'));trial.guard_values(t)
            m['telemetry_fresh']=t;m['mutation_attempted']=True
            (out/'set_mcconf_frame.bin').write_bytes(frame);m['write_sha256']=hashlib.sha256(frame).hexdigest();save()
            w.save_motor_once(min(final_gate_started+.75,before['started']+10))
            w.ack();m['ack_verified']=True;save()
            after=capture_four(reads,out/'after',IDENTITY)
            if after['payloads']['motor_configuration']!=new or after['payloads']['app_configuration']!=app or after['payloads']['firmware']!=before['payloads']['firmware']: raise ValueError('Readback differs beyond approved field')
            audit=compare_decoded(before['decoded'],after['decoded']);write_json(out/'field-audit.json',audit)
            m['runtime_readback_verified']=True;m['other_375_fields_preserved']=True
            m['status_after']=parse_status(w.expression('status'));trial.guard_status(m['status_after'])
            m['complete']=True
    except BaseException as e:
        m['error']=repr(e)
        if m['mutation_attempted']:m['failure_instruction']='May be stored/applied. Inspect read-only; do not resend, rollback or reset automatically.'
        raise
    finally:m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print(json.dumps(m,indent=2))
def selftest():
    import tempfile
    old,new,raw=prepared();assert old!=new
    assert PacketParser().feed(raw)==[b'\x0d'+new[1:]]
    for n in ('start','stop','rollback','SET_APPCONF','brake_limit'):
        try:Wire.send(None,n)
        except ValueError:pass
        else:raise AssertionError(n)
    with tempfile.TemporaryDirectory() as d,patch.object(os,'write',return_value=1) as write:
        w=Wire(9999,Path(d))
        try:w.save_motor_once(time.monotonic()+1)
        except IOError:pass
        else:raise AssertionError('partialwriteaccepted')
        try:w.save_motor_once(time.monotonic()+1)
        except ValueError:pass
        else:raise AssertionError('duplicateallowed')
        assert write.call_count==1
    with tempfile.TemporaryDirectory() as d,patch.object(os,'write') as write:
        w=Wire(9999,Path(d))
        try:w.save_motor_once(0)
        except ValueError:pass
        else:raise AssertionError('staleallowed')
        write.assert_not_called()
    print('Fixed one-field frame, command refusals, freshness, one-send and partial-send checks passed')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('plan','selftest','apply'));p.add_argument('--setup-confirmed',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args()
    if a.action=='selftest':selftest()
    elif a.action=='plan':print(json.dumps({'command':13,'persistent':True,'change':'l_current_min 0 to -5A only','frame_sha256':hashlib.sha256(prepared()[2]).hexdigest(),'powercycle_required_for_persistence_verification':True},indent=2))
    elif a.out:run(a.out,a.setup_confirmed)
    else:p.error('--out required')
