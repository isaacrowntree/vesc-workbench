; Write the measured Hoyt Puck calibration and persist it.
; Measured over a full sweep: brake 1.1850 / neutral 1.5010 / throttle 1.9660 ms
; Endpoints pulled in ~5us so full travel is reliably reachable despite jitter.
(def b0 (conf-get 'ppm-pulse-start))
(def c0 (conf-get 'ppm-pulse-center))
(def e0 (conf-get 'ppm-pulse-end))
(def h0 (conf-get 'ppm-hyst))

(conf-set 'ppm-pulse-start  1.19)
(conf-set 'ppm-pulse-center 1.501)
(conf-set 'ppm-pulse-end    1.96)
(conf-set 'ppm-hyst         0.05)   ; 15% deadband was eating usable travel

(def b1 (conf-get 'ppm-pulse-start))
(def c1 (conf-get 'ppm-pulse-center))
(def e1 (conf-get 'ppm-pulse-end))
(def h1 (conf-get 'ppm-hyst))
(conf-store)
(def stored 1)
