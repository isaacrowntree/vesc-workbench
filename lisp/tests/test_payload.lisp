; Byte-layout assertions for the DAVEGA payload, run in real LispBM.
; Offsets are frame-relative and must match DAVEga's vesc_comm_standard.cpp.

(define fails 0)

(define chk (lambda (name got want)
  (if (= got want)
      (print (str-merge "  PASS  " name))
      { (setq fails (+ fails 1))
        (print (str-merge "  FAIL  " name " got=" (str-from-n got) " want=" (str-from-n want))) })))

(reply-get-values)

(print "== packet id")
(chk "id byte @2 = COMM_GET_VALUES" (bufget-u8 o 2) 4)

(print "== fields at DAVEga's offsets")
(chk "temp_fet @3      (25.0 * 10)"    (bufget-i16 o 3)  250)
(chk "temp_motor @5    (30.0 * 10)"    (bufget-i16 o 5)  300)
(chk "motor_current @7 (12.34 * 100)"  (bufget-i32 o 7)  1234)
(chk "batt_current @11 (5.67 * 100)"   (bufget-i32 o 11) 567)
(chk "duty @23         (0.5 * 1000)"   (bufget-i16 o 23) 500)
(chk "rpm @25"                         (bufget-i32 o 25) 12345)
(chk "voltage @29      (50.4 * 10)"    (bufget-i16 o 29) 504)
(chk "amp_hours @31    (1.5 * 10000)"  (bufget-i32 o 31) 15000)
(chk "ah_charged @35   (0.25 * 10000)" (bufget-i32 o 35) 2500)
; tacho = dist * (3*poles*gear) / (wheel*pi) = 1234.5 * 176.4 / 0.62832
(chk "tachometer @47 (from get-dist)"  (bufget-i32 o 47) 346584)
(chk "tacho_abs @51 (from get-dist-abs)" (bufget-i32 o 51) 693169)
(chk "fault @55"                       (bufget-u8  o 55) 0)

(print "== unused fields are zeroed, not garbage")
(chk "avg_id @15 zero"  (bufget-i32 o 15) 0)
(chk "avg_iq @19 zero"  (bufget-i32 o 19) 0)
(chk "batt_current spans 11-14" (bufget-i32 o 11) 567)

(print "== framing")
(reply-fw-version)
(chk "frame start byte" (bufget-u8 o 0) 2)
(chk "fw major spoofed" (bufget-u8 o 3) 6)
(chk "fw minor spoofed" (bufget-u8 o 4) 0)



(print "== COMM_GET_VALUES_SETUP_SELECTIVE (51)")
; the mask the DAVEGA actually sends: 245 3 0 0 -> 0xF5030000 big-endian,
; whose only valid bits are 16 (fault) and 17 (controller id)
(reply-setup 245 3 0 0)
(chk "id @2 = 51"           (bufget-u8 o 2) 51)
(chk "mask echoed b0"       (bufget-u8 o 3) 245)
(chk "mask echoed b1"       (bufget-u8 o 4) 3)
(chk "fault (bit16) @7"     (bufget-u8 o 7) 0)
(chk "ctrl id (bit17) @8"   (bufget-u8 o 8) 123)
(chk "frame length = 7"     (bufget-u8 o 1) 7)

(print "== mask decoding is big-endian and bit-ordered")
; 0x000003F5 -> bits 0,2,4,5,6,7,8,9
(reply-setup 0 0 3 245)
; fields pack sequentially from payload offset 5; frame offset = payload + 2
(chk "temp_fet  frame @7"   (bufget-i16 o 7)  250)
(chk "current   frame @9"   (bufget-i32 o 9)  1234)
(chk "duty      frame @13"  (bufget-i16 o 13) 500)
(chk "rpm       frame @15"  (bufget-i32 o 15) 12345)
(chk "speed     frame @19"  (bufget-i32 o 19) 8500)
(chk "voltage   frame @23"  (bufget-i16 o 23) 504)
(chk "batt lvl  frame @25"  (bufget-i16 o 25) 750)
(chk "amp hours frame @27"  (bufget-i32 o 27) 15000)
(chk "frame length = 29"    (bufget-u8 o 1)   29)

(print "== COMM_PING_CAN (62) - CAN device discovery")
(reply-ping)
(chk "id @2 = 62"            (bufget-u8 o 2) 62)
(chk "reports CAN id 124 @3" (bufget-u8 o 3) 124)
(chk "frame length = 2"      (bufget-u8 o 1) 2)


(print "== COMM_GET_VALUES_SELECTIVE (50) - live telemetry")
; observed mask 107 3 223 207 = 0x6B03DFCF big-endian
; valid bits: 0,1,2,3,6,7,8,9,10,11,12,14,15,16,17
(reply-values-sel 107 3 223 207)
(chk "id @2 = 50"          (bufget-u8  o 2)  50)
(chk "mask echoed"         (bufget-u8  o 3)  107)
(chk "temp_fet  @7"        (bufget-i16 o 7)  250)
(chk "temp_mot  @9"        (bufget-i16 o 9)  300)
(chk "current   @11"       (bufget-i32 o 11) 1234)
(chk "curr_in   @15"       (bufget-i32 o 15) 567)
(chk "duty      @19"       (bufget-i16 o 19) 500)
(chk "rpm       @21"       (bufget-i32 o 21) 12345)
(chk "vin       @25"       (bufget-i16 o 25) 504)
(chk "amp_hours @27"       (bufget-i32 o 27) 15000)
(chk "ah_chg    @31"       (bufget-i32 o 31) 2500)
(chk "fault     @47"       (bufget-u8  o 47) 0)
(chk "ctrl_id   @52"       (bufget-u8  o 52) 123)
(chk "frame len = 51"      (bufget-u8  o 1)  51)

; summary MUST be last - anything after it is invisible to the runner
(if (= fails 0)
    (print "all lisp tests passed")
    (print (str-merge (str-from-n fails) " LISP TESTS FAILED")))
