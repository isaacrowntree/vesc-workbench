; ---- integration harness ----------------------------------------------------
; A fake UART in front of the real reader. The point is CHUNKING: a real UART
; hands you whatever bytes have arrived, which is not necessarily the number
; you asked for. `wire` is the byte stream the DAVEGA is sending; `avail` is
; how many of those bytes uart-read is allowed to return on the next call.
;
; Setting avail to 1 exactly once, at a frame boundary, reproduces the split
; header that used to desync the reader for every frame after it.

(def wire (bufcreate 512))   ; bytes the DAVEGA has sent
(def wire-len 0)             ; how many are valid
(def wire-pos 0)             ; how many the reader has consumed
(def caps nil)               ; queue of per-call read caps; nil = no cap
(def replies 0)              ; frames the firmware decoder was asked to answer
(def reads 0)                ; uart-read calls - the cost we are trying to cut
(def bufs 0)                 ; buffers allocated in the frame path
(def last-proc (bufcreate 128))

(defun wire-reset () {
    (setq wire-len 0) (setq wire-pos 0) (setq caps nil) (setq replies 0)
    (setq reads 0) (setq bufs 0)
})

; Append a framed packet to the stream.
(defun wire-put (f) {
    (var n (buflen f))
    (bufcpy wire wire-len f 0 n)
    (setq wire-len (+ wire-len n))
})

; The next read returns at most n bytes, once. Queue as many as you like.
(defun cap (n) (setq caps (append caps (list n))))

(defun take-cap () (if (eq caps nil) nil { (var c (car caps)) (setq caps (cdr caps)) c }))

; Stand-in for the VESC uart-read: (uart-read buf n offset stop timeout).
; Returns how many bytes it actually delivered, like the real one does.
(defun uart-read (b n off stop tmo) {
    (setq reads (+ reads 1))
    (var want n)
    (var c (take-cap))
    (if (not (eq c nil)) (if (< c want) (setq want c)))
    (var have (- wire-len wire-pos))
    (if (< have want) (setq want have))
    (if (> want 0) {
        (bufcpy b off wire wire-pos want)
        (setq wire-pos (+ wire-pos want))
    })
    want
})

; The firmware decoder: record that a reply was owed, and for whom.
(defun cmds-proc (b) {
    (setq replies (+ replies 1))
    (setq bufs (+ bufs 1))
    (bufcpy last-proc 0 b 0 (buflen b))
    t
})

(defun reply-ping () (setq replies (+ replies 1)))

; Drive the reader until the wire is drained (bounded, so a bug can't hang CI).
(defun drain () (looprange i 0 200 (pump)))
