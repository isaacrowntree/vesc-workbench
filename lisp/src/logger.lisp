; ---- flight recorder -------------------------------------------------------
; The ESC keeps faults only "since start". After a ride the counters are gone
; at the next power cycle, which is exactly how the one fault we most wanted
; to look at was lost.
;
; This records what a ride did, in globals - which come back through
; lispGetStats, so nothing has to print and nothing has to survive a reboot to
; be useful. Pull it with `make log-pull` before powering down.
;
; Costs one pass over a handful of getters per tick, and it does not grow.
; Every slot is a global scalar updated in place - no lists, no buffers,
; nothing appended. LispBM boxes floats, so a tick does allocate and then
; drop a handful of them, but that is churn the collector handles: measured
; in the real interpreter, the heap is identical after 500 ticks and after
; 25,000 (`lisp/tests/test_logger.lisp`).
;
; It only ever *reads* the ESC. There is no set-current, no config write, and
; deliberately no uart-start - that call permanently flashes
; app_to_use = APP_NONE and takes the throttle with it.

(def log-rate 0.2)          ; seconds between samples

; --- high-water marks, the session summary
(def hi-motor 0.0)          ; peak motor current, A
(def lo-motor 0.0)          ; peak regen, A (negative)
(def hi-batt 0.0)           ; peak pack draw, A
(def lo-batt 0.0)           ; peak pack charge, A
(def hi-fet 0.0)            ; peak FET temperature, C
(def hi-mot 0.0)            ; peak motor temperature, C
(def lo-vin 200.0)          ; minimum pack voltage seen under load
(def hi-erpm 0.0)           ; peak ERPM
(def hi-duty 0.0)           ; peak duty

; --- fault capture: the first fault, with the context that explains it
(def flt-code 0)
(def flt-vin 0.0)
(def flt-erpm 0.0)
(def flt-duty 0.0)
(def flt-motor 0.0)
(def flt-count 0)

; --- traction control: nothing on the ESC reports whether it ever engaged
(def tc-events 0)           ; times wheel-speed difference exceeded the limit
(def tc-worst 0.0)          ; largest difference seen, ERPM
(def tc-max-diff 6000.0)    ; mirrors app_ppm_conf.tc_max_diff

(def samples 0)
(def uptime 0.0)          ; seconds, derived from samples - see log-tick

(defun hiwater () {
    (var im (get-current))
    (var ib (get-current-in))
    (var tf (get-temp-fet))
    (var tm (get-temp-mot))
    (var v (get-vin))
    (var r (get-rpm))
    (var d (get-duty))
    (if (> im hi-motor) (setq hi-motor im))
    (if (< im lo-motor) (setq lo-motor im))
    (if (> ib hi-batt) (setq hi-batt ib))
    (if (< ib lo-batt) (setq lo-batt ib))
    (if (> tf hi-fet) (setq hi-fet tf))
    (if (> tm hi-mot) (setq hi-mot tm))
    ; only count sag while actually pulling current, or a resting pack
    ; looks like a dying one
    (if (and (> ib 1.0) (< v lo-vin)) (setq lo-vin v))
    (if (> r hi-erpm) (setq hi-erpm r))
    (if (> d hi-duty) (setq hi-duty d))
})

(defun catch-fault () {
    (var f (get-fault))
    (if (not (= f 0)) {
        (setq flt-count (+ flt-count 1))
        ; keep the FIRST fault: what started it explains more than what
        ; followed, and later faults are usually consequences
        (if (= flt-code 0) {
            (setq flt-code f)
            (setq flt-vin (get-vin))
            (setq flt-erpm (get-rpm))
            (setq flt-duty (get-duty))
            (setq flt-motor (get-current))
        })
    })
})

; Wheel-speed difference across the two motors. On a dual-motor ESC the second
; side is a CAN device; when it cannot be read this reports 0 rather than
; guessing, so a zero here means "not measured", not "no slip".
(defun tc-watch () {
    (var a (get-rpm))
    (var b (canget-rpm 124))
    (if (eq b nil) 0 {
        (var diff (abs (- a b)))
        (if (> diff tc-worst) (setq tc-worst diff))
        (if (> diff tc-max-diff) (setq tc-events (+ tc-events 1)))
        diff
    })
})

(defun log-reset () {
    (setq hi-motor 0.0) (setq lo-motor 0.0)
    (setq hi-batt 0.0) (setq lo-batt 0.0)
    (setq hi-fet 0.0) (setq hi-mot 0.0)
    (setq lo-vin 200.0) (setq hi-erpm 0.0) (setq hi-duty 0.0)
    (setq flt-code 0) (setq flt-count 0)
    (setq tc-events 0) (setq tc-worst 0.0)
    (setq samples 0) (setq uptime 0.0)
})

(defun log-tick () {
    (hiwater)
    (catch-fault)
    (tc-watch)
    (setq samples (+ samples 1))
    ; Derived, not accumulated. Adding 0.2 to a float thirty thousand times
    ; drifts: 25,000 ticks came out as 5000.18 s instead of 5000.0, and it
    ; gets worse the longer the ride. Multiplying an exact integer does not.
    (setq uptime (* samples log-rate))
})
