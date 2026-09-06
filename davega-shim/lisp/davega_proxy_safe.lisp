; Pass-through proxy core. Testable without the UART/event plumbing.
;
; The firmware's own packet decoder handles every command (cmds-proc), and the
; reply comes back framed on event-cmds-data-tx. We rewrite ONE thing: the two
; version bytes in a COMM_FW_VERSION reply, so the DAVEGA sees 6.00 and stops
; refusing to talk. The CRC is recomputed over the patched payload.
;
; Frame: [2][len][payload][crc-hi][crc-lo][3]   (short form, len <= 255)

(def p (bufcreate 128))   ; scratch for CRC (crc16 always starts at index 0)

(defun fixfw (d) {
    (var n (bufget-u8 d 1))
    (if (and (= (bufget-u8 d 0) 2) (= (bufget-u8 d 2) 0)) {
        (bufset-u8 d 3 6)               ; FW_VERSION_MAJOR -> 6
        (bufset-u8 d 4 0)               ; FW_VERSION_MINOR -> 0
        (bufcpy p 0 d 2 n)
        (var c (crc16 p n))
        (bufset-u8 d (+ 2 n) (shr c 8))
        (bufset-u8 d (+ 3 n) (bitwise-and c 255))
    })
    d
})

; COMM_PING_CAN (62) is a *blocking-thread* command in the firmware: it replies
; via send_func_blocking, NOT event-cmds-data-tx, so forwarding it yields no
; response - and it walks all 255 CAN ids, which is slow enough to time the
; display out. So we answer it ourselves.
;
; can-id is the second motor thread's controller id. @@CANID@@ is substituted at
; build time from the Makefile / board profile; the literal fallback keeps this
; file runnable and testable on its own.
(def can-id @@CANID@@)

(def pg (bufcreate 7))
(defun mk-ping () {
    (bufset-u8 p 0 62) (bufset-u8 p 1 can-id)
    (var c (crc16 p 2))
    (bufset-u8 pg 0 2) (bufset-u8 pg 1 2)
    (bufset-u8 pg 2 62) (bufset-u8 pg 3 can-id)
    (bufset-u8 pg 4 (shr c 8)) (bufset-u8 pg 5 (bitwise-and c 255))
    (bufset-u8 pg 6 3)
})
(mk-ping)
(defun reply-ping () (uart-write pg))

; Commands the firmware defers to its blocking thread. Their replies go out via
; send_func_blocking, NOT event-cmds-data-tx, so forwarding them to cmds-proc
; produces no response AND leaves is_blocking set, which can wedge later ones.
; We never forward these. 62 (PING_CAN) we answer ourselves; the rest are
; bootloader/memory/IMU-calibration commands a display never sends.
(def blocking-cmds '(62 66 67 68 69 70 71 72 80 83 90 116 125 158))

; (member elem list) - element first, returns the tail or nil
(defun blocking? (d) (if (member d blocking-cmds) t nil))

; ---- plumbing ---------------------------------------------------------------
; UART bytes -> firmware packet decoder; replies come back framed on
; event-cmds-data-tx, get patched, and go out the UART.
(def rx (bufcreate 128))
(def dbg-in 0)    ; bytes read from the DAVEGA
(def dbg-out 0)   ; replies forwarded
(def dbg-fw 0)    ; COMM_FW_VERSION replies patched
(def dbg-ping 0)  ; CAN pings answered locally
(def dbg-blk 0)   ; blocking-thread commands intercepted
(def dbg-proc 0)  ; frames handed to the firmware decoder
(def dbg-bad 0)   ; frames rejected (bad start byte or implausible length)
(def dbg-c50 0)   ; GET_VALUES_SELECTIVE  (live telemetry)
(def dbg-c51 0)   ; GET_VALUES_SETUP_SELECTIVE (setup info)
(def dbg-c0 0)    ; FW_VERSION (the version gate)
(def dbg-cx -1)   ; last command id that was none of the above
(def dbg-fwid -1) ; CAN id the DAVEGA targets in COMM_FORWARD_CAN
(def dbg-fwcmd -1); inner command it forwards
(def dbg-fw124 0) ; FORWARD_CAN aimed at the real second motor
(def dbg-fwmax 0) ; highest CAN id probed

(defun eh () {
    (set-mailbox-size 3)
    (loopwhile t
        (recv ((event-cmds-data-tx (? d)) {
                  (setq dbg-out (+ dbg-out 1))
                  (if (and (= (bufget-u8 d 0) 2) (= (bufget-u8 d 2) 0))
                      (setq dbg-fw (+ dbg-fw 1)))
                  (uart-write (fixfw d))
              })
              (_ nil)))
})

(event-register-handler (spawn eh))
(event-enable 'event-cmds-data-tx)
(cmds-start-stop true)
(app-disable-output -1)
(uart-start 115200)

; Frame-aligned read: header [2][len], then payload, then crc+stop. Reading
; arbitrary chunks means rx[0] is rarely the start byte, so command inspection
; never fires - cmds-proc tolerates that, our interception does not.
(loopwhile t {
    (if (and (= (uart-read rx 2 0 nil 0.1) 2) (= (bufget-u8 rx 0) 2)) {
        (var n (bufget-u8 rx 1))
        (if (not (and (> n 0) (< n 100))) (setq dbg-bad (+ dbg-bad 1)))
        (if (and (> n 0) (< n 100)) {
            (uart-read rx n 2 nil 0.05)          ; payload
            (uart-read rx 3 (+ n 2) nil 0.05)    ; crc + stop
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
        })
    })
})
