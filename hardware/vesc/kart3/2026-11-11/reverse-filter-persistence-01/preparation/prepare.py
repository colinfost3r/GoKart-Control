from pathlib import Path
import ast,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parent
BASE=Path('/Users/cofo/Projects/50 Day/GoKart Control/.worktrees/m5-v1.5/firmware/vesc-lisp/reverse-input/rx-filter-candidate.compact.lisp')
BASE_SHA='d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
base=BASE.read_bytes();assert hashlib.sha256(base).hexdigest()==BASE_SHA
wrapper="""(if (and (eq (sysinfo 'uuid) '(55 0 78 0 9 81 52 48 55 53 55 57))
         (eq (sysinfo 'fw-ver) '(6 2 0))
         (eq (gk-rx-filter-config-ok) t))
  (print (list 'gk-rx-autostart-result (gk-rx-filter-start t)))
  (print 'gk-rx-autostart-refused))
"""
source=base+wrapper.encode('ascii');assert b'\0' not in source
(ROOT/'rx-filter-autostart.lisp').write_bytes(source)
(ROOT/'rx-filter-autostart-code.bin').write_bytes(source+b'\0\0\0')
(ROOT/'autostart-wrapper.lisp').write_text(wrapper)
generator=ast.parse(Path('/tmp/gokart-rx-filter-lifecycle-20261111/make_mock_tests.py').read_text())
common=next(ast.literal_eval(n.value) for n in generator.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='common' for t in n.targets))
common+='''
(define mock-uuid '(55 0 78 0 9 81 52 48 55 53 55 57))
(define mock-fw '(6 2 0))
(define sysinfo (lambda (key)
  (if (eq key 'uuid) mock-uuid (if (eq key 'fw-ver) mock-fw nil))))
'''
boot='''
(wait gk-rx-filter-pid)
(and (>= gk-rx-filter-pid 0) (not gk-rx-filter-run)
     gk-rx-filter-active (= gk-rx-filter-applied DIR)
     (eq mock-calls '((250 detach 2 1) (250 override 2 DIR))))
'''
never='''
(wait gk-rx-filter-pid)
(and (>= gk-rx-filter-pid 0) (not gk-rx-filter-run)
     (not gk-rx-filter-active) (= gk-rx-filter-applied -1)
     (eq mock-calls nil))
'''
refused='''
(and (eq mock-output '(gk-rx-autostart-refused))
     (= gk-rx-filter-pid -1) (not gk-rx-filter-run)
     (not gk-rx-filter-active) (= gk-rx-filter-applied -1)
     (eq mock-calls nil))
'''
setup="(setvar 'mock-stop-at 1000)\n"
scenarios={
'boot-forward':(setup,boot.replace('DIR','0')),
'boot-reverse':(setup+"(setvar 'mock-pin (lambda () 0))\n",boot.replace('DIR','1')),
'pedal-high-refuses-arm':(setup+"(setvar 'mock-pedal (lambda () 0.13))\n",never),
'rpm-high-refuses-arm':(setup+"(setvar 'mock-rpm (lambda () 51.0))\n",never),
'fault-refuses-arm':(setup+"(setvar 'mock-fault (lambda () 1))\n",never),
'chatter-refuses-arm':(setup+"(setvar 'mock-pin (lambda () (if (< (mod mock-time 20) 10) 1 0)))\n",never),
'wrong-uuid-refused':("(setvar 'mock-uuid '(1 0 78 0 9 81 52 48 55 53 55 57))\n",refused),
'wrong-firmware-refused':("(setvar 'mock-fw '(6 3 0))\n",refused),
'wrong-test-firmware-refused':("(setvar 'mock-fw '(6 2 1))\n",refused),
'wrong-app-refused':("(setvar 'mock-app (lambda () 5))\n",refused),
'wrong-control-type-refused':("(setvar 'mock-ctrl (lambda () 2))\n",refused),
'pedal-release-then-reverse-qualifies':(setup+"(setvar 'mock-pin (lambda () 0))\n(setvar 'mock-pedal (lambda () (if (< mock-time 400) 0.13 0.09)))\n",boot.replace('DIR','1').replace('250','650')),
'rpm-stops-then-forward-qualifies':(setup+"(setvar 'mock-rpm (lambda () (if (< mock-time 400) 51.0 0.0)))\n",boot.replace('DIR','0').replace('250','650')),
'spawn-failure-no-retry':("(define memory-pressure (array-create (* (word-size) (- (mem-longest-free) 128))))\n",'''
(and (eq mock-output '((gk-rx-autostart-result nil) gk-rx-filter-spawn-failed))
     (not gk-rx-filter-run) (= gk-rx-filter-pid -1)
     (not gk-rx-filter-active) (= gk-rx-filter-applied -1) (eq mock-calls nil))
'''),
}
results=[]
for name,(before,after) in scenarios.items():
    p=ROOT/f'test-autostart-{name}.lisp';p.write_text(common+before+source.decode()+after)
    start=time.monotonic()
    try:
        run=subprocess.run(['/tmp/gokart-lbm-602/tests/test_lisp_code_cps','-h2464',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=12)
        code=run.returncode;out=run.stdout
    except subprocess.TimeoutExpired as e:
        code='timeout';out=e.stdout or b''
    (ROOT/(p.stem+'.log')).write_bytes(out)
    passed=code==1 and b'Test: OK!' in out and b'Result: t' in out
    results.append({'case':name,'pass':passed,'exit_code':code,'elapsed_seconds':round(time.monotonic()-start,3)})
    print('PASS' if passed else 'FAIL',name)
    if not passed: print(out.decode(errors='replace')[-3000:])
meta={'scope':'Supervised persistent trial; not production/fleet acceptance. Existing raw-input boot gap and watchdog suppression remain. Pedal must stay released until active/PID/matching direction is verified.',
      'base_compact_sha256':BASE_SHA,'base_bytes':len(base),'source_bytes':len(source),'source_sha256':hashlib.sha256(source).hexdigest(),
      'code_blob_bytes':len(source)+3,'code_blob_sha256':hashlib.sha256(source+b'\0\0\0').hexdigest(),
      'code_blob_format':'ASCII source followed by one NUL and big-endian uint16 zero import count, matching VESC Tool6.02 lispPackImports. No eight-byte flash size/CRC/flags header is included.',
      'uuid_guard':'37004e000951343037353739','fw_guard':[6,2,0],'app_guard':[2,3],
      'all_pass':all(r['pass'] for r in results),'tests':results}
(ROOT/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({k:v for k,v in meta.items() if k!='tests'},indent=2))
