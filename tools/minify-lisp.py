#!/usr/bin/env python3
"""Minify a LispBM file. Upload happens in 384-byte chunks over BLE and the
flash path allows only 1s per chunk, so fewer chunks = better odds.

Strips comments and collapses whitespace, including around parens (LispBM
does not need it). Verified by tests/lisp - the minified output is what ships.
"""
import re, sys, pathlib

def minify(src: str) -> str:
    lines = [re.sub(r';.*$', '', l).strip() for l in src.splitlines()]
    out = re.sub(r'\s+', ' ', ' '.join(l for l in lines if l))
    out = re.sub(r'\)\s+\(', ')(', out)
    out = re.sub(r'\(\s+', '(', out)
    out = re.sub(r'\s+\)', ')', out)
    return out

if __name__ == "__main__":
    src_p, dst_p = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    src = src_p.read_text()
    # board-specific substitutions (see profiles/)
    canid = sys.argv[3] if len(sys.argv) > 3 else "124"
    src = src.replace("@@CANID@@", canid)
    out = minify(src)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    dst_p.write_text(out)
    chunks = (len(out) + 383) // 384
    print(f"{src_p.name}: {len(src)} -> {len(out)} chars ({chunks} chunks of 384)")
