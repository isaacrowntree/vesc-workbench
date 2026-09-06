
; ---- runner ----------------------------------------------------------------
; Standalone: this does NOT touch the UART, so it can run on a board whose
; display is being driven by something else - or on one with no display at all.
(log-reset)
(loopwhile t {
    (log-tick)
    (sleep log-rate)
})
