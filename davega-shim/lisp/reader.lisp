; ---- reader -----------------------------------------------------------------
; One UART frame in, one call to the firmware decoder out. Kept free of the
; event/UART setup so tests/lisp/test_reader.lisp can drive `pump` directly
; against a fake UART.
(def rx (bufcreate 128))
(def dbg-in 0)    ; frames read from the DAVEGA
(def dbg-out 0)   ; replies forwarded
(def dbg-fw 0)    ; COMM_FW_VERSION replies patched
(def dbg-ping 0)  ; CAN pings answered locally
(def dbg-blk 0)   ; blocking-thread commands intercepted
(def dbg-proc 0)  ; frames handed to the firmware decoder
(def dbg-bad 0)   ; frames rejected (implausible length, or a short read)
(def dbg-sync 0)  ; bytes skipped while hunting for a frame start
(def dbg-c50 0)   ; GET_VALUES_SELECTIVE  (live telemetry)
(def dbg-c51 0)   ; GET_VALUES_SETUP_SELECTIVE (setup info)
(def dbg-c0 0)    ; FW_VERSION (the version gate)
(def dbg-cx -1)   ; last command id that was none of the above
(def dbg-fwid -1) ; CAN id the DAVEGA targets in COMM_FORWARD_CAN
(def dbg-fwcmd -1); inner command it forwards
(def dbg-fw124 0) ; FORWARD_CAN aimed at the real second motor
(def dbg-fwmax 0) ; highest CAN id probed

; Dispatch one complete frame sitting in rx, payload length n.
(defun handle (n) {
    (var id (bufget-u8 rx 2))
    (setq dbg-in (+ dbg-in 1))
    (cond ((= id 50) (setq dbg-c50 (+ dbg-c50 1)))
          ((= id 51) (setq dbg-c51 (+ dbg-c51 1)))
          ((= id 0)  (setq dbg-c0  (+ dbg-c0 1)))
          ((= id 34) { (var cid (bufget-u8 rx 3))
                       (setq dbg-fwid cid) (setq dbg-fwcmd (bufget-u8 rx 4))
                       (if (> cid dbg-fwmax) (setq dbg-fwmax cid))
                       (if (= cid can-id) (setq dbg-fw124 (+ dbg-fw124 1))) })
          (t (setq dbg-cx id)))
    (if (blocking? id)
        { (setq dbg-blk (+ dbg-blk 1))
          (if (= id 62) { (setq dbg-ping (+ dbg-ping 1)) (reply-ping) }) }
        { (setq dbg-proc (+ dbg-proc 1))
          (var b (bufcreate (+ n 5)))
          (bufcpy b 0 rx 0 (+ n 5))
          (cmds-proc b) })
    t
})

; Read exactly n bytes, tolerating short reads. A UART hands you what has
; arrived, not what you asked for; a partial read means the frame is still
; coming, not that it is corrupt. The common case is one call, so the
; accumulating loop is only entered when that first read comes up short.
; Returns how many bytes were delivered.
(defun rdn (b n off) {
    (var got (uart-read b n off nil 0.05))
    (if (= got n) got {
        (var live t)
        (loopwhile (and live (< got n)) {
            (var k (uart-read b (- n got) (+ off got) nil 0.05))
            (if (= k 0) (setq live nil) (setq got (+ got k)))
        })
        got })
})

; Read the payload and hand off a complete frame sitting in rx.
(defun frame () {
    (var n (bufget-u8 rx 1))
    ; payload plus crc and stop byte in one read - the length byte already
    ; says how much is coming, so splitting it in two costs a UART call per
    ; frame for nothing. tests/lisp/bench_reader.lisp measures the difference.
    (if (and (> n 0) (< n 100)
             (= (rdn rx (+ n 3) 2) (+ n 3)))
        (handle n)
        { (setq dbg-bad (+ dbg-bad 1)) nil })
})

; One iteration of the reader. Returns t if a frame was handled.
;
; Both header bytes are asked for in one read, because that is one UART call
; per frame instead of two and the throughput difference is measurable. The
; cost of that shortcut is that a header straddling the read boundary used to
; leave the length byte to be misread as the next frame's start byte,
; misaligning everything until a gap in traffic resynced it - so both ways it
; can go wrong are handled explicitly rather than dropped:
;
;   got 1 byte, and it starts a frame   -> fetch the length byte and continue
;   got 2 bytes, second one starts one  -> realign onto it and continue
;
; Anything else is genuinely not a frame. At idle that is simply the read
; timing out with the display between polls, which is why dbg-sync is
; expected to be non-zero on a healthy board.
(defun pump () {
    (var k (uart-read rx 2 0 nil 0.1))
    (cond ((and (= k 2) (= (bufget-u8 rx 0) 2)) (frame))
          ((and (= k 1) (= (bufget-u8 rx 0) 2))
           (if (= (rdn rx 1 1) 1) (frame) { (setq dbg-bad (+ dbg-bad 1)) nil }))
          ((and (= k 2) (= (bufget-u8 rx 1) 2))
           { (bufset-u8 rx 0 2)
             (if (= (rdn rx 1 1) 1) (frame) { (setq dbg-bad (+ dbg-bad 1)) nil }) })
          (t { (setq dbg-sync (+ dbg-sync 1)) nil }))
})
