"""VESC UART packet framing + CRC, ported from bldc/comm/packet.c and util/crc.c."""

COMM_FW_VERSION = 0
COMM_GET_VALUES = 4

START_1B, START_2B, START_3B, STOP = 2, 3, 4, 3


def _make_table():
    # bldc/util/crc.c: CCITT poly 0x1021, table indexed by (crc>>8)^byte
    tab = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
        tab.append(c)
    return tab


CRC16_TAB = _make_table()


def crc16(buf: bytes, cksum: int = 0) -> int:
    for b in buf:
        cksum = CRC16_TAB[((cksum >> 8) ^ b) & 0xFF] ^ ((cksum << 8) & 0xFFFF)
    return cksum & 0xFFFF


def encode(payload: bytes) -> bytes:
    n = len(payload)
    if n <= 255:
        head = bytes([START_1B, n])
    elif n <= 65535:
        head = bytes([START_2B, n >> 8, n & 0xFF])
    else:
        head = bytes([START_3B, n >> 16, (n >> 8) & 0xFF, n & 0xFF])
    c = crc16(payload)
    return head + payload + bytes([c >> 8, c & 0xFF, STOP])


def decode(frame: bytes):
    """Return (payload, consumed) or (None, 0) if not a complete valid frame."""
    if not frame:
        return None, 0
    s = frame[0]
    if s == START_1B:
        hdr, n = 2, (frame[1] if len(frame) > 1 else None)
    elif s == START_2B:
        hdr, n = 3, (int.from_bytes(frame[1:3], "big") if len(frame) > 2 else None)
    elif s == START_3B:
        hdr, n = 4, (int.from_bytes(frame[1:4], "big") if len(frame) > 3 else None)
    else:
        return None, 0
    if n is None:
        return None, 0
    total = hdr + n + 3
    if len(frame) < total:
        return None, 0
    payload = frame[hdr:hdr + n]
    crc_rx = int.from_bytes(frame[hdr + n:hdr + n + 2], "big")
    if frame[total - 1] != STOP or crc_rx != crc16(payload):
        return None, 0
    return payload, total
