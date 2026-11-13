import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('loader',ROOT/'tools/vesc/rx_filter_repl_load.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def identity(uuid=r.UUID):return bytes((0,6,2))+b'75_300_R2\0'+bytes.fromhex(uuid)+bytes(8)+b'no_hw_limits\0'
def cap(*lines):return r.Capture([b'\x87'+s.encode() for s in lines],quiet_tail_seconds=.4,pending_bytes=0)
class FakeConnection:
    fd=7
    def __enter__(self):return self
    def __exit__(self,*args):pass
class FakeWire:
    wrong_identity=False;busy=False;fail_step=None;made=[]
    def __init__(self,fd,out):self.queries=[];self.steps=[];self.__class__.made.append(self)
    def query(self,c):self.queries.append(c);return identity('17004e000951343037353739' if self.wrong_identity else r.UUID)
    def observe(self,e,seconds):
        if e==':info':return cap('Free cons cells: 1900','Memory free: 3000 Words')
        lines=['****** Running contexts ******','****** Blocked contexts ******','****** Sleeping contexts ******']
        if self.busy:lines.insert(1,'ContextID: 101')
        return cap(*lines)
    def step(self,s,i):
        self.steps.append(i)
        if self.fail_step==i:raise TimeoutError('uncertain')
        return [s['expected_line'],'> t']
class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);FakeWire.wrong_identity=False;FakeWire.busy=False;FakeWire.fail_step=None;FakeWire.made=[]
    def test_exact_plan_all_frames(self):
        p=r.reviewed_plan();self.assertEqual(len(p['steps']),24);self.assertEqual(p['source_length'],3732)
        for s in p['steps']:
            payload=b'\x8a'+s['expression'].encode()+b'\0';self.assertLessEqual(len(payload),397)
            self.assertEqual(r.PacketParser().feed(r.frame(payload)),[payload])
        for c in (4,5,6,13,16,131,132,133,139):
            with self.assertRaises(ValueError):r.frame(bytes((c,)))
    def test_plan_tamper_before_port(self):
        with patch.object(r,'PLAN_SHA256','0'*64),patch.object(r,'SerialConnection') as connection:
            with self.assertRaises(ValueError):r.run('none',self.root/'a',ownership_reviewed=True,no_previous_copy_reviewed=True)
            connection.assert_not_called()
    def test_attestations_required_before_output_or_port(self):
        for a,b in [(False,False),(True,False),(False,True)]:
            with self.assertRaises(ValueError):r.run('none',self.root/'a',ownership_reviewed=a,no_previous_copy_reviewed=b)
        self.assertFalse((self.root/'a').exists())
    def run_fake(self,name,**kw):return r.run('fake',self.root/name,ownership_reviewed=True,no_previous_copy_reviewed=True,connection_factory=lambda p:FakeConnection(),wire_factory=FakeWire,**kw)
    def test_complete_load_never_activates(self):
        m=self.run_fake('a');self.assertTrue(m['complete']);self.assertFalse(m['activation_sent']);self.assertFalse(m['stream_sent']);self.assertEqual(FakeWire.made[0].queries,[0,0]);self.assertEqual(FakeWire.made[0].steps,list(range(24)))
    def test_wrong_uuid_no_steps(self):
        FakeWire.wrong_identity=True
        with self.assertRaises(ValueError):self.run_fake('a')
        self.assertEqual(FakeWire.made[0].steps,[])
    def test_busy_context_refuses(self):
        FakeWire.busy=True
        with self.assertRaises(ValueError):self.run_fake('a')
        self.assertEqual(FakeWire.made[0].steps,[])
    def test_partial_sequence_no_retry_or_cleanup(self):
        FakeWire.fail_step=4
        with self.assertRaises(TimeoutError):self.run_fake('a')
        self.assertEqual(FakeWire.made[0].steps,list(range(5)))
        m=json.loads((self.root/'a/manifest.json').read_text());self.assertFalse(m['complete']);self.assertEqual(m['steps_completed'],4)
    def test_inspect_no_ram_plan_or_eval(self):
        m=self.run_fake('a',inspect=True);self.assertTrue(m['complete']);self.assertEqual(FakeWire.made[0].steps,[])
    def test_single_write_on_partial(self):
        out=self.root/'a';out.mkdir();w=r.Wire(9,out)
        with patch.object(r.os,'write',return_value=1) as write:
            with self.assertRaises(IOError):w.send(b'\x8a:info\0','info')
            self.assertEqual(write.call_count,1)
    def test_step_requires_marker_and_real_repl_completion(self):
        s={'expression':"(print 'gk-step)",'expected_line':'gk-step'}
        for replies,passed in [([b'\x87gk-step',b'\x87> t'],True),([b'\x87gk-step',b'\x87> nil'],False),([b'\x87wrong',b'\x87> t',None],False),([b'\x87gk-step',None],False)]:
            out=self.root/str(len(list(self.root.iterdir())));out.mkdir();w=r.Wire(9,out)
            with patch.object(w,'send') as send,patch.object(w,'packet',side_effect=replies):
                if passed:self.assertEqual(w.step(s,1),['gk-step','> t'])
                else:
                    with self.assertRaises(RuntimeError):w.step(s,1)
                self.assertEqual(send.call_count,1)
    def test_fragmented_wire_packets_and_crc(self):
        out=self.root/'a';out.mkdir();w=r.Wire(9,out)
        # Incoming PRINT frames use the same VESC framing but different command.
        def incoming(p):return bytes((2,len(p)))+p+r.binascii.crc_hqx(p,0).to_bytes(2,'big')+b'\x03'
        a=incoming(b'\x87gk-step');b=incoming(b'\x87> t');chunks=[a[:3],a[3:]+b]
        with patch.object(r.select,'select',return_value=([9],[],[])),patch.object(r.os,'read',side_effect=chunks):
            self.assertEqual(w.packet(r.time.monotonic()+1),b'\x87gk-step');self.assertEqual(w.packet(r.time.monotonic()+1),b'\x87> t')
        self.assertEqual((out/'rx-wire.bin').read_bytes(),a+b)
    def test_pending_reply_blocks_send(self):
        out=self.root/'a';out.mkdir();w=r.Wire(9,out);w.pending=[b'\x87> t']
        with patch.object(r.os,'write') as write:
            with self.assertRaises(RuntimeError):w.send(b'\0','identity')
            write.assert_not_called()
if __name__=='__main__':unittest.main()
