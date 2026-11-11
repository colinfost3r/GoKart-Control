#!/usr/bin/env python3
"""One bounded read-only kart3 trace. No lifecycle, config or motor commands."""
import argparse, binascii, datetime, hashlib, json, os, select, struct, time
from pathlib import Path
from capture import PacketParser
from decode import decode_telemetry
from read_lisp import SerialConnection, require_identity
from rx_filter_control import UUID, require_app, EXPRESSIONS, parse_status
ALLOWED = frozenset((0, 4, 14, 17, 32))
STATUS = b'\x8a' + EXPRESSIONS['status'] + b'\0'
def frame(payload):
    if payload != STATUS and not (len(payload) == 1 and payload[0] in ALLOWED):
        raise ValueError('Only fixed read requests and unchanged status expression allowed')
    if len(payload) > 255: raise ValueError('Oversized request')
    return bytes((2,len(payload))) + payload + binascii.crc_hqx(payload,0).to_bytes(2,'big') + b'\x03'
def adc(payload):
    if len(payload)!=17 or payload[0]!=32: raise ValueError('Invalid ADC response')
    return dict(zip(('decoded1','voltage1','decoded2','voltage2'), (v/1e6 for v in struct.unpack('>iiii',payload[1:]))))
class Link:
    def __init__(self,fd,out):
        self.fd,self.out=fd,out; self.parser=PacketParser(); self.queue=[]; self.count=0
        self.deadline=time.monotonic()+60
    def log(self,kind,**kw):
        with (self.out/'wire.jsonl').open('a') as f: f.write(json.dumps(dict(kind=kind,monotonic=time.monotonic(),**kw))+'\n')
    def packet(self,deadline):
        while time.monotonic()<min(deadline,self.deadline):
            if self.queue: return self.queue.pop(0)
            ready,_,_=select.select([self.fd],[],[],max(0,min(.05,deadline-time.monotonic())))
            if not ready: continue
            raw=os.read(self.fd,4096)
            if not raw: raise IOError('USB closed')
            self.count+=len(raw)
            if self.count>512*1024: raise IOError('Read budget exceeded')
            self.log('rx',hex=raw.hex()); self.queue.extend(self.parser.feed(raw))
        return None
    def request(self,payload):
        if time.monotonic()>=self.deadline: raise TimeoutError('Session limit')
        if self.queue or self.parser.buffer: raise IOError('Pending or partial response; no send')
        data=frame(payload); self.log('tx_attempt',hex=data.hex())
        n=os.write(self.fd,data); self.log('tx_return',count=n)
        if n!=len(data): raise IOError('Partial send; no retry')
        deadline=time.monotonic()+2
        if payload==STATUS:
            packets=[]
            while time.monotonic()<deadline:
                p=self.packet(deadline)
                if p is None: break
                if p[0] not in (135,138): raise ValueError('Unexpected status response')
                packets.append(p)
                try: parsed=parse_status(packets)
                except ValueError: continue
                # Drain the trailing REPL result, without new requests.
                tail=time.monotonic()+.12
                while time.monotonic()<tail:
                    p=self.packet(tail)
                    if p is None: break
                    if p[0] not in (135,138): raise ValueError('Unexpected status tail')
                return parsed
            raise TimeoutError('No fixed status reply')
        while time.monotonic()<deadline:
            p=self.packet(deadline)
            if p is None: break
            if p[0]==payload[0]: return p
            if p[0] not in (135,138): raise ValueError('Unexpected response')
        raise TimeoutError('No read reply; no retry')
def selftest():
    for p in (b'\x05',b'\x06',b'\x0d',b'\x10',b'\x1e',b'\x85',b'\x8a(reset)\0',b'\x20\x00'):
        try: frame(p)
        except ValueError: pass
        else: raise AssertionError('Unsafe payload accepted')
    for p in [bytes((x,)) for x in ALLOWED]+[STATUS]:
        assert PacketParser().feed(frame(p))==[p]
    assert adc(b'\x20'+struct.pack('>iiii',150000,987000,0,3300000))==dict(decoded1=.15,voltage1=.987,decoded2=0.,voltage2=3.3)
    for p in (b'', b'\x04'+b'\0'*16,b'\x20'+b'\0'*15):
        try: adc(p)
        except ValueError: pass
        else: raise AssertionError('Bad ADC frame accepted')
    print('Offline fixed-read/frame/ADC checks passed')
def run(out):
    out.mkdir(parents=True,exist_ok=False)
    m={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete':False,'commands':[0,4,14,17,32,138],'motor_or_config_or_lifecycle_writes':False,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'note':'GET_VALUES resets telemetry averaging accumulators; REPL status may pause/GC evaluator. No output or filter-state mutation.'}
    try:
        with SerialConnection('/dev/cu.usbmodem3041') as con:
            w=Link(con.fd,out)
            m['identity']=require_identity(w.request(b'\0'),UUID)
            if m['identity']['firmware']!='6.02' or m['identity']['test_version']!=0: raise ValueError('Firmware mismatch')
            before={}
            for name,cmd in (('app',17),('motor',14)):
                before[name]=w.request(bytes((cmd,))); (out/(name+'_before.bin')).write_bytes(before[name])
            require_app(before['app'])
            m['status_before']=w.request(STATUS)
            print('READ-ONLY RECORDING STARTED '+json.dumps(m['status_before']),flush=True)
            start=time.monotonic(); lastprint=-1; nextstatus=0; rows=0
            with (out/'samples.jsonl').open('x') as f:
                while time.monotonic()-start<40:
                    cycle=time.monotonic(); a=w.request(b'\x20'); at=time.monotonic(); v=w.request(b'\x04'); vt=time.monotonic()
                    r={'seconds':at-start,'adc_at_monotonic':at,'values_at_monotonic':vt,'adc':adc(a),'telemetry':decode_telemetry(v),'adc_hex':a.hex(),'values_hex':v.hex()}
                    if cycle-start>=nextstatus:
                        r['filter']=w.request(STATUS); nextstatus=cycle-start+1
                    f.write(json.dumps(r)+'\n'); f.flush(); rows+=1
                    if int(cycle-start)!=lastprint:
                        lastprint=int(cycle-start); t=r['telemetry']; print(json.dumps({'seconds':round(r['seconds'],1),'pedal':r['adc'],'erpm':t['erpm'],'iq_a':t['iq_a'],'duty':t['duty'],'fault':t['fault_code'],'timeout':t['timeout_active'],'kill':t['kill_switch_active'],'filter':r.get('filter')}),flush=True)
                    time.sleep(max(0,.1-(time.monotonic()-cycle)))
            m['rows']=rows; m['status_after']=w.request(STATUS)
            for name,cmd in (('app',17),('motor',14)):
                after=w.request(bytes((cmd,))); (out/(name+'_after.bin')).write_bytes(after)
                m[name+'_unchanged']=after==before[name]
            m['identity_after']=require_identity(w.request(b'\0'),UUID)
            m['complete']=True
    except BaseException as e:
        m['error']=repr(e); raise
    finally:
        m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat(); (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps(m,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path); p.add_argument('--selftest',action='store_true'); a=p.parse_args()
    if a.selftest: selftest()
    elif a.out: run(a.out)
    else: p.error('Choose --selftest or --out')
