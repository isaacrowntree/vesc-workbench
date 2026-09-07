; Frame builders shared by the proxy and reader tests.
; build a framed packet: [2][len][payload][crc-hi][crc-lo][3]
(define mkframe (lambda (payload) {
    (var n (buflen payload))
    (var f (bufcreate (+ n 5)))
    (bufset-u8 f 0 2) (bufset-u8 f 1 n)
    (bufcpy f 2 payload 0 n)
    (var c (crc16 payload n))
    (bufset-u8 f (+ 2 n) (shr c 8))
    (bufset-u8 f (+ 3 n) (bitwise-and c 255))
    (bufset-u8 f (+ 4 n) 3)
    f
}))

(define crc-of-frame (lambda (f) {
    (var n (bufget-u8 f 1))
    (var q (bufcreate n))
    (bufcpy q 0 f 2 n)
    (crc16 q n)
}))
(define frame-crc-field (lambda (f) {
    (var n (bufget-u8 f 1))
    (+ (shl (bufget-u8 f (+ 2 n)) 8) (bufget-u8 f (+ 3 n)))
}))

