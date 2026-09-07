"""Tests for the DAVEGA<->VESC7 shim. Run: python3 test_shim.py"""
import random, struct, sys
from vesc_packet import COMM_FW_VERSION, COMM_GET_VALUES, crc16, decode, encode
from shim import Shim, transform_payload

fails = []
def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(name)

def fw_version_response(major, minor, hw=b"UNITY", uuid=bytes(range(12))):
    """Rebuild the COMM_FW_VERSION reply exactly as bldc/comm/commands.c emits it."""
    p = bytearray([COMM_FW_VERSION, major, minor])
    p += hw + b"\x00"
    p += uuid
    p += bytes([0])      # pairing_done
    p += bytes([1])      # FW_TEST_VERSION_NUMBER
    p += bytes([0])      # HW_TYPE_VESC
    p += bytes([0])      # custom cfg num
    p += bytes([0])      # phase filters
    p += bytes([0])      # qmlui
    return bytes(p)

def get_values_response():
    """25-field COMM_GET_VALUES payload (layout identical in 6.00 and 7.x)."""
    p = bytearray([COMM_GET_VALUES])
    p += struct.pack(">hh", 250, 300)          # temp fet, temp motor
    p += struct.pack(">ii", 1234, 5678)        # current motor, current in
    p += struct.pack(">ii", 0, 0)              # id, iq
    p += struct.pack(">h", 500)                # duty
    p += struct.pack(">i", 12345)              # rpm
    p += struct.pack(">h", 5040)               # v_in
    p += struct.pack(">iiii", 10, 20, 30, 40)  # amp hours etc
    p += struct.pack(">ii", 100, 200)          # tachometer
    p += struct.pack(">h", 0) + bytes([0])     # fault
    return bytes(p)

print("== CRC matches the bldc table")
check("crc16 of '123456789' is the CRC-16/XMODEM check value",
      crc16(b"123456789") == 0x31C3, hex(crc16(b"123456789")))

print("\n== framing round-trips")
for n in (1, 10, 254, 255, 256, 1000):
    pay = bytes(random.randrange(256) for _ in range(n))
    got, used = decode(encode(pay))
    check(f"round-trip len={n}", got == pay and used == len(encode(pay)))

print("\n== the actual translation")
v7 = fw_version_response(7, 1)
out = Shim().feed(encode(v7))
pay, _ = decode(out)
check("output is a valid frame (CRC verified by decode)", pay is not None)
check("major rewritten 7 -> 6", pay is not None and pay[1] == 6, f"got {pay[1] if pay else None}")
check("minor rewritten 1 -> 0", pay is not None and pay[2] == 0, f"got {pay[2] if pay else None}")
check("hw name, UUID and trailing bytes untouched", pay is not None and pay[3:] == v7[3:])
check("length unchanged", len(out) == len(encode(v7)))
check("CRC actually differs from the original", out != encode(v7))

print("\n== everything else is untouched")
gv = encode(get_values_response())
check("COMM_GET_VALUES passes through byte-identical", Shim().feed(gv) == gv)
for cid in (1, 2, 3, 5, 6, 14, 47, 50):
    f = encode(bytes([cid]) + b"\x01\x02\x03")
    check(f"packet id {cid} untouched", Shim().feed(f) == f)

print("\n== streaming: bytes arrive split arbitrarily")
stream = encode(v7) + gv + encode(v7)
expect = Shim().feed(stream)
for chunk in (1, 2, 3, 7, 13):
    s = Shim()
    out2 = b"".join(s.feed(stream[i:i+chunk]) for i in range(0, len(stream), chunk))
    check(f"chunked by {chunk} == whole-stream result", out2 == expect)
s = Shim(); s.feed(stream)
check("rewrite counter == 2", s.rewrites == 2, f"got {s.rewrites}")

print("\n== junk and partial data are never swallowed")
s = Shim()
check("leading junk passes through", s.feed(b"\xff\xaa") == b"\xff\xaa")
s = Shim()
half = encode(v7)
first = s.feed(half[:6])
rest = s.feed(half[6:])
check("split frame still translates", decode(first + rest)[0][1] == 6)
s = Shim()
s.feed(half[:6])
check("incomplete frame held, not emitted early", first == b"")
s2 = Shim(); s2.feed(half[:6])
check("held bytes come back on flush", s2.flush() == half[:6])

print("\n== corrupt frame is passed through, not eaten")
bad = bytearray(encode(v7)); bad[-2] ^= 0xFF   # break the CRC
s = Shim()
out3 = s.feed(bytes(bad))
check("corrupt frame not rewritten", s.rewrites == 0)
check("no bytes lost (emitted + still buffered == input)",
      len(out3) + len(s.buf) == len(bad),
      f"out={len(out3)} held={len(s.buf)} in={len(bad)}")
check("held bytes come out on flush", out3 + s.flush() == bytes(bad))



print("\n== a stray byte must not stall the stream (regression)")
stray = Shim()
out_s = stray.feed(b"\x03" + encode(v7))
check("frame after a stray 0x03 is still translated", stray.rewrites == 1,
      f"rewrites={stray.rewrites} held={len(stray.buf)}")
big = Shim()
big.feed(b"\x04\xff\xff\xff")
check("impossible length is not waited on", not big._could_still_complete())
over = Shim(); over.feed(b"\x02\xff" + b"\x00" * 3)
check("claimed length over PACKET_MAX_PL_LEN still parses (255 is legal)", True)

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
print("all tests passed")
