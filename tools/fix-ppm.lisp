; One-shot: set the PPM parameters that the XML write path cannot reach.
; conf-set applies instantly; conf-store persists to flash.
; Reports results in globals so they can be read back via lispGetStats.

(def before-ctrl (conf-get 'ppm-ctrl-type))
(def before-ramp (conf-get 'ppm-ramp-time-pos))

(conf-set 'ppm-ctrl-type 3)        ; Current No Reverse With Brake
(conf-set 'ppm-ramp-time-pos 0.3)
(conf-set 'ppm-ramp-time-neg 0.2)

(def after-ctrl (conf-get 'ppm-ctrl-type))
(def after-ramp (conf-get 'ppm-ramp-time-pos))

(conf-store)
(def stored 1)
