
; ---- UART loop --------------------------------------------------------------
; DAVEGA request frames are [2][len][payload][crc][crc][3]. Only two commands
; matter: 0 = COMM_FW_VERSION (the version gate), 4 = COMM_GET_VALUES.
(def r (bufcreate 16))
(def dbg-rx 0)      ; frames seen
(def dbg-cmd -1)    ; last command id
(def dbg-len 0)     ; payload length of last frame
(def dbg-m0 0) (def dbg-m1 0) (def dbg-m2 0) (def dbg-m3 0) (def dbg-m4 0)  ; payload bytes 1..5
(def dbg-started 0) ; 1 once uart-start returned
(def dbg-got 0)     ; bytes actually returned by the payload read
(def dbg-h0 0) (def dbg-h1 0)  ; the 2 header bytes
(uart-start 115200)
(setq dbg-started 1)
(loopwhile t
    (if (and (= (uart-read r 2 0 nil 0.1) 2) (= (bufget-u8 r 0) 2))
        (let ((n (bufget-u8 r 1)))
          (if (and (> n 0) (< n 8)) {
              (setq dbg-h0 2) (setq dbg-h1 n)
              (setq dbg-got (uart-read r n 0 nil 0.05))
              (var d (bufget-u8 r 0))
              (uart-read r 3 n nil 0.05)
              (setq dbg-rx (+ dbg-rx 1))
              (setq dbg-cmd d)
              (setq dbg-len n)
              (if (> n 4) {
                  (setq dbg-m0 (bufget-u8 r 1)) (setq dbg-m1 (bufget-u8 r 2))
                  (setq dbg-m2 (bufget-u8 r 3)) (setq dbg-m3 (bufget-u8 r 4))
                  (setq dbg-m4 (bufget-u8 r 5)) })
              (cond ((= d 4)  (reply-get-values))
                    ((= d 0)  (reply-fw-version))
                    ((= d 62) (reply-ping))
                    ((= d 51) (reply-setup (bufget-u8 r 1) (bufget-u8 r 2) (bufget-u8 r 3) (bufget-u8 r 4)))
                    ((= d 50) (reply-values-sel (bufget-u8 r 1) (bufget-u8 r 2) (bufget-u8 r 3) (bufget-u8 r 4)))
                    (t nil))
          }))))
