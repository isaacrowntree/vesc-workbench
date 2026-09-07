; Flight recorder tests. The stubs let a whole ride be played through the
; recorder and the summary asserted - no board, no waiting for a fault to
; happen by luck.
(define fails 0)
(define chk (lambda (name got want)
  (if (= got want)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

(define chkf (lambda (name got want)
  (if (< (abs (- got want)) 0.01)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

; drive one sample with a given state
(define sample (lambda (im ib tf tm v r d f rpm2) {
    (setq S-current im) (setq S-current-in ib)
    (setq S-temp-fet tf) (setq S-temp-mot tm)
    (setq S-vin v) (setq S-rpm r) (setq S-duty d)
    (setq S-fault f) (setq S-can-rpm rpm2)
    (log-tick)
}))

(print "== a quiet ride leaves quiet marks")
(log-reset)
(sample 5.0 3.0 30.0 32.0 48.0 8000.0 0.3 0 8000.0)
(sample 6.0 3.5 31.0 33.0 47.8 8200.0 0.31 0 8100.0)
(chkf "peak motor A"  hi-motor 6.0)
(chkf "peak pack A"   hi-batt 3.5)
(chkf "peak FET"      hi-fet 31.0)
(chk  "no faults"     flt-count 0)
(chk  "no tc events"  tc-events 0)
(chk  "two samples"   samples 2)

(print "== a hard pull sets the high-water marks")
(sample 78.0 29.0 71.0 80.0 41.2 34000.0 0.94 0 33900.0)
(chkf "peak motor A"     hi-motor 78.0)
(chkf "peak pack A"      hi-batt 29.0)
(chkf "peak FET"         hi-fet 71.0)
(chkf "peak motor temp"  hi-mot 80.0)
(chkf "min voltage"      lo-vin 41.2)
(chkf "peak erpm"        hi-erpm 34000.0)

(print "== regen is recorded as its own extreme, not lost in the peaks")
(sample -60.0 -7.5 55.0 60.0 49.9 20000.0 -0.4 0 19950.0)
(chkf "peak regen motor A" lo-motor -60.0)
(chkf "peak regen pack A"  lo-batt -7.5)
(chkf "peak motor A kept"  hi-motor 78.0)

(print "== a resting pack is not mistaken for a sagging one")
(log-reset)
(sample 0.0 0.0 25.0 25.0 36.5 0.0 0.0 0 0.0)
(chkf "no load, no sag recorded" lo-vin 200.0)
(sample 40.0 18.0 40.0 45.0 41.0 20000.0 0.6 0 19900.0)
(chkf "under load it records"    lo-vin 41.0)

(print "== the first fault is kept, with the context that explains it")
(log-reset)
(sample 70.0 25.0 60.0 65.0 43.0 30000.0 0.8 3 29800.0)
(sample 10.0 4.0 61.0 66.0 44.0 12000.0 0.3 6 11900.0)
(chk  "fault code is the first"   flt-code 3)
(chk  "later faults still counted" flt-count 2)
(chkf "voltage at the fault"      flt-vin 43.0)
(chkf "erpm at the fault"         flt-erpm 30000.0)
(chkf "duty at the fault"         flt-duty 0.8)

(print "== traction control engagement, which nothing else reports")
(log-reset)
(sample 60.0 22.0 50.0 55.0 44.0 20000.0 0.7 0 19000.0)   ; 1000 apart
(chk  "small difference is not an event" tc-events 0)
(chkf "worst difference tracked"          tc-worst 1000.0)
(sample 60.0 22.0 50.0 55.0 44.0 26000.0 0.7 0 19000.0)   ; 7000 apart
(chk  "over the limit counts"             tc-events 1)
(chkf "worst difference updated"          tc-worst 7000.0)

(print "== an unreadable second motor reports nothing rather than guessing")
(log-reset)
(setq S-can-rpm nil)
(sample 60.0 22.0 50.0 55.0 44.0 26000.0 0.7 0 nil)
(chk "no phantom tc events" tc-events 0)
(chkf "no phantom worst"    tc-worst 0.0)

(print "== reset clears everything")
(log-reset)
(chkf "motor"  hi-motor 0.0)
(chk  "faults" flt-code 0)
(chk  "tc"     tc-events 0)
(chk  "samples" samples 0)

(print "== a long ride does not grow the heap")
; This runs on the motor controller of a board somebody rides, for hours, and
; the failure it must not have is the one that only shows up late: a recorder
; that creeps until LispBM runs out and stops - or worse, thrashes the
; collector while the rider is on it. So the whole ride is played through at
; three lengths and the heap compared, rather than reasoned about.
;
; It also pins the derived uptime. Accumulating 0.2 in a float drifts: this
; ride used to report 5000.18 seconds where it had run exactly 5000.
(log-reset)
(gc)
(def free0 (mem-longest-free))

(defun soak (n) {
    (var i 0)
    (loopwhile (< i n) {
        ; deliberately restless - every high-water branch taken, every float
        ; re-boxed. The quiet case would prove nothing.
        (setq S-current (+ 10.0 (mod i 70)))
        (setq S-current-in (+ 5.0 (mod i 25)))
        (setq S-temp-fet (+ 20.0 (mod i 60)))
        (setq S-temp-mot (+ 20.0 (mod i 60)))
        (setq S-vin (- 50.0 (/ (to-float (mod i 100)) 10.0)))
        (setq S-rpm (* 100.0 (mod i 300)))
        (setq S-duty (/ (to-float (mod i 90)) 100.0))
        (setq S-can-rpm (* 100.0 (mod i 290)))
        (setq S-fault 0)
        (log-tick)
        (setq i (+ i 1))
    })
})

(soak 500)
(gc)
(def free1 (mem-longest-free))
(soak 24500)
(gc)
(def free2 (mem-longest-free))

(chk "500 ticks and 25,000 ticks leave the same heap" free1 free2)
(chk "and it is no worse than before the ride"
     (if (>= free2 free0) 1 0) 1)
(chk "25,000 ticks is 25,000 samples" samples 25000)
(chkf "uptime is exact, not accumulated" uptime 5000.0)

(log-reset)

; summary MUST be last
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
