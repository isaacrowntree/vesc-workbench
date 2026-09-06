; Tests for the pass-through proxy: only a COMM_FW_VERSION reply is rewritten,
; everything else must pass through byte-identical.
(define fails 0)
(define chk (lambda (name got want)
  (if (= got want)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

; build a framed packet: [2][len][payload][crc-hi][crc-lo][3]
(define mkframe (lambda (payload) {
    (var n (buflen payload))
    (var f (bufcreate (+ n 5)))
    (bufset-u8 f 0 2) (bufset-u8 f 1 n)
    (bufcpy f 2 payload 0 n)
    (var c (crc16 payload n))
    (bufset-u8 f (+ 2 n) (shr c 8))
    (bufset-u8 f (+ 3 n) (bitwise-and c 255))
    (bufset-u8 f (+ 4 n) 3)
    f
}))

(define crc-of-frame (lambda (f) {
    (var n (bufget-u8 f 1))
    (var q (bufcreate n))
    (bufcpy q 0 f 2 n)
    (crc16 q n)
}))
(define frame-crc-field (lambda (f) {
    (var n (bufget-u8 f 1))
    (+ (shl (bufget-u8 f (+ 2 n)) 8) (bufget-u8 f (+ 3 n)))
}))

(print "== COMM_FW_VERSION reply is rewritten to 6.00")
(define fw (bufcreate 20))
(bufset-u8 fw 0 0)    ; COMM_FW_VERSION
(bufset-u8 fw 1 7)    ; major
(bufset-u8 fw 2 1)    ; minor
(bufset-u8 fw 3 85)   ; "U" - hw name start
(define fwf (mkframe fw))
(fixfw fwf)
(chk "major 7 -> 6"          (bufget-u8 fwf 3) 6)
(chk "minor 1 -> 0"          (bufget-u8 fwf 4) 0)
(chk "hw name untouched"     (bufget-u8 fwf 5) 85)
(chk "packet id untouched"   (bufget-u8 fwf 2) 0)
(chk "crc recomputed to match payload" (frame-crc-field fwf) (crc-of-frame fwf))

(print "== every other reply passes through untouched")
(define gv (bufcreate 12))
(bufset-u8 gv 0 4)    ; COMM_GET_VALUES
(bufset-u8 gv 1 99)
(bufset-u8 gv 2 88)
(define gvf (mkframe gv))
(define before-crc (frame-crc-field gvf))
(fixfw gvf)
(chk "id untouched"          (bufget-u8 gvf 2) 4)
(chk "byte 1 untouched"      (bufget-u8 gvf 3) 99)
(chk "byte 2 untouched"      (bufget-u8 gvf 4) 88)
(chk "crc untouched"         (frame-crc-field gvf) before-crc)


(print "== constant COMM_PING_CAN reply frame")
(chk "start byte"     (bufget-u8 pg 0) 2)
(chk "payload len 2"  (bufget-u8 pg 1) 2)
(chk "id 62"          (bufget-u8 pg 2) 62)
(chk "can id 124"     (bufget-u8 pg 3) 124)
(chk "stop byte"      (bufget-u8 pg 6) 3)
(chk "crc valid"      (+ (shl (bufget-u8 pg 4) 8) (bufget-u8 pg 5)) (crc-of-frame pg))


(print "== blocking-thread command classification")
(chk "62  PING_CAN is blocking"        (if (blocking? 62) 1 0) 1)
(chk "66  BM_CONNECT is blocking"      (if (blocking? 66) 1 0) 1)
(chk "90  IMU_CALIBRATION is blocking" (if (blocking? 90) 1 0) 1)
(chk "158 CAN_UPDATE_BAUD is blocking" (if (blocking? 158) 1 0) 1)
(chk "0   FW_VERSION is NOT blocking"  (if (blocking? 0) 1 0) 0)
(chk "4   GET_VALUES is NOT blocking"  (if (blocking? 4) 1 0) 0)
(chk "50  SELECTIVE is NOT blocking"   (if (blocking? 50) 1 0) 0)
(chk "51  SETUP_SEL is NOT blocking"   (if (blocking? 51) 1 0) 0)

; summary MUST be last
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
