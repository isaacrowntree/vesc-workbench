; minimal pipeline test - no UART, no side effects
(print "shim-pipeline-ok")
(print (str-merge "vin=" (str-from-n (get-vin))))
(print (str-merge "temp-fet=" (str-from-n (get-temp-fet))))
