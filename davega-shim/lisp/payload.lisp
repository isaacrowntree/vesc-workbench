; Pure payload/framing. Shared by davega_shim.lisp and tests/lisp.
; Golfed deliberately: every byte saved is fewer 384-byte upload chunks.
;   - builtins aliased to 1 char (they are ordinary values in the environment)
;   - strings ARE byte arrays, so "UNITY\0" goes in with one bufcpy
;   - (crc16 arr optLen) has NO start offset, so payload lives in its own buffer
; Frame on the wire: [2][len][payload][crc-hi][crc-lo][3]
; DAVEga indexes the whole frame, so its offsets = payload offset + 2.

(def u bufset-u8)

; get-tacho/get-tacho-abs are NOT VESC extensions - only get-dist/get-dist-abs
; exist. The GET_VALUES tachometer fields are motor steps, so invert the
; firmware's metres conversion: dist = tacho * (wheel*pi)/(3*poles*gear).
(def tscale (/ (* (conf-get 'si-wheel-diameter) 3.141593)
               (* 3.0 (conf-get 'si-motor-poles) (conf-get 'si-gear-ratio))))

(def p (bufcreate 96))   ; payload
(def o (bufcreate 104))  ; framed output

; NOTE: (uart-write arr) writes the WHOLE array - there is no length arg - so
; the output buffer must be resized to exactly the frame length first.
(defun sf (n) {
    (buf-resize o nil (+ 5 n))
    (var c (crc16 p n))
    (u o 0 2) (u o 1 n)
    (bufcpy o 2 p 0 n)
    (u o (+ 2 n) (shr c 8))
    (u o (+ 3 n) (bitwise-and c 255))
    (u o (+ 4 n) 3)
    (uart-write o)
})

; COMM_FW_VERSION -> claim 6.00
(defun reply-fw-version () {
    (bufclear p)
    (u p 1 6)
    (bufcpy p 3 "UNITY" 0 6)
    (sf 27)
})

; scaled writers. NOTE: LispBM symbols are CASE-INSENSITIVE, so these
; must not collide with the w/l aliases above.
(defun g (b x s) (bufset-i16 p b (to-i (* x s))))
(defun h (b x s) (bufset-i32 p b (to-i (* x s))))

; COMM_GET_VALUES -> rebuild the standard payload from live values
(defun reply-get-values () {
    (bufclear p)
    (u p 0 4)
    (g 1  (get-temp-fet) 10)
    (g 3  (get-temp-mot) 10)
    (h 5  (get-current) 100)
    (h 9  (get-current-in) 100)
    (g 21 (get-duty) 1000)
    (h 23 (get-rpm) 1)
    (g 27 (get-vin) 10)
    (h 29 (get-ah) 10000)
    (h 33 (get-ah-chg) 10000)
    (h 37 (get-wh) 10000)
    (h 41 (get-wh-chg) 10000)
    (h 45 (/ (get-dist) tscale) 1)
    (h 49 (/ (get-dist-abs) tscale) 1)
    (u p 53 (get-fault))
    (sf 78)
})

; COMM_GET_VALUES_SETUP_SELECTIVE (51). The request carries a big-endian uint32
; field mask (bldc/comm/commands.c: buffer_get_uint32). We echo it verbatim then
; append ONLY the selected fields, in bit order, exactly as the firmware does.
(def k 0)
(defun aw (x s) { (g k x s) (setq k (+ k 2)) })   ; append float16
(defun al (x s) { (h k x s) (setq k (+ k 4)) })   ; append float32
(defun ab (x)   { (u p k x)  (setq k (+ k 1)) })  ; append u8
(defun bt (m n) (= 1 (bitwise-and 1 (shr m n))))

(defun reply-setup (m0 m1 m2 m3) {
    (bufclear p)
    (u p 0 51)
    (u p 1 m0) (u p 2 m1) (u p 3 m2) (u p 4 m3)
    (var m (+ (shl m0 24) (shl m1 16) (shl m2 8) m3))
    (setq k 5)
    (if (bt m 0)  (aw (get-temp-fet) 10))
    (if (bt m 1)  (aw (get-temp-mot) 10))
    (if (bt m 2)  (al (get-current) 100))
    (if (bt m 3)  (al (get-current-in) 100))
    (if (bt m 4)  (aw (get-duty) 1000))
    (if (bt m 5)  (al (get-rpm) 1))
    (if (bt m 6)  (al (get-speed) 1000))
    (if (bt m 7)  (aw (get-vin) 10))
    (if (bt m 8)  (aw (get-batt) 1000))
    (if (bt m 9)  (al (get-ah) 10000))
    (if (bt m 10) (al (get-ah-chg) 10000))
    (if (bt m 11) (al (get-wh) 10000))
    (if (bt m 12) (al (get-wh-chg) 10000))
    (if (bt m 13) (al (get-dist) 1000))
    (if (bt m 14) (al (get-dist-abs) 1000))
    (if (bt m 15) (al 0 1))
    (if (bt m 16) (ab (get-fault)))
    (if (bt m 17) (ab 123))
    (if (bt m 18) (ab 2))
    (if (bt m 19) (al 0 1))
    (if (bt m 20) (al 0 1))
    (if (bt m 21) (al 0 1))
    (sf k)
})

; COMM_PING_CAN (62) - reply with the CAN ids present. On this Unity the second
; motor thread is controller 124, so the DAVEGA sees a 2-motor setup.
(defun reply-ping () { (bufclear p) (u p 0 62) (u p 1 124) (sf 2) })

; COMM_GET_VALUES_SELECTIVE (50) - live telemetry, same big-endian uint32 mask
; mechanism as 51 but over the COMM_GET_VALUES field list. Bits above 20 do not
; exist and are ignored, exactly as the firmware does.
(defun reply-values-sel (m0 m1 m2 m3) {
    (bufclear p)
    (u p 0 50)
    (u p 1 m0) (u p 2 m1) (u p 3 m2) (u p 4 m3)
    (var m (+ (shl m0 24) (shl m1 16) (shl m2 8) m3))
    (setq k 5)
    (if (bt m 0)  (aw (get-temp-fet) 10))
    (if (bt m 1)  (aw (get-temp-mot) 10))
    (if (bt m 2)  (al (get-current) 100))
    (if (bt m 3)  (al (get-current-in) 100))
    (if (bt m 4)  (al 0 1))                    ; avg id
    (if (bt m 5)  (al 0 1))                    ; avg iq
    (if (bt m 6)  (aw (get-duty) 1000))
    (if (bt m 7)  (al (get-rpm) 1))
    (if (bt m 8)  (aw (get-vin) 10))
    (if (bt m 9)  (al (get-ah) 10000))
    (if (bt m 10) (al (get-ah-chg) 10000))
    (if (bt m 11) (al (get-wh) 10000))
    (if (bt m 12) (al (get-wh-chg) 10000))
    (if (bt m 13) (al (/ (get-dist) tscale) 1))
    (if (bt m 14) (al (/ (get-dist-abs) tscale) 1))
    (if (bt m 15) (ab (get-fault)))
    (if (bt m 16) (al 0 1))                    ; pid pos
    (if (bt m 17) (ab 123))                    ; controller id
    (if (bt m 18) { (aw 0 1) (aw 0 1) (aw 0 1) (aw 0 1) (aw 0 1) (aw 0 1) })
    (if (bt m 19) { (al 0 1) (al 0 1) })
    (if (bt m 20) (ab 0))
    (sf k)
})
