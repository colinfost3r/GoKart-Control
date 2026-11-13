"""Run guarded-autostart boot cases in an already built, pinned VESC6.02 LispBM VM.

Offline only: hardware/sysinfo/time are mocked. No device or network access.
This verifies candidate startup logic, not MCU boot ordering, watchdog recovery,
real timing, electrical input quality or physical motor behavior.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

SOURCE_SHA256 = '30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700'
BASE_SHA256 = 'd530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
CODE_BLOB_SHA256 = 'a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801'
FIRMWARE_COMMIT = 'f7c2b34e1cff2234cae98be3abf0cd50e249558f'

def digest(data):
    return hashlib.sha256(data).hexdigest()

common = '''
(define mock-time 0)
(define mock-stop-at -1)
(define mock-step (lambda () 2))
(define mock-calls nil)
(define mock-output nil)
(define mock-pin (lambda () 1))
(define mock-pedal (lambda () 0.0))
(define mock-rpm (lambda () 0.0))
(define mock-fault (lambda () 0))
(define mock-app (lambda () 2))
(define mock-ctrl (lambda () 3))
(define systime (lambda () mock-time))
(define secs-since (lambda (stamp) (/ (- mock-time stamp) 1000.0)))
(define gpio-read (lambda (pin) (if (eq pin 'pin-rx) (mock-pin) -1)))
(define get-adc-decoded (lambda (channel) (if (= channel 0) (mock-pedal) -1)))
(define get-rpm (lambda () (mock-rpm)))
(define get-fault (lambda () (mock-fault)))
(define conf-get (lambda (key) (if (eq key 'app-to-use) (mock-app)
                             (if (eq key 'adc-ctrl-type) (mock-ctrl) -1))))
(define print (lambda (value) (progn (setvar 'mock-output (cons value mock-output)) t)))
(define app-adc-override (lambda (target value)
  (progn (setvar 'mock-calls (cons (list mock-time 'override target value) mock-calls)) t)))
(define app-adc-detach (lambda (target value)
  (progn (setvar 'mock-calls (cons (list mock-time 'detach target value) mock-calls)) t)))
(define sleep (lambda (seconds)
  (progn
    (setvar 'mock-time (+ mock-time (mock-step)))
    (if (and (>= mock-stop-at 0) (>= mock-time mock-stop-at))
      (setvar 'gk-rx-filter-run nil))
    t)))

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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runner', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New directory for cases and logs')
    args = parser.parse_args()
    runner = args.runner.resolve(strict=True)
    source_path = Path(__file__).resolve().parents[1] / 'rx-filter-autostart.lisp'
    source = source_path.read_bytes()
    code_blob = source + b'\0\0\0'  # NUL + BEuint16 zero imports; excludes flash header.
    if (len(source) != 3981 or digest(source) != SOURCE_SHA256 or
            digest(source[:3732]) != BASE_SHA256 or digest(code_blob) != CODE_BLOB_SHA256):
        raise ValueError('Autostart source/package differs from the reviewed artifact')
    source_text = source.decode('ascii')
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for name, (before, after) in scenarios.items():
        case = output / f'test-autostart-{name}.lisp'
        case.write_text(common + before + source_text + after)
        try:
            run = subprocess.run([str(runner), '-h', '2464', str(case)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, timeout=45)
            log = run.stdout
            passed = run.returncode == 1 and 'Test: OK!' in log and 'Result: t' in log
            code = run.returncode
        except subprocess.TimeoutExpired as error:
            log = error.stdout or ''
            if isinstance(log, bytes):
                log = log.decode('utf-8', errors='replace')
            log += '\nHOST TEST TIMEOUT\n'
            passed, code = False, None
        case.with_suffix('.log').write_text(log)
        results.append({'case': name, 'passed': passed, 'returncode': code,
                        'sha256': digest(case.read_bytes())})
        print(f"{'PASS' if passed else 'FAIL'} {case.name}")
    manifest = {'recorded_at': datetime.now(timezone.utc).isoformat(),
                'firmware_source_commit': FIRMWARE_COMMIT,
                'host_runner_sha256': digest(runner.read_bytes()), 'heap_cons_cells': 2464,
                'source_sha256': digest(source), 'source_bytes': len(source),
                'unchanged_base_compact_sha256': BASE_SHA256,
                'canonical_code_blob_sha256': digest(code_blob), 'canonical_code_blob_bytes': len(code_blob),
                'limitation': 'Mocked host interpreter. Does not prove filter-first MCU startup, watchdog behavior, real deadlines or physical safety.',
                'results': results}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    passed = sum(r['passed'] for r in results)
    print(f'{passed}/{len(results)} passed; logs: {output}')
    return 0 if results and passed == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
