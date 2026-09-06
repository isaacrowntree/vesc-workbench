"""DAVEGA <-> VESC7 translation.

The VESC UART protocol is byte-identical between FW 6.00 and 7.x (see
../tests/protocol-diff.sh). The DAVEGA only refuses to work because of the two
version bytes in the COMM_FW_VERSION response. This rewrites those, recomputes
the CRC, and passes every other byte through untouched.

Direction that matters: ESC -> DAVEGA.
"""

from vesc_packet import COMM_FW_VERSION, decode, encode

SPOOF_MAJOR = 6
SPOOF_MINOR = 0


def transform_payload(payload: bytes) -> bytes:
    """Rewrite a COMM_FW_VERSION response; leave everything else alone."""
    if len(payload) >= 3 and payload[0] == COMM_FW_VERSION:
        return bytes([payload[0], SPOOF_MAJOR, SPOOF_MINOR]) + payload[3:]
    return payload


class Shim:
    """Byte-stream transformer. Feed bytes in, get bytes out, in order.

    Anything that is not a complete valid VESC frame is passed through verbatim,
    so noise, partial frames and unknown traffic can never be swallowed.
    """

    MAX_BUF = 8192
    # bldc/comm/packet.h PACKET_MAX_PL_LEN - a longer claimed payload is junk,
    # so treat it as a bad start byte and resync instead of waiting for it.
    MAX_PAYLOAD = 512

    def __init__(self):
        self.buf = bytearray()
        self.rewrites = 0

    def feed(self, data: bytes) -> bytes:
        self.buf += data
        out = bytearray()
        while self.buf:
            payload, used = decode(bytes(self.buf))
            if payload is not None:
                new = transform_payload(payload)
                if new != payload:
                    self.rewrites += 1
                out += encode(new)
                del self.buf[:used]
                continue
            # Might be an incomplete frame at a valid start byte -> wait for more.
            if self.buf[0] in (2, 3, 4) and len(self.buf) < self.MAX_BUF:
                if self._could_still_complete():
                    break
            out.append(self.buf[0])   # not a frame start, or junk: pass through
            del self.buf[:1]
        return bytes(out)

    def _could_still_complete(self) -> bool:
        if not self.buf:
            return False
        s = self.buf[0]
        hdr = {2: 2, 3: 3, 4: 4}[s]
        if len(self.buf) < hdr:
            return True
        n = self.buf[1] if s == 2 else int.from_bytes(bytes(self.buf[1:hdr]), "big")
        if n > self.MAX_PAYLOAD:
            return False
        total = hdr + n + 3
        # Bound the wait by the CLAIMED length, not just by what is buffered.
        # A stray 0x03 or 0x04 byte otherwise parks the stream for hundreds of
        # bytes while every frame in that window passes through untranslated.
        return total <= self.MAX_BUF and len(self.buf) < total

    def flush(self) -> bytes:
        # Release one byte at a time and re-attempt resync, rather than dumping
        # the buffer raw - held bytes may contain a translatable frame.
        out = bytearray()
        while self.buf:
            out.append(self.buf[0])
            del self.buf[:1]
            out += self.feed(b"")
        return bytes(out)
