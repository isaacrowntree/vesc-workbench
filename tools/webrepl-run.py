#!/usr/bin/env python3
"""Drive a MicroPython WebREPL from the shell. Stdlib only.

The browser client is fine for poking around, but pasting a long script into a
terminal emulator over a websocket is slow and lossy. This talks the same
protocol directly, so scripts can be run and their output captured.

    tools/webrepl-run.py -p PASS -e "import sys; print(sys.implementation)"
    tools/webrepl-run.py -p PASS -f davega-shim/webrepl/recon.py -e "recon()"
    tools/webrepl-run.py -p PASS -f davega-shim/webrepl/settings.py -e "show()"

Uses the raw REPL (ctrl-A), so what comes back is the script's output rather
than an echo of everything typed.
"""
import argparse
import base64
import os
import socket
import struct
import sys
import time


class WS:
    """The smallest websocket client that will hold a WebREPL session."""

    def __init__(self, host, port, timeout=10):
        self.sock = socket.create_connection((host, port), timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            ("GET / HTTP/1.1\r\n"
             "Host: %s:%d\r\n"
             "Connection: Upgrade\r\n"
             "Upgrade: websocket\r\n"
             "Sec-WebSocket-Version: 13\r\n"
             "Sec-WebSocket-Key: %s\r\n\r\n" % (host, port, key)).encode())
        hdr = b""
        while b"\r\n\r\n" not in hdr:
            chunk = self.sock.recv(1)
            if not chunk:
                raise IOError("connection closed during handshake")
            hdr += chunk
        if b"101" not in hdr.split(b"\r\n")[0]:
            raise IOError("not a websocket upgrade: %r" % hdr[:80])
        self.buf = b""

    def send(self, data):
        # Client frames must be masked. Binary opcode: what the JS client uses.
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            head = struct.pack("!BB", 0x82, 0x80 | n)
        elif n < 65536:
            head = struct.pack("!BBH", 0x82, 0x80 | 126, n)
        else:
            head = struct.pack("!BBQ", 0x82, 0x80 | 127, n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(head + mask + masked)

    def _frame(self):
        def need(n):
            while len(self.buf) < n:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise IOError("closed")
                self.buf += chunk
        need(2)
        b1, b2 = self.buf[0], self.buf[1]
        ln = b2 & 0x7F
        off = 2
        if ln == 126:
            need(4); ln = struct.unpack("!H", self.buf[2:4])[0]; off = 4
        elif ln == 127:
            need(10); ln = struct.unpack("!Q", self.buf[2:10])[0]; off = 10
        need(off + ln)
        payload = self.buf[off:off + ln]
        self.buf = self.buf[off + ln:]
        return b1 & 0x0F, payload

    def read_until(self, marker, timeout=25):
        """Collect payloads until marker appears. Returns everything read."""
        out = b""
        end = time.time() + timeout
        while marker not in out:
            if time.time() > end:
                raise TimeoutError("waiting for %r, got %r" % (marker, out[-300:]))
            try:
                op, payload = self._frame()
            except socket.timeout:
                continue
            if op == 0x8:
                raise IOError("server closed the connection")
            out += payload
        return out

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def run(host, port, password, files, exprs, quiet=False):
    ws = WS(host, port)
    ws.read_until(b"Password:")
    ws.send((password + "\r\n").encode())
    banner = ws.read_until(b">>>")
    if b"denied" in banner or b"Access denied" in banner:
        raise SystemExit("password rejected")
    if not quiet:
        print("connected to %s:%d" % (host, port), file=sys.stderr)

    ws.send(b"\x01")                    # raw REPL: no echo, no prettifying
    ws.read_until(b"raw REPL")

    def execute(src, label):
        ws.send(src.encode() + b"\x04")
        out = ws.read_until(b"\x04>", timeout=90)
        body = out.split(b"OK", 1)[-1]
        text, _, err = body.partition(b"\x04")
        sys.stdout.write(text.decode("utf8", "replace"))
        err = err.rstrip(b"\x04>").strip()
        if err:
            sys.stderr.write("[%s] %s\n" % (label, err.decode("utf8", "replace")))
            return False
        return True

    ok = True
    for path in files:
        with open(path) as fh:
            ok &= execute(fh.read(), path)
    for expr in exprs:
        ok &= execute(expr, expr[:40])

    ws.send(b"\x02")                    # back to the friendly REPL
    ws.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="192.168.4.1")
    ap.add_argument("--port", type=int, default=8266)
    ap.add_argument("-p", "--password", default=os.environ.get("WEBREPL_PASSWORD"),
                    help="or set WEBREPL_PASSWORD")
    ap.add_argument("-f", "--file", action="append", default=[],
                    help="source file to send, repeatable; sent before -e")
    ap.add_argument("-e", "--eval", action="append", default=[],
                    help="expression to evaluate, repeatable")
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    if not a.password:
        ap.error("no password given (-p or WEBREPL_PASSWORD)")
    if not a.file and not a.eval:
        a.eval = ["import sys, os; print(sys.implementation); print(os.listdir('/'))"]
    try:
        sys.exit(run(a.host, a.port, a.password, a.file, a.eval, a.quiet))
    except (IOError, TimeoutError) as e:
        sys.exit("failed: %s" % e)


if __name__ == "__main__":
    main()
