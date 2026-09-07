; Stand-ins for the VESC extensions the REPL doesn't have, with known values
; so the assertions below can check exact bytes.
(define get-temp-fet   (lambda () 25.0))
(define get-temp-mot   (lambda () 30.0))
(define get-current    (lambda () 12.34))
(define get-current-in (lambda () 5.67))
(define get-duty       (lambda () 0.5))
(define get-rpm        (lambda () 12345.0))
(define get-vin        (lambda () 50.4))
(define get-ah         (lambda () 1.5))
(define get-ah-chg     (lambda () 0.25))
(define get-wh         (lambda () 60.0))
(define get-wh-chg     (lambda () 10.0))
(define get-fault      (lambda () 0))
(define uart-write     (lambda (b) nil))
(define uart-start     (lambda (b) nil))

; VESC extensions the upstream REPL lacks.
; crc16 is implemented for real (CCITT poly 0x1021, init 0) so the framing
; bytes get checked too, not just the payload offsets.
(define crc16 (lambda (arr len)
  (let ((c 0))
    (progn
      (looprange i 0 len
        (progn
          (setq c (bitwise-xor c (shl (bufget-u8 arr i) 8)))
          (looprange b 0 8
            (if (= (bitwise-and c 32768) 0)
                (setq c (bitwise-and (shl c 1) 65535))
                (setq c (bitwise-and (bitwise-xor (shl c 1) 4129) 65535))))))
      c))))

; to-i is built into LispBM - do not redefine

; buf-resize is a VESC extension (6.05+), absent from the upstream REPL.
; The test buffer is already large enough, so a no-op returning the array is fine.
(define buf-resize (lambda (a d s) a))
(define get-speed (lambda () 8.5))
(define get-batt  (lambda () 0.75))
(define get-dist (lambda () 1234.5))
(define get-dist-abs (lambda () 2469.0))
(define conf-get (lambda (k) (if (eq k 'si-wheel-diameter) 0.2 (if (eq k 'si-motor-poles) 14 4.2))))
