#!/usr/bin/env python3
"""Fixed, volatile definitions loader for kart 3. No filter activation or STREAM.

The only writes are reviewed, hash-pinned REPL expressions assembling source in
RAM and evaluating definitions. Partial/uncertain delivery never retries. Exact
controller identity, complete context review and manual namespace review required.
"""
import argparse, binascii, datetime, hashlib, json, os, select, sys, time
from pathlib import Path
TOOLS=Path('/Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/tools/vesc')
sys.path.insert(0,str(TOOLS))
from capture import PacketParser
from read_lisp import SerialConnection, require_identity
from rx_probe import Capture, context_summary, printed_text
UUID='37004e000951343037353739'
PLAN=Path(__file__).with_name('plan.json')
PLAN_SHA256='c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805'
SOURCE_SHA256='d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
MAX_BYTES=256*1024
SESSION_SECONDS=240.0

def frame(payload):
    if not 1<=len(payload)<=512:raise ValueError('Payload exceeds reviewed limit')
    if payload[0] not in (0,134,138):raise ValueError('Unsupported command')
    head=bytes((2,len(payload))) if len(payload)<256 else b'\x03'+len(payload).to_bytes(2,'big')
    return head+payload+binascii.crc_hqx(payload,0).to_bytes(2,'big')+b'\x03'

def reviewed_plan():
    raw=PLAN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PLAN_SHA256:raise ValueError('Unreviewed plan; no hardware opened')
    p=json.loads(raw)
    if p['source_sha256']!=SOURCE_SHA256:raise ValueError('Source pin mismatch')
    if not p['steps']:raise ValueError('Empty plan')
    for step in p['steps']:
        e=step['expression'].encode('ascii')
        if b'\0' in e:raise ValueError('NUL in REPL expression')
        frame(b'\x8a'+e+b'\0')
        if not step['expected_line']:raise ValueError('Missing unique completion evidence')
    return p

class Wire:
    def __init__(self,fd,out):
        self.fd,self.out=fd,Path(out);self.parser=PacketParser();self.pending=[]
        self.start=time.monotonic();self.deadline=self.start+SESSION_SECONDS;self.last_rx=self.start;self.nbytes=0
    def log(self,**r):
        r['elapsed_s']=time.monotonic()-self.start
        with (self.out/'wire.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    def send(self,payload,label):
        if time.monotonic()>=self.deadline:raise TimeoutError('Session deadline')
        if self.pending or self.parser.buffer:raise RuntimeError('Pending/partial reply before next request')
        data=frame(payload);self.log(direction='tx_attempt',label=label,frame_hex=data.hex())
        with (self.out/'tx-attempts.bin').open('ab') as f:f.write(data)
        count=os.write(self.fd,data)
        self.log(direction='tx_return',label=label,written_bytes=count)
        if count!=len(data):raise IOError('Partial/uncertain write; no retry')
    def packet(self,deadline):
        deadline=min(deadline,self.deadline)
        while time.monotonic()<deadline:
            if self.pending:return self.pending.pop(0)
            ready,_,_=select.select([self.fd],[],[],min(.05,max(0,deadline-time.monotonic())))
            if not ready:continue
            try:raw=os.read(self.fd,4096)
            except BlockingIOError:continue
            if not raw:raise IOError('Serial EOF')
            self.last_rx=time.monotonic();self.nbytes+=len(raw)
            with (self.out/'rx-wire.bin').open('ab') as f:f.write(raw)
            if self.nbytes>MAX_BYTES:raise IOError('Receive byte bound')
            packets=self.parser.feed(raw)
            for p in packets:
                r={'direction':'rx','command':p[0],'payload_hex':p.hex(),'crc_verified':True}
                if p[0] in (135,138):r['text']=p[1:].rstrip(b'\0').decode(errors='replace')
                self.log(**r)
            self.pending.extend(packets)
        return None
    def query(self,command):
        if command not in (0,134):raise ValueError('Only fixed read requests')
        self.send(bytes((command,)),f'read-{command}')
        end=time.monotonic()+3
        while time.monotonic()<end:
            p=self.packet(end)
            if p is None:break
            if p[0]==command:return p
            raise RuntimeError('Unexpected response during identity/stats query')
        raise TimeoutError('Read timeout; no retry')
    def observe(self,expression,seconds):
        if expression not in (':ctxs',':info'):raise ValueError('Only fixed context/memory observations')
        self.send(b'\x8a'+expression.encode()+b'\0',expression)
        end=time.monotonic()+seconds;result=Capture()
        while time.monotonic()<end:
            p=self.packet(end)
            if p is None:break
            if p[0] not in (135,138):raise RuntimeError('Unexpected response during observation')
            result.append(p)
        result.quiet_tail_seconds=time.monotonic()-self.last_rx
        result.pending_bytes=len(self.parser.buffer)
        return result
    def step(self,step,index):
        self.send(b'\x8a'+step['expression'].encode('ascii')+b'\0',f'plan-{index}')
        end=time.monotonic()+5;lines=[];complete=False
        while time.monotonic()<end:
            p=self.packet(end)
            if p is None:break
            if p[0] not in (135,138):raise RuntimeError('Unexpected response during fixed REPL step')
            lines.extend(p[1:].rstrip(b'\0').decode(errors='strict').splitlines())
            stripped=[s.strip() for s in lines]
            if sum(s==step['expected_line'] for s in stripped)>1:raise RuntimeError('Duplicate step marker')
            if any(s.startswith('> ') and s!='> t' for s in stripped):raise RuntimeError('REPL expression returned failure/unknown value')
            if step['expected_line'] in stripped and '> t' in stripped:
                complete=True;break
        if not complete:raise RuntimeError('Missing exact marker or REPL completion; no retry')
        # Both the reviewed expression's marker and the firmware completion callback
        # were observed. No still-running parse is inferred from byte acceptance.
        if self.pending or self.parser.buffer:raise RuntimeError('Unconsumed/partial output after completion')
        return lines

def run(port,out,*,inspect=False,ownership_reviewed=False,no_previous_copy_reviewed=False,connection_factory=SerialConnection,wire_factory=Wire):
    if not inspect and not (ownership_reviewed and no_previous_copy_reviewed):raise ValueError('Manual ownership and no-previous-copy review required')
    plan=None if inspect else reviewed_plan()
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    m={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'inspect' if inspect else 'load-definitions-only','uuid_pin':UUID,'plan_sha256':None if inspect else PLAN_SHA256,'source_sha256':None if inspect else SOURCE_SHA256,'complete':False,'activation_sent':False,'stream_sent':False,'flash_written':False,'namespace_absence_machine_verified':False,'steps_completed':0}
    def save():(out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    try:
        save()
        if plan:(out/'plan.json').write_bytes(PLAN.read_bytes())
        with connection_factory(port) as c:
            w=wire_factory(c.fd,out)
            before=w.query(0);(out/'identity-before.bin').write_bytes(before);m['identity_before']=require_identity(before,UUID)
            contexts=w.observe(':ctxs',1.0);m['contexts_before']=context_summary(contexts)
            if m['contexts_before']['snapshot']!='no_contexts_reported':raise ValueError('Existing or uncertain evaluator ownership')
            info=w.observe(':info',.7);m['memory_before']=printed_text(info)
            if info.pending_bytes:raise ValueError('Incomplete memory response')
            if plan:
                m['manual_ownership_reviewed']=True;m['manual_no_previous_copy_reviewed']=True
                for index,step in enumerate(plan['steps']):
                    m['attempting_step']=index;save()
                    m.setdefault('step_results',[]).append({'index':index,'lines':w.step(step,index)})
                    m['steps_completed']=index+1;save()
                m['memory_after']=printed_text(w.observe(':info',.7))
                m['contexts_after']=context_summary(w.observe(':ctxs',1.0))
                if m['contexts_after']['snapshot']!='no_contexts_reported':raise RuntimeError('Definitions load left unexpected active contexts')
            after=w.query(0);(out/'identity-after.bin').write_bytes(after);m['identity_after']=require_identity(after,UUID)
            if m['identity_before']!=m['identity_after']:raise ValueError('Identity changed')
            m['complete']=True
    except BaseException as e:
        m['error']=f'{type(e).__name__}: {e}';m['after_failure']='Partial RAM definitions may exist. No automatic retry, reset or cleanup.';raise
    finally:
        m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    return m

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--port',required=True);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--inspect',action='store_true');ap.add_argument('--ownership-reviewed',action='store_true');ap.add_argument('--no-previous-copy-reviewed',action='store_true');a=ap.parse_args()
    m=run(a.port,a.out,inspect=a.inspect,ownership_reviewed=a.ownership_reviewed,no_previous_copy_reviewed=a.no_previous_copy_reviewed)
    print(json.dumps(m if a.inspect else {k:m[k] for k in ('complete','steps_completed','activation_sent')},indent=2))
if __name__=='__main__':main()
