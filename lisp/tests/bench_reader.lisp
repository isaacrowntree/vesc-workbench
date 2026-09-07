; Reader cost bench. Same wire, same frames, different read strategies.
; What we can count host-side is UART calls and buffer allocations per frame -
; both of which the LispBM interpreter pays for directly, so they track the
; CPU figure `make davega-debug` reports off the board.
(define fails 0)
(define chk (lambda (name got want)
  (if (= got want)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

(define req50 (lambda () {
    (var pl (bufcreate 5))
    (bufset-u8 pl 0 50)
    (bufset-u8 pl 1 0) (bufset-u8 pl 2 0) (bufset-u8 pl 3 3) (bufset-u8 pl 4 255)
    (mkframe pl)
}))

; One prebuilt request, reused: wire-put copies the bytes, so rebuilding it per
; frame would only measure the harness allocating.
(define REQ (req50))

(define reset-counters (lambda () {
    (setq dbg-in 0) (setq dbg-bad 0) (setq dbg-sync 0) (setq dbg-proc 0)
}))

; ---- candidates -------------------------------------------------------------

; A: shipped today - header, then payload, then crc+stop. Three reads a frame.
(define frame-a (lambda () {
    (var n (bufget-u8 rx 1))
    (if (and (> n 0) (< n 100)
             (= (rdn rx n 2) n)
             (= (rdn rx 3 (+ n 2)) 3))
        (handle n)
        { (setq dbg-bad (+ dbg-bad 1)) nil })
}))
(define pump-a (lambda () {
    (var k (uart-read rx 2 0 nil 0.1))
    (cond ((and (= k 2) (= (bufget-u8 rx 0) 2)) (frame-a))
          ((and (= k 1) (= (bufget-u8 rx 0) 2))
           (if (= (rdn rx 1 1) 1) (frame-a) { (setq dbg-bad (+ dbg-bad 1)) nil }))
          ((and (= k 2) (= (bufget-u8 rx 1) 2))
           { (bufset-u8 rx 0 2)
             (if (= (rdn rx 1 1) 1) (frame-a) { (setq dbg-bad (+ dbg-bad 1)) nil }) })
          (t { (setq dbg-sync (+ dbg-sync 1)) nil }))
}))

; B: the rest of the frame is one read. The length byte already says how much
; is coming, so payload and crc+stop need not be fetched separately.
(define frame-b (lambda () {
    (var n (bufget-u8 rx 1))
    (if (and (> n 0) (< n 100)
             (= (rdn rx (+ n 3) 2) (+ n 3)))
        (handle n)
        { (setq dbg-bad (+ dbg-bad 1)) nil })
}))
(define pump-b (lambda () {
    (var k (uart-read rx 2 0 nil 0.1))
    (cond ((and (= k 2) (= (bufget-u8 rx 0) 2)) (frame-b))
          ((and (= k 1) (= (bufget-u8 rx 0) 2))
           (if (= (rdn rx 1 1) 1) (frame-b) { (setq dbg-bad (+ dbg-bad 1)) nil }))
          ((and (= k 2) (= (bufget-u8 rx 1) 2))
           { (bufset-u8 rx 0 2)
             (if (= (rdn rx 1 1) 1) (frame-b) { (setq dbg-bad (+ dbg-bad 1)) nil }) })
          (t { (setq dbg-sync (+ dbg-sync 1)) nil }))
}))

; C: as B, but rdn only enters its loop when the first read came up short.
(define rdn-fast (lambda (b n off) {
    (var got (uart-read b n off nil 0.05))
    (if (= got n) got {
        (var live t)
        (loopwhile (and live (< got n)) {
            (var k (uart-read b (- n got) (+ off got) nil 0.05))
            (if (= k 0) (setq live nil) (setq got (+ got k)))
        })
        got })
}))
(define frame-c (lambda () {
    (var n (bufget-u8 rx 1))
    (if (and (> n 0) (< n 100)
             (= (rdn-fast rx (+ n 3) 2) (+ n 3)))
        (handle n)
        { (setq dbg-bad (+ dbg-bad 1)) nil })
}))
(define pump-c (lambda () {
    (var k (uart-read rx 2 0 nil 0.1))
    (cond ((and (= k 2) (= (bufget-u8 rx 0) 2)) (frame-c))
          ((and (= k 1) (= (bufget-u8 rx 0) 2))
           (if (= (rdn-fast rx 1 1) 1) (frame-c) { (setq dbg-bad (+ dbg-bad 1)) nil }))
          ((and (= k 2) (= (bufget-u8 rx 1) 2))
           { (bufset-u8 rx 0 2)
             (if (= (rdn-fast rx 1 1) 1) (frame-c) { (setq dbg-bad (+ dbg-bad 1)) nil }) })
          (t { (setq dbg-sync (+ dbg-sync 1)) nil }))
}))

; ---- bench ------------------------------------------------------------------

(define run-bench (lambda (name pump n-frames) {
    (wire-reset) (reset-counters)
    (looprange i 0 n-frames (wire-put REQ))
    (looprange i 0 60 (pump))
    (print (str-merge "  " name
                      "  frames=" (str-from-n dbg-in)
                      " replies=" (str-from-n replies)
                      " uart-reads=" (str-from-n reads)
                      " bad=" (str-from-n dbg-bad)))
    reads
}))

(print "== cost per frame over a clean 20-frame stream")
(define ra (run-bench "A three reads " pump-a 20))
(define rb (run-bench "B two reads   " pump-b 20))
(define rc (run-bench "C two + fast  " pump-c 20))

; Every candidate must still deliver all 20 frames - a cheaper reader that
; drops frames is not cheaper, it is broken.
(chk "A handles 20" dbg-in 20)
(wire-reset) (reset-counters)
(looprange i 0 20 (wire-put REQ)) (looprange i 0 60 (pump-b))
(chk "B handles 20" dbg-in 20)
(chk "B replies 20" replies 20)
(wire-reset) (reset-counters)
(looprange i 0 20 (wire-put REQ)) (looprange i 0 60 (pump-c))
(chk "C handles 20" dbg-in 20)
(chk "C replies 20" replies 20)

(chk "B costs less than A" (if (< rb ra) 1 0) 1)
(chk "C costs no more than B" (if (<= rc rb) 1 0) 1)

(print "== the cheap candidates must still survive a split header")
(wire-reset) (reset-counters)
(looprange i 0 10 (wire-put REQ))
(cap 1)
(looprange i 0 60 (pump-c))
(chk "C survives a 1-byte first read" dbg-in 10)
(chk "C answers all 10"               replies 10)

(wire-reset) (reset-counters)
(looprange i 0 10 (wire-put REQ))
(cap 1) (cap 3) (cap 1) (cap 2)
(looprange i 0 60 (pump-c))
(chk "C survives repeated chunking"   dbg-in 10)
(chk "C answers all 10 again"         replies 10)

(wire-reset) (reset-counters)
{ (bufset-u8 wire 0 99) (setq wire-len 1) }
(looprange i 0 5 (wire-put REQ))
(looprange i 0 60 (pump-c))
(chk "C realigns after a stray byte"  dbg-in 5)

; summary MUST be last
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
