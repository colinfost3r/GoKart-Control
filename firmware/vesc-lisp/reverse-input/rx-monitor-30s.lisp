; VESC 6.02, one volatile REPL expression. Reads only. No GPIO reconfiguration.
; Existing ADC app already owns RX as an input with pull-up.
; Print summary every 1 second, nominal 2 ms sampling, stop after 30 seconds.
(let ((started (systime)) (report-at (systime)) (edge-at (systime))
      (sample-at (systime)) (raw (gpio-read 'pin-rx))
      (stable (gpio-read 'pin-rx)) (edges 0) (settled 0)
      (samples 0) (max-gap 0.0))
  (progn
    (print '(gk-rx-monitor elapsed raw edges stable settled samples max-gap-ms adc rpm fault))
    (loopwhile (< (secs-since started) 30.0)
      (let ((next (gpio-read 'pin-rx)) (gap (secs-since sample-at)))
        (progn
          (setvar 'sample-at (systime))
          (setvar 'samples (+ samples 1))
          (if (> gap max-gap) (setvar 'max-gap gap))
          (if (> gap 0.010) (setvar 'edge-at (systime)))
          (if (!= next raw)
            (progn (setvar 'raw next) (setvar 'edges (+ edges 1))
                   (setvar 'edge-at (systime))))
          (if (and (!= raw stable) (>= (secs-since edge-at) 0.050))
            (progn (setvar 'stable raw) (setvar 'settled (+ settled 1))))
          (if (>= (secs-since report-at) 1.0)
            (progn
              (print (list 'gk-rx-monitor (secs-since started) raw edges stable
                           settled samples (* 1000.0 max-gap)
                           (get-adc-decoded 0) (get-rpm) (get-fault)))
              (setvar 'report-at (systime))))
          (sleep 0.002))))
    (print (list 'gk-rx-monitor-done (secs-since started) edges settled samples
                 (* 1000.0 max-gap)))
    t))
