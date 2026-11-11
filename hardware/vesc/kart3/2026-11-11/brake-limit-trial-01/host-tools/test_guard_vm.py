#!/usr/bin/env python3
"""Offline mocked-native tests of the exact fixed brake-limit REPL expressions."""
import hashlib
import json
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent / 'guard-vm-results'
RUNNER = Path('/tmp/gokart-lbm-602/tests/test_lisp_code_cps')
TEMPLATE = "(print (list 'gk-brake-limit-result (if (and (= (conf-get 'l-current-min) EXPECTED) (eq (gk-rx-filter-safe) t) (eq (gk-rx-filter-config-ok) t) gk-rx-filter-run gk-rx-filter-active (= gk-rx-filter-applied 0) (= (gpio-read 'pin-rx) 1) (<= (get-vin) 82.0)) (conf-set 'l-current-min TARGET) nil) (conf-get 'l-current-min)))"
COMMON = '''
(define mock-limit INITIAL)
(define mock-other-field 140.0)
(define mock-safe t)
(define mock-config t)
(define mock-rx 1)
(define mock-vin 81.5)
(define mock-set-calls nil)
(define mock-output nil)
(define gk-rx-filter-run t)
(define gk-rx-filter-active t)
(define gk-rx-filter-applied 0)
(define conf-get (lambda (key) (if (eq key 'l-current-min) mock-limit mock-other-field)))
(define conf-set (lambda (key value) (progn
  (setvar 'mock-set-calls (cons (list key value) mock-set-calls))
  (if (eq key 'l-current-min) (progn (setvar 'mock-limit value) t) nil))))
(define gk-rx-filter-safe (lambda () mock-safe))
(define gk-rx-filter-config-ok (lambda () mock-config))
(define gpio-read (lambda (pin) (if (eq pin 'pin-rx) mock-rx -1)))
(define get-vin (lambda () mock-vin))
(define print (lambda (value) (progn (setvar 'mock-output (cons value mock-output)) t)))
'''

def digest(raw): return hashlib.sha256(raw).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    results = []
    expressions = {}
    scenarios = {
        'permitted-one-field-one-call': ('', True),
        'voltage-exact-boundary': ("(setvar 'mock-vin 82.0)", True),
        'voltage-over-boundary': ("(setvar 'mock-vin 82.001)", False),
        'unsafe-refused': ("(setvar 'mock-safe nil)", False),
        'safe-nonboolean-refused': ("(setvar 'mock-safe 1)", False),
        'config-refused': ("(setvar 'mock-config nil)", False),
        'config-nonboolean-refused': ("(setvar 'mock-config 1)", False),
        'worker-not-running-refused': ("(setvar 'gk-rx-filter-run nil)", False),
        'filter-inactive-refused': ("(setvar 'gk-rx-filter-active nil)", False),
        'reverse-applied-refused': ("(setvar 'gk-rx-filter-applied 1)", False),
        'unarmed-direction-refused': ("(setvar 'gk-rx-filter-applied -1)", False),
        'raw-reverse-refused': ("(setvar 'mock-rx 0)", False),
        'wrong-existing-limit-refused': ("(setvar 'mock-limit -3.0)", False),
    }
    for mode, expected, target in [('apply', '0.0', '-5.0'), ('restore', '-5.0', '0.0')]:
        expression = TEMPLATE.replace('EXPECTED', expected).replace('TARGET', target)
        expressions[mode] = {'expression': expression, 'expression_bytes': len(expression.encode('ascii')),
                             'vesc_payload_bytes_including_id_nul': len(expression.encode('ascii')) + 2,
                             'sha256': digest(expression.encode('ascii'))}
        assert len(expression.encode('ascii')) + 2 <= 512
        (OUT / (mode + '.repl')).write_text(expression + '\n')
        for name, (setup, permitted) in scenarios.items():
            initial = '-3.0' if name == 'wrong-existing-limit-refused' else expected
            ending = target if permitted else initial
            calls = "'((l-current-min TARGET))".replace('TARGET', target) if permitted else 'nil'
            flag = 't' if permitted else 'nil'
            assertion = f"""
(and (= mock-limit {ending}) (= mock-other-field 140.0)
     (eq mock-set-calls {calls})
     (eq mock-output '((gk-brake-limit-result {flag} {ending}))))
"""
            case = OUT / (mode + '-' + name + '.lisp')
            case.write_text(COMMON.replace('INITIAL', expected) + setup + '\n' + expression + '\n' + assertion)
            ran = subprocess.run([str(RUNNER), '-h', '2464', str(case)], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, timeout=15)
            case.with_suffix('.log').write_text(ran.stdout)
            ok = ran.returncode == 1 and 'Test: OK!' in ran.stdout and 'Result: t' in ran.stdout
            results.append({'case': case.name, 'passed': ok, 'exit_code': ran.returncode,
                            'source_sha256': digest(case.read_bytes())})
            print(('PASS' if ok else 'FAIL'), case.name)
    manifest = {'scope': 'Offline only; no device, serial, config store, native motor command or flash calls',
                'pinned_firmware_commit': 'f7c2b34e1cff2234cae98be3abf0cd50e249558f',
                'pinned_lispbm_tree': '5173bfae688fb89e45fba09011e33404a4ee7c29',
                'runner': str(RUNNER), 'runner_sha256': digest(RUNNER.read_bytes()),
                'runner_heap_cons_cells': 2464, 'expressions': expressions, 'results': results,
                'all_passed': all(r['passed'] for r in results),
                'limits': 'Native functions are mocked. This tests exact Lisp expression semantics, guard refusals and one-field setter call count/result. It does not prove MCU scheduling, hardware state or physical safety.'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(str(sum(r['passed'] for r in results)) + '/' + str(len(results)) + ' passed')
    return 0 if manifest['all_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
