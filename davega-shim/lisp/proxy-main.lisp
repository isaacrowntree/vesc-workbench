; ---- plumbing ---------------------------------------------------------------
; UART bytes -> firmware packet decoder; replies come back framed on
; event-cmds-data-tx, get patched, and go out the UART.
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

(loopwhile t (pump))
