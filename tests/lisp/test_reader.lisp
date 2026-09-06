; Integration tests: bytes on a wire -> frames handled -> replies owed.
; These drive the real reader (`pump`) through a fake UART, so they exercise
; framing and resync, not just the pure helpers.
(define fails 0)
(define chk (lambda (name got want)
  (if (= got want)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

; a COMM_GET_VALUES_SELECTIVE request, which is what the DAVEGA polls with
(define req50 (lambda () {
    (var pl (bufcreate 5))
    (bufset-u8 pl 0 50)
    (bufset-u8 pl 1 0) (bufset-u8 pl 2 0) (bufset-u8 pl 3 3) (bufset-u8 pl 4 255)
    (mkframe pl)
}))

(define reset-counters (lambda () {
    (setq dbg-in 0) (setq dbg-bad 0) (setq dbg-sync 0) (setq dbg-proc 0)
}))

(print "== a clean stream of polls is answered one for one")
(wire-reset) (reset-counters)
(looprange i 0 10 (wire-put (req50)))
(drain)
(chk "10 frames read"     dbg-in  10)
(chk "10 replies owed"    replies 10)
(chk "nothing malformed"  dbg-bad 0)

(print "== a header split across a read must not eat the next frame")
; This is the regression. The reader asks for the start byte, gets it, then
; asks for the length byte - and the UART has nothing more to give yet. If the
; header were read as one 2-byte call, that partial read would leave the length
; byte to be misread as the NEXT frame's start byte, and every frame after it
; would be lost until a gap in traffic resynced things.
(wire-reset) (reset-counters)
(looprange i 0 10 (wire-put (req50)))
(cap 1)          ; first read delivers a single byte
(drain)
(chk "still 10 frames read"  dbg-in  10)
(chk "still 10 replies owed" replies 10)
(chk "no frames lost"        dbg-bad 0)

(print "== repeated splits mid-stream stay aligned")
(wire-reset) (reset-counters)
(looprange i 0 10 (wire-put (req50)))
(cap 1) (cap 3) (cap 1) (cap 2) (cap 1)
(drain)
(chk "10 frames survive chunking" dbg-in  10)
(chk "10 replies owed"            replies 10)

(print "== a truncated tail is dropped, not forwarded")
(wire-reset) (reset-counters)
(wire-put (req50))
{ (var f (req50)) (setq wire-len (- wire-len 0))   ; full frame above
  (bufcpy wire wire-len f 0 4) (setq wire-len (+ wire-len 4)) }  ; then 4 bytes of a second
(drain)
(chk "only the complete frame handled" dbg-in  1)
(chk "only one reply owed"             replies 1)
(chk "the runt counted as bad"         dbg-bad 1)

(print "== an implausible length byte is rejected")
(wire-reset) (reset-counters)
{ (bufset-u8 wire 0 2) (bufset-u8 wire 1 200) (setq wire-len 2) }
(drain)
(chk "rejected"           dbg-bad 1)
(chk "nothing forwarded"  dbg-proc 0)

(print "== leading garbage is skipped without losing the frame behind it")
(wire-reset) (reset-counters)
{ (bufset-u8 wire 0 99) (bufset-u8 wire 1 7) (setq wire-len 2) }
(wire-put (req50))
(drain)
(chk "frame still read"    dbg-in  1)
(chk "reply still owed"    replies 1)
(chk "garbage counted"     (if (> dbg-sync 0) 1 0) 1)

(print "== a single stray byte realigns onto the frame behind it")
; One byte of garbage means the 2-byte header read returns [garbage][start],
; so the start byte is the SECOND one. Dropping that read would take the frame
; with it; the reader realigns onto it instead.
(wire-reset) (reset-counters)
{ (bufset-u8 wire 0 99) (setq wire-len 1) }
(looprange i 0 5 (wire-put (req50)))
(drain)
(chk "all 5 frames read"  dbg-in  5)
(chk "all 5 answered"     replies 5)
(chk "nothing malformed"  dbg-bad 0)

; summary MUST be last
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
