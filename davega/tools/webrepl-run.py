#!/usr/bin/env python3
"""Drive a MicroPython WebREPL from the shell. Stdlib only.

The browser client is fine for poking around, but pasting a long script into a
terminal emulator over a websocket is slow and lossy. This talks the same
protocol directly, so scripts can be run and their output captured.

    davega/tools/webrepl-run.py -p PASS -e "import sys; print(sys.implementation)"
    davega/tools/webrepl-run.py -p PASS -f davega/tools/recon.py -e "recon()"
    davega/tools/webrepl-run.py -p PASS -f davega/tools/settings.py -e "show()"

Uses the raw REPL (ctrl-A), so what comes back is the script's output rather
than an echo of everything typed.
"""
import argparse
import base64
import os
import socket
import struct
import sys
import tempfile
import time

# macOS: pin a socket to one interface. Needed because the DAVEGA's access
# point hands out 192.168.4.x with a 192.168.4.1 gateway, which collides with
# plenty of phone hotspots and routers. When two interfaces share the subnet
# the default route wins and the packets go to the wrong 192.168.4.1 - which
# answers pings and refuses port 8266, so it looks like the display is broken.
IP_BOUND_IF = 25


def _connect(host, port, timeout, iface=None):
    def bound(name):
        s = socket.socket()
        s.settimeout(timeout)
        s.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF,
                     struct.pack("I", socket.if_nametoindex(name)))
        s.connect((host, port))
        return s

    if iface:
        return bound(iface)
    try:
        return socket.create_connection((host, port), timeout)
    except OSError as first:
        if not hasattr(socket, "if_nameindex"):
            raise
        for _, name in socket.if_nameindex():
            if name.startswith("lo"):
                continue
            try:
                s = bound(name)
                print("reached %s via %s (the default route goes elsewhere)"
                      % (host, name), file=sys.stderr)
                return s
            except OSError:
                continue
        raise first


class WS:
    """The smallest websocket client that will hold a WebREPL session."""

    def __init__(self, host, port, timeout=10, iface=None):
        self.sock = _connect(host, port, timeout, iface)
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
        # Client frames must be masked. TEXT opcode: WebREPL treats binary
        # frames as the file-transfer protocol, so terminal input sent as
        # binary is silently swallowed - the prompt answers, then nothing.
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            head = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < 65536:
            head = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            head = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
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

    def read_raw_result(self, timeout=90):
        """Read one raw-REPL response: OK, stdout, 0x04, stderr, 0x04, '>'.

        MicroPython is not consistent about how many 0x04s trail the result,
        so stop on the prompt once at least one has been seen rather than
        matching an exact terminator.
        """
        out = b""
        end = time.time() + timeout
        # Two 0x04s bracket the result: one ends stdout, one ends stderr.
        # Stopping at the first ">" is wrong - a traceback says "<stdin>",
        # and a frame boundary landing after it truncates the error.
        while not (out.endswith(b">") and out.count(b"\x04") >= 2):
            if time.time() > end:
                raise TimeoutError("raw REPL did not finish, got %r" % out[-300:])
            try:
                op, payload = self._frame()
            except socket.timeout:
                continue
            if op == 0x8:
                raise IOError("server closed the connection")
            out += payload
        return out

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

    def send_binary(self, data):
        """Binary frames are the file-transfer channel, not terminal input."""
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            head = struct.pack("!BB", 0x82, 0x80 | n)
        elif n < 65536:
            head = struct.pack("!BBH", 0x82, 0x80 | 126, n)
        else:
            head = struct.pack("!BBQ", 0x82, 0x80 | 127, n)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4]
                                              for i, b in enumerate(data)))

    def _resp(self):
        out = b""
        while len(out) < 4:
            _, payload = self._frame()
            out += payload
        sig, code = struct.unpack("<2sH", out[:4])
        if sig != b"WB":
            raise IOError("bad file-transfer response %r" % out[:4])
        return code

    def put_file(self, local, remote):
        """Upload a file. Far more reliable than pasting a script into a 1.14
        REPL, which has no raw-paste flow control and drops what it cannot
        keep up with."""
        with open(local, "rb") as fh:
            data = fh.read()
        name = remote.encode()
        rec = struct.pack("<2sBBQLH64s", b"WA", 1, 0, 0, len(data),
                          len(name), name)
        self.send_binary(rec[:10])
        self.send_binary(rec[10:])
        if self._resp() != 0:
            raise IOError("device refused the write of %s" % remote)
        for i in range(0, len(data), 1024):
            self.send_binary(data[i:i + 1024])
        if self._resp() != 0:
            raise IOError("upload of %s failed" % remote)
        return len(data)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def run(host, port, password, files, exprs, quiet=False, iface=None,
        puts=(), mkdirs=()):
    ws = WS(host, port, iface=iface)
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
        # MicroPython 1.14 has no raw-paste flow control (that arrived in
        # 1.19), so anything but a short line can overrun the input buffer -
        # the device then answers with a bare prompt and no result, which
        # looks like the code failed rather than never arriving. Ship
        # anything sizeable as a file over the transfer channel, which does
        # have flow control, and execute a one-liner that reads it back.
        if len(src) > 100 or "\n" in src.strip():
            tmp = os.path.join(tempfile.gettempdir(), "_webrepl_snippet.py")
            with open(tmp, "w") as fh:
                fh.write(src)
            ws.send(b"\x02")
            ws.read_until(b">>>")
            ws.put_file(tmp, "/_snip.py")
            ws.send(b"\x01")
            ws.read_until(b"raw REPL")
            src = "exec(open('/_snip.py').read())"
        ws.send(src.encode() + b"\x04")
        out = ws.read_raw_result()
        body = out.split(b"OK", 1)[-1]
        text, _, err = body.partition(b"\x04")
        sys.stdout.write(text.decode("utf8", "replace"))
        err = err.rstrip(b"\x04>").strip()
        if err:
            sys.stderr.write("[%s] %s\n" % (label, err.decode("utf8", "replace")))
            return False
        return True

    ok = True
    for d in mkdirs:
        execute("import os\ntry:\n    os.mkdir('%s')\nexcept OSError:\n    pass" % d,
                "mkdir " + d)
    for spec in puts:
        local, _, remote = spec.partition(":")
        ws.send(b"\x02")
        ws.read_until(b">>>")
        n = ws.put_file(local, remote)
        if not quiet:
            print("uploaded %s -> %s (%d bytes)" % (local, remote, n), file=sys.stderr)
        ws.send(b"\x01")
        ws.read_until(b"raw REPL")
    for path in files:
        remote = "/" + os.path.basename(path)
        ws.send(b"\x02")                # file transfer needs the normal REPL
        ws.read_until(b">>>")
        n = ws.put_file(path, remote)
        if not quiet:
            print("uploaded %s -> %s (%d bytes)" % (path, remote, n),
                  file=sys.stderr)
        ws.send(b"\x01")
        ws.read_until(b"raw REPL")
        ok &= execute("exec(open('%s').read())" % remote, path)
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
    ap.add_argument("--put", action="append", default=[], metavar="LOCAL:REMOTE",
                    help="upload a file to an exact remote path, repeatable; "
                         "runs before -f and -e")
    ap.add_argument("--mkdir", action="append", default=[], metavar="PATH",
                    help="create a directory on the device if absent")
    ap.add_argument("-i", "--iface", default=os.environ.get("DAVEGA_IFACE"),
                    help="pin to an interface, e.g. en0; auto-detected if the "
                         "default route reaches the wrong host")
    a = ap.parse_args()
    if not a.password:
        ap.error("no password given (-p or WEBREPL_PASSWORD)")
    if not a.file and not a.eval and not a.put and not a.mkdir:
        a.eval = ["import sys, os; print(sys.implementation); print(os.listdir('/'))"]
    try:
        sys.exit(run(a.host, a.port, a.password, a.file, a.eval, a.quiet, a.iface,
                     a.put, a.mkdir))
    except (IOError, TimeoutError) as e:
        sys.exit("failed: %s" % e)


if __name__ == "__main__":
    main()
