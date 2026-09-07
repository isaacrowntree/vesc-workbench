"""Payload layout must match BOTH bldc/comm/commands.c and DAVEga's parser.

These offsets are frame-relative (start byte + length byte, then payload), which
is how DAVEga indexes and also how davega_shim.lisp writes into its tx buffer -
so the numbers below should read identically in all three places.
Run: python3 test_layout.py
"""
import re, pathlib, sys

# what DAVEga's vesc_comm_standard.cpp reads (verified against upstream source)
DAVEGA = {
    "temp_fet": 3, "temp_motor": 5, "motor_current": 7, "battery_current": 11,
    "duty": 23, "rpm": 25, "voltage": 29, "amphours": 31, "amphours_chg": 35,
    "tachometer": 47, "tachometer_abs": 51, "fault": 55,
}

# derived from the firmware field order/widths in commands.c
FIELD_WIDTHS = [
    ("id", 1), ("temp_fet", 2), ("temp_motor", 2), ("motor_current", 4),
    ("battery_current", 4), ("avg_id", 4), ("avg_iq", 4), ("duty", 2),
    ("rpm", 4), ("voltage", 2), ("amphours", 4), ("amphours_chg", 4),
    ("watthours", 4), ("watthours_chg", 4), ("tachometer", 4),
    ("tachometer_abs", 4), ("fault", 1),
]

def derived_offsets():
    off, out, cur = {}, {}, 2      # payload starts at frame index 2
    for name, w in FIELD_WIDTHS:
        off[name] = cur
        cur += w
    return off

fails = []
def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond: fails.append(name)

print("== derived firmware layout vs DAVEga parser offsets")
d = derived_offsets()
for field, expect in DAVEGA.items():
    check(f"{field} @ {expect}", d.get(field) == expect, f"derived {d.get(field)}")

print("\n== payload.lisp structural checks")
# Byte-level behaviour is verified for real in lisp/tests (make test-lisp),
# which runs this exact code in the LispBM interpreter. Here we only guard the
# things that are easy to break silently while golfing.
# Relative to this file, not to the shell's cwd: the test is run both from
# the repo root by CI and from this directory by the Makefile.
lisp = (pathlib.Path(__file__).resolve().parent.parent
        / "src" / "payload.lisp").read_text()
check("crc16 called with 2 args, no start offset", "(crc16 p n)" in lisp)
check("payload built in its own buffer", "(def p (bufcreate" in lisp)
check("framed output buffer is separate", "(def o (bufcreate" in lisp)
check("UNITY written via bufcpy from a string", '(bufcpy p 3 "UNITY" 0 6)' in lisp)
check("alias u = bufset-u8", "(def u bufset-u8)" in lisp)
check("scaled i16 writer g", "(defun g (b x s) (bufset-i16 p b (to-i (* x s))))" in lisp)
check("scaled i32 writer h", "(defun h (b x s) (bufset-i32 p b (to-i (* x s))))" in lisp)
# LispBM symbols are CASE-INSENSITIVE - helper names must not collide with aliases
check("no case-collision between helpers and aliases",
      not any(f"(def {c} " in lisp and f"(defun {c} " in lisp for c in "uwlighp"))
check("fw version spoofed to 6", "(u p 1 6)" in lisp)
check("temps use firmware scale 1e1", "(g 1  (get-temp-fet) 10)" in lisp)
check("amp hours use firmware scale 1e4", "(h 29 (get-ah) 10000)" in lisp)

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}"); sys.exit(1)
print("all layout tests passed")
