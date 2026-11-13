#!/usr/bin/env python3
"""Bounded read-only pedal trace with fixed internal FOC snapshots at missed-start onset."""
import argparse, datetime, hashlib, json, os, time
from pathlib import Path
import pedal_trace_180s as base
import extra_diagnostics as extra
from decode import decode_telemetry
from read_lisp import SerialConnection, require_identity
from rx_filter_control import require_app, at_rest
DEPENDENCIES = {'pedal_trace_180s.py':'51f0bfd945fdd51b7470d2b8e820d767a4f919533fc4eb5241ce7d83de41aa65',
                'extra_diagnostics.py':'373a33d72cd03afd4320286232887cb7fc1eb4f6501d938846f4147a9b7b44f0'}

def check_dependencies():
    for name,digest in DEPENDENCIES.items():
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Reviewed dependency changed: '+name)

def suspect(row):
    return row['adc']['decoded1']>.20 and abs(row['telemetry']['erpm'])<=50 and abs(row['telemetry']['iq_a'])<8.0

class Detector:
    def __init__(self): self.since=None; self.last=None
    def update(self,row):
        t=row['seconds']
        if self.last is not None and (t<self.last or t-self.last>.35): self.since=None
        self.last=t
        if not suspect(row): self.since=None; return False
        if self.since is None: self.since=t
        return t-self.since>=.20

class Link(base.Link):
    def diagnostic(self,action):
        if action not in ('foc_state','events','faults','output-disabled'):
            raise ValueError('Only four fixed print diagnostics')
        if time.monotonic()>=self.deadline or self.queue or self.parser.buffer:
            raise TimeoutError('Expired or undrained serial data')
        raw=extra.frame(action)
        self.log('tx_attempt',hex=raw.hex(),diagnostic=action)
        if time.monotonic()>=self.deadline: raise TimeoutError('Expired before send')
        n=os.write(self.fd,raw); self.log('tx_return',count=n)
        if n!=len(raw): raise IOError('Partial send; no retry')
        begun=time.monotonic(); deadline=min(self.deadline,begun+2.5); packets=[]
        while time.monotonic()<deadline:
            p=self.packet(deadline)
            if p is None: break
            if p[0] not in (21,135,138): raise ValueError('Unexpected diagnostic response')
            packets.append(p)
            summary=extra.response_summary(action,packets)
            if summary['expected_output_seen']:
                # Expected last field/result then 40ms with no additional packet.
                # Preserve all packets; this is a print snapshot, not atomic state.
                while True:
                    quiet_start=time.monotonic()
                    if quiet_start+.04>deadline: raise TimeoutError('Insufficient time for quiet tail')
                    q=self.packet(quiet_start+.04)
                    if q is None:
                        quiet_elapsed=time.monotonic()-quiet_start
                        if quiet_elapsed<.04: raise TimeoutError('Quiet tail interrupted')
                        break
                    if q[0] not in (21,135,138): raise ValueError('Unexpected diagnostic tail')
                    packets.append(q)
                    if time.monotonic()>=deadline: raise TimeoutError('No quiet tail')
                if self.parser.buffer: raise ValueError('Partial diagnostic packet')
                return dict(extra.response_summary(action,packets),started_monotonic=begun,
                            finished_monotonic=time.monotonic(),quiet_tail_seconds=quiet_elapsed)
        raise TimeoutError('Incomplete fixed diagnostic; no retry')

def sample(w,start):
    a=w.request(b'\x20'); at=time.monotonic(); v=w.request(b'\x04'); vt=time.monotonic()
    return {'seconds':at-start,'adc_at_monotonic':at,'values_at_monotonic':vt,
            'adc':base.adc(a),'telemetry':decode_telemetry(v),'adc_hex':a.hex(),'values_hex':v.hex()}

def run(out):
    check_dependencies(); out.mkdir(parents=True,exist_ok=False)
    m={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete':False,
       'motor_or_settings_or_lifecycle_commands':False,'fixed_diagnostics':list(extra.ACTIONS),
       'trigger':'decodedADC1>.20, absERPM<=50, absIq<8 A for >=.20s; samples gaps>.35s reset',
       'snapshot_limit':3,'maximum_trace_seconds':180,'post_first_trigger_seconds':10,
       'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'dependency_sha256':DEPENDENCIES,'snapshots_are_nonatomic':True,'snapshots':[]}
    def save(): (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    save()
    try:
        with SerialConnection('/dev/cu.usbmodem3041') as con:
            w=Link(con.fd,out)
            ident=require_identity(w.request(b'\0'),base.UUID)
            if ident['test_version']!=0 or ident['hardware']!='75_300_R2' or ident['firmware_name']!='no_hw_limits': raise ValueError('Wrong target firmware')
            m['identity']=ident; before={}
            for name,cmd in (('app',17),('motor',14)):
                before[name]=w.request(bytes((cmd,))); (out/(name+'_before.bin')).write_bytes(before[name])
            require_app(before['app']); m['status_before']=w.request(base.STATUS)
            state=m['status_before']
            if not(at_rest(state) and state['run'] and state['active'] and state['applied']==0 and state['rx']==1):
                raise ValueError('Start requires active filter, forward and rest; no test started')
            save(); print('READ-ONLY RECORDING STARTED '+json.dumps(state),flush=True)
            start=time.monotonic(); finish=start+180; detector=Detector(); nextstatus=0.; nexttrigger=0.; lastprint=-1; rows=0
            with (out/'samples.jsonl').open('x') as f:
                def record(r):
                    nonlocal rows
                    f.write(json.dumps(r)+'\n'); f.flush(); rows+=1
                while time.monotonic()<finish:
                    cycle=time.monotonic(); r=sample(w,start); record(r)
                    trigger=detector.update(r)
                    if trigger and r['seconds']>=nexttrigger and len(m['snapshots'])<3:
                        snap={'trigger_sample':r,'foc_state':w.diagnostic('foc_state')}
                        snap['after_foc']=sample(w,start); record(snap['after_foc'])
                        # Persist the time-critical snapshot before any subsequent reads.
                        m['snapshots'].append(snap); save()
                        print('INTERNAL TARGET CAPTURED '+json.dumps({'seconds':r['seconds'],'before_adc':r['adc'],
                              'before_values':r['telemetry'],'foc':snap['foc_state']['terminal_lines'],
                              'after_adc':snap['after_foc']['adc'],'after_erpm':snap['after_foc']['telemetry']['erpm']}),flush=True)
                        snap['events']=w.diagnostic('events'); snap['after_events']=sample(w,start); record(snap['after_events'])
                        snap['filter']=w.request(base.STATUS); snap['output_disabled']=w.diagnostic('output-disabled'); save()
                        finish=min(finish,time.monotonic()+10); nexttrigger=r['seconds']+2
                    elif cycle-start>=nextstatus:
                        status={'seconds':time.monotonic()-start,'filter':w.request(base.STATUS)}
                        with (out/'filter-status.jsonl').open('a') as sf: sf.write(json.dumps(status)+'\n')
                        nextstatus=cycle-start+1
                    if int(cycle-start)!=lastprint:
                        lastprint=int(cycle-start); t=r['telemetry']
                        print(json.dumps({'seconds':round(r['seconds'],1),'adc':r['adc']['decoded1'],
                              'voltage':r['adc']['voltage1'],'erpm':t['erpm'],'iq':t['iq_a'],'fault':t['fault_code']}),flush=True)
                    time.sleep(max(0,.1-(time.monotonic()-cycle)))
            m['rows']=rows; m['fault_history']=w.diagnostic('faults'); m['status_after']=w.request(base.STATUS)
            for name,cmd in (('app',17),('motor',14)):
                raw=w.request(bytes((cmd,))); (out/(name+'_after.bin')).write_bytes(raw); m[name+'_unchanged']=raw==before[name]
            m['identity_after']=require_identity(w.request(b'\0'),base.UUID); m['complete']=True
    except BaseException as e: m['error']=repr(e); raise
    finally:
        m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat(); save()
    print('RECORDING FINISHED '+json.dumps({'complete':m['complete'],'snapshots':len(m['snapshots']),'status_after':m['status_after']}),flush=True)

def selftest():
    check_dependencies(); base.selftest()
    def row(t,a=.5,rpm=0,iq=.05): return {'seconds':t,'adc':{'decoded1':a},'telemetry':{'erpm':rpm,'iq_a':iq}}
    d=Detector(); assert not d.update(row(0)); assert not d.update(row(.1)); assert d.update(row(.21))
    assert not d.update(row(.3,a=.1)); assert not d.update(row(.4)); assert not d.update(row(.8)); assert d.update(row(1.01))
    assert not d.update(row(1.1,iq=9)); assert not d.update(row(1.2,rpm=51))
    assert not suspect(row(0,a=.2)); assert not suspect(row(0,iq=-9)); assert not suspect(row(0,rpm=-51))
    for action in ('set_current','reboot','foc_dc_cal','start','events;reboot'):
        try: Link.diagnostic(None,action)
        except ValueError: pass
        else: raise AssertionError('Unsafe action accepted')
    foc=[b'\x15FOC State:',b'\x15Mod q flt: -0.01',b'\x15iq_target: 0.05',b'\x15off_delay: 0.00']
    assert extra.response_summary('foc_state',foc)['expected_output_seen']
    assert not extra.response_summary('foc_state',foc[:-1])['expected_output_seen']
    print('Trigger boundary/gap/allowlist/completion checks passed')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--selftest',action='store_true'); p.add_argument('--out',type=Path); a=p.parse_args()
    if a.selftest: selftest()
    elif a.out: run(a.out)
    else: p.error('Choose --selftest or --out')
