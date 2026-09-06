
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
(uart-start 115200)

; Frame-aligned read. Hunt for the start byte ONE byte at a time: asking for
; two at once means a header that straddles the read boundary swallows the
; length byte, and every frame after it is misaligned until a gap in traffic
; resyncs us. Each miss is a whole request/reply round trip the DAVEGA never
; gets, which shows up as a speed readout that updates in lurches.
;
; Short reads are dropped rather than forwarded: a truncated frame fails CRC
; downstream anyway, and feeding it to cmds-proc costs a reply slot.
(loopwhile t {
    (if (and (= (uart-read rx 1 0 nil 0.1) 1)
             (= (bufget-u8 rx 0) 2)
             (= (uart-read rx 1 1 nil 0.05) 1)) {
        (var n (bufget-u8 rx 1))
        (if (and (> n 0) (< n 100)
                 (= (uart-read rx n 2 nil 0.05) n)          ; payload
                 (= (uart-read rx 3 (+ n 2) nil 0.05) 3)) { ; crc + stop
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
        } (setq dbg-bad (+ dbg-bad 1)))
    } (setq dbg-sync (+ dbg-sync 1)))
})
