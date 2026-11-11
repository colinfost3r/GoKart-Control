"""Generate mocked cases for the LispBM interpreter vendored in VESC 6.02."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", required=True, type=Path, help="New directory for generated cases")
args = parser.parse_args()
root = args.out.resolve()
root.mkdir(parents=True, exist_ok=False)
source = Path(__file__).resolve().parents[1]
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
'''
filter_src = (source/'rx-filter-candidate.lisp').read_text()
monitor_src = (source/'rx-monitor-30s.lisp').read_text()
scenarios = {
'stall-restarts-qualification': '''
(setvar 'mock-pin (lambda () 0))
(setvar 'mock-step (lambda () (if (= mock-time 200) 100 2)))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(eq mock-calls '((550 detach 2 1) (550 override 2 1)))
''',
'rollback-stall-refused': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'mock-step (lambda () (if (= mock-time 100) 100 2)))
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'rollback-stall-crossing-deadline-refused': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'mock-step (lambda () (if (= mock-time 248) 1000 2)))
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'fresh-pedal-check-restarts-qualification': '''
(define mock-pedal-reads 0)
(setvar 'mock-pedal (lambda ()
  (if (= mock-time 250)
    (progn (setvar 'mock-pedal-reads (+ mock-pedal-reads 1))
           (if (> mock-pedal-reads 1) 0.5 0.0)) 0.0)))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(eq mock-calls '((502 detach 2 1) (502 override 2 0)))
''',
'fresh-check-stall-restarts-qualification': '''
(define mock-pedal-reads 0)
(setvar 'mock-pedal (lambda ()
  (progn
    (if (= mock-time 250)
      (progn (setvar 'mock-pedal-reads (+ mock-pedal-reads 1))
             (if (> mock-pedal-reads 1) (setvar 'mock-time 350)))) 0.0)))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(eq mock-calls '((602 detach 2 1) (602 override 2 0)))
''',
'rollback-body-helper-stall-refused': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'mock-pedal (lambda () (progn
  (if (= mock-time 100) (setvar 'mock-time 200)) 0.0)))
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'rollback-final-helper-stall-refused': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'mock-pedal (lambda () (progn
  (if (= mock-time 250) (setvar 'mock-time 350)) 0.0)))
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'load-is-disarmed': '''(and (eq mock-calls nil) (not gk-rx-filter-active)
 (not gk-rx-filter-run) (= gk-rx-filter-pid -1) (= mock-time 0))''',
'boot-reverse-seed-before-detach': '''
(setvar 'mock-pin (lambda () 0))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(and (= mock-time 1000) (= gk-rx-filter-applied 1) gk-rx-filter-active
  (eq mock-calls '((250 detach 2 1) (250 override 2 1))))
''',
'glitch-rejected-sustained-accepted': '''
(setvar 'mock-pin (lambda ()
  (if (or (and (>= mock-time 500) (< mock-time 520)) (>= mock-time 600)) 0 1)))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(eq mock-calls '((650 override 2 1) (250 detach 2 1) (250 override 2 0)))
''',
'pedal-and-rpm-interlock': '''
(setvar 'mock-pin (lambda () (if (>= mock-time 600) 0 1)))
(setvar 'mock-pedal (lambda () (if (and (>= mock-time 400) (< mock-time 1000)) 0.5 0.0)))
(setvar 'mock-rpm (lambda () (if (and (>= mock-time 900) (< mock-time 1100)) 100.0 0.0)))
(setvar 'mock-stop-at 1600)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(eq mock-calls '((1350 override 2 1) (250 detach 2 1) (250 override 2 0)))
''',
'fault-blocks-initial-arm': '''
(setvar 'mock-fault (lambda () 1))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(and (eq mock-calls nil) (not gk-rx-filter-active))
''',
'preflight-false-refused': '''
(and (not (gk-rx-filter-start nil)) (eq mock-calls nil) (not gk-rx-filter-run))
''',
'adc-uart-config-refused': '''
(setvar 'mock-app (lambda () 5))
(and (not (gk-rx-filter-start t)) (eq mock-calls nil) (not gk-rx-filter-run))
''',
'config-change-holds-last': '''
(setvar 'mock-app (lambda () (if (>= mock-time 600) 5 2)))
(setvar 'mock-stop-at 1000)
(setvar 'gk-rx-filter-run t)
(gk-rx-filter-worker)
(and (= mock-time 602) (not gk-rx-filter-run) gk-rx-filter-active
  (eq mock-calls '((250 detach 2 1) (250 override 2 0))))
''',
'rollback-refused-unjoined': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'gk-rx-filter-pid 7)
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil))
''',
'rollback-refused-pedal': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(setvar 'mock-pedal (lambda () 0.5))
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'rollback-refused-rx-mismatch': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 1)
(and (not (gk-rx-filter-rollback t)) (eq mock-calls nil) gk-rx-filter-active)
''',
'rollback-at-rest-matching-rx': '''
(setvar 'gk-rx-filter-active t)
(setvar 'gk-rx-filter-applied 0)
(and (gk-rx-filter-rollback t) (eq mock-calls '((250 detach 2 0)))
     (not gk-rx-filter-active) (= gk-rx-filter-applied -1))
''',
'start-stop-join-holds-last': '''
(setvar 'mock-pin (lambda () 0))
(setvar 'mock-stop-at 1000)
(gk-rx-filter-start t)
(wait gk-rx-filter-pid)
(gk-rx-filter-stop)
(and (= gk-rx-filter-pid -1) (not gk-rx-filter-run) gk-rx-filter-active
  (eq mock-calls '((250 detach 2 1) (250 override 2 1))))
''',
}
for name, body in scenarios.items():
    (root/f'test-{name}.lisp').write_text(common+'\n'+filter_src+'\n'+body)
monitor_setup = '''
(setvar 'mock-pin (lambda ()
  (if (or (and (>= mock-time 100) (< mock-time 120))
          (and (>= mock-time 1000) (< mock-time 2000))) 0 1)))
'''
monitor_assert = '''
(and (= mock-time 30000) (eq mock-calls nil) (= (length mock-output) 31)
  (eq (car (cdr (cdr (car mock-output)))) 4)
  (eq (car (cdr (cdr (cdr (car mock-output))))) 2)
  (eq (car (cdr (cdr (cdr (cdr (car mock-output)))))) 15000))
'''
(root/'test-monitor-readonly-bounded.lisp').write_text(common+monitor_setup+monitor_src+monitor_assert)

compact_src = (source/'rx-monitor-compact.repl').read_text()
compact_assert = """
(and (= mock-time 30000) (eq mock-calls nil) (= (length mock-output) 30)
     (eq (car mock-output) '(done 4 15000)))
"""
(root/'test-monitor-compact-readonly-bounded.lisp').write_text(common+monitor_setup+compact_src+compact_assert)
print('Compact monitor packet bytes:', len(compact_src.strip().encode()) + 2)

print(f'Wrote {len(scenarios)+2} pinned-interpreter mock tests')
