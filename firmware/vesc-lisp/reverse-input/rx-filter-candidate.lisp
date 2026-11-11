; VESC 6.02 / kart 3 RX only. VOLATILE BENCH TRIAL, NOT A PERMANENT FIX.
; DEFINITIONS ONLY: loading does not change inputs.
; Do not load over an active copy: definitions reset lifecycle tracking.
; Host preflight must verify the kart UUID and saved settings: app=2, ctrl_type=3,
; buttons=0 (cruise/inversion disabled), servo_out_enable=0, ADC hyst=0.15,
; safe-start enabled and unchanged pedal calibration. Freeze that app configuration
; throughout this trial; no other USB/BLE/configuration writers may change it.
; No conflicting existing Lisp/input overrides. ADC_UART app=5 is unsupported.
; No GPIO configuration, throttle override, timeout reset, motor command or
; configuration/flash write. Button detach includes cruise; buttons=0 is required.
;
; Provisional bench interlock: decoded pedal <=0.12, |ERPM| <=50, fault=0 for
; 250 ms; RX stable for 50 ms. Gaps >10 ms restart qualification. Nominal 2 ms
; samples are not hard realtime. Rollback refuses a gap >10 ms.
; Reverse is RX low. These thresholds require wheels-up commissioning.
; Observed released-pedal range on 2026-11-11: 0.081..0.106 before native
; deadband. The 0.12 guard remains below unchanged 0.15 native deadband; it
; identifies a conservative zero-command region, not physical pedal position.
; Severe chatter can block arming. A wrong level held >=50 ms at rest can still
; be accepted: verify printed applied direction against the switch before driving.
; Native pedal/Hall calibration and motor-braking-current setting remain unchanged.
;
; Manual sequence, each call completed before the next:
;   (gk-rx-filter-start t)     ; t asserts host preflight + supervised bench setup
;   (gk-rx-filter-stop)        ; join worker; leave last reverse override held
;   (gk-rx-filter-rollback t)  ; at rest, restore raw RX only if it agrees for 250 ms
; The eq-wrapped helper calls in and preserve lexical scope in pinned 6.02.
; Do not simplify them without rerunning the actual interpreter tests.
; No autostart/persistent install. No calls below start the worker.
; Errors/stop hold the last C-side override; physical switch then stops updating.
; Whole-controller reset returns to configured raw input. A watchdog reset may
; suppress Lisp autostart. Never promise this candidate removes electrical faults.
(progn
  (define gk-rx-filter-run nil)
  (define gk-rx-filter-active nil)
  (define gk-rx-filter-pid -1)
  (define gk-rx-filter-applied -1)
  (define gk-rx-filter-safe
    (lambda ()
      (let ((rpm (get-rpm)))
        (and (<= (get-adc-decoded 0) 0.12)
             (>= rpm -50.0) (<= rpm 50.0) (= (get-fault) 0)))))
  (define gk-rx-filter-config-ok
    (lambda ()
      (and (= (conf-get 'app-to-use) 2) (= (conf-get 'adc-ctrl-type) 3))))
  (define gk-rx-filter-worker
    (lambda ()
      (progn
        (let ((candidate (gpio-read 'pin-rx)) (candidate-at (systime))
              (safe-at (systime)) (safe-previous nil) (sample-at (systime)))
          (loopwhile gk-rx-filter-run
            (let ((raw (gpio-read 'pin-rx)) (safe (gk-rx-filter-safe))
                  (gap (secs-since sample-at)))
              (progn
                (setvar 'sample-at (systime))
                (if (> gap 0.010)
                  (progn (setvar 'candidate-at (systime))
                         (setvar 'safe-at (systime))
                         (setvar 'safe-previous nil)))
                (if (not (gk-rx-filter-config-ok))
                  (progn (setvar 'gk-rx-filter-run nil)
                         (print 'gk-rx-filter-config-changed)))
                (if (!= raw candidate)
                  (progn (setvar 'candidate raw)
                         (setvar 'candidate-at (systime))))
                (if (and safe (not safe-previous)) (setvar 'safe-at (systime)))
                (setvar 'safe-previous safe)
                (if (and gk-rx-filter-run safe
                         (>= (secs-since safe-at) 0.250)
                         (>= (secs-since candidate-at) 0.050))
                  (let ((desired (if (= candidate 0) 1 0)))
                    (if (or (not gk-rx-filter-active)
                            (!= desired gk-rx-filter-applied))
                      (if (and (= (if (= (gpio-read 'pin-rx) 0) 1 0) desired)
                               (eq (gk-rx-filter-config-ok) t)
                               (eq (gk-rx-filter-safe) t) gk-rx-filter-run
                               (<= (secs-since sample-at) 0.010))
                        (progn
                          ; Seed qualified actual state BEFORE detaching buttons.
                          (app-adc-override 2 desired)
                          (if (not gk-rx-filter-active)
                            (progn (app-adc-detach 2 1)
                                   (setvar 'gk-rx-filter-active t)))
                          (setvar 'gk-rx-filter-applied desired)
                          (print (list 'gk-rx-filter-applied desired)))
                        (progn (setvar 'candidate-at (systime))
                               (setvar 'safe-at (systime))
                               (setvar 'safe-previous nil))))))
                (sleep 0.002)))))
        (print (list 'gk-rx-filter-stopped-holding gk-rx-filter-applied))
        t)))
  (define gk-rx-filter-start
    (lambda (preflight-ok)
      (if (or (not preflight-ok) gk-rx-filter-run gk-rx-filter-active
              (!= gk-rx-filter-pid -1) (not (gk-rx-filter-config-ok)))
        (progn (print 'gk-rx-filter-refused) nil)
        (progn
          (setvar 'gk-rx-filter-run t)
          (setvar 'gk-rx-filter-pid (spawn 256 gk-rx-filter-worker))
          (if (< gk-rx-filter-pid 0)
            (progn (setvar 'gk-rx-filter-run nil)
                   (print 'gk-rx-filter-spawn-failed) nil)
            gk-rx-filter-pid)))))
  (define gk-rx-filter-stop
    (lambda ()
      (progn
        (setvar 'gk-rx-filter-run nil)
        ; IDs are recycled context-memory addresses. A dead worker's ID may
        ; now belong to this REPL context; waiting on self would never finish.
        (if (and (>= gk-rx-filter-pid 0) (!= gk-rx-filter-pid (self)))
          (wait gk-rx-filter-pid))
        (setvar 'gk-rx-filter-pid -1)
        (print (list 'gk-rx-filter-joined-holding gk-rx-filter-applied))
        t)))
  (define gk-rx-filter-rollback
    (lambda (supervised-ok)
      (if (or (not supervised-ok) gk-rx-filter-run
              (!= gk-rx-filter-pid -1) (not gk-rx-filter-active)
              (not (gk-rx-filter-config-ok)))
        (progn (print 'gk-rx-filter-rollback-refused) nil)
        (let ((started (systime)) (sample-at (systime)) (ok t))
          (progn
            (loopwhile (and ok (< (secs-since started) 0.250))
              (progn
                (if (> (secs-since sample-at) 0.010) (setvar 'ok nil))
                (setvar 'sample-at (systime))
                (if (or gk-rx-filter-run (!= gk-rx-filter-pid -1)
                        (not (gk-rx-filter-config-ok))
                        (not (gk-rx-filter-safe))
                        (!= (if (= (gpio-read 'pin-rx) 0) 1 0)
                            gk-rx-filter-applied))
                  (setvar 'ok nil))
                (if (> (secs-since sample-at) 0.010) (setvar 'ok nil))
                (sleep 0.002)))
            (if (and ok (eq (gk-rx-filter-safe) t)
                     (eq (gk-rx-filter-config-ok) t)
                     (not gk-rx-filter-run) (= gk-rx-filter-pid -1)
                     (= (if (= (gpio-read 'pin-rx) 0) 1 0) gk-rx-filter-applied)
                     (<= (secs-since sample-at) 0.010))
              (progn
                (app-adc-detach 2 0)
                (setvar 'gk-rx-filter-active nil)
                (setvar 'gk-rx-filter-applied -1)
                (print 'gk-rx-filter-raw-rx-restored)
                t)
              (progn (print 'gk-rx-filter-rollback-not-at-rest-or-rx-disagrees) nil)))))))
  t)
