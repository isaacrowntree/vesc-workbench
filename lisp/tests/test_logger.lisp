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

; summary MUST be last
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
