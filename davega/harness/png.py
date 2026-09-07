"""Minimal PNG writer. Stdlib only, so CI needs no image library.

The harness renders a 240x320 RGB buffer; this puts it on disk in a form a
human can look at and git can diff.
"""
import struct
import zlib


def write_rgb(path, width, height, pixels):
    """pixels: bytearray of width*height*3 bytes, row-major RGB."""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)                     # filter type 0 (None)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        fh.write(chunk(b"IEND", b""))


def read_rgb(path):
    """Read back a PNG this module wrote. Returns (width, height, pixels)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG" % path)
    pos, width, height, idat = 8, None, None, b""
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
        elif tag == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    stride = width * 3
    out = bytearray()
    for y in range(height):
        f = raw[y * (stride + 1)]
        if f != 0:
            raise ValueError("only filter 0 is supported, got %d" % f)
        out += raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
    return width, height, out
