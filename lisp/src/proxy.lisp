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
