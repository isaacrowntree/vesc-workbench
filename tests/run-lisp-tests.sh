#!/usr/bin/env bash
# Run the shim's pure LispBM logic in the upstream LispBM REPL (Docker/OrbStack).
# Tests BOTH the readable source and the minified artifact that actually ships.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! docker info >/dev/null 2>&1; then
  echo "docker not available - skipping lisp tests (start Docker/OrbStack)" >&2
  exit 0
fi

IMG=lacroix-lispbm
if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  echo "building $IMG (first run only)..."
  docker build -q -f tests/Dockerfile.lispbm -t "$IMG" tests >/dev/null
fi

mkdir -p build
python3 tools/minify-lisp.py davega-shim/lisp/davega_shim.lisp build/davega_shim.min.lisp

cat tests/lisp/stubs.lisp davega-shim/lisp/payload.lisp tests/lisp/test_payload.lisp \
    > build/lisp-test-bundle.lisp

python3 - <<'PY'
import pathlib
mini = pathlib.Path("build/davega_shim.min.lisp").read_text()
idx = mini.find("(uart-start")
assert idx > 0, "minified output missing (uart-start"
pathlib.Path("build/min-test-bundle.lisp").write_text(
    pathlib.Path("tests/lisp/stubs.lisp").read_text() + "\n" + mini[:idx] + "\n"
    + pathlib.Path("tests/lisp/test_payload.lisp").read_text())
PY

# the proxy has its own bundle
sed 's/@@CANID@@/124/' davega-shim/lisp/proxy.lisp > build/proxy-sub.lisp
cat tests/lisp/stubs.lisp build/proxy-sub.lisp tests/lisp/frames.lisp \
    tests/lisp/test_proxy.lisp > build/proxy-test-bundle.lisp

# integration: the real reader driven through a fake UART. The harness comes
# after the proxy core so its uart-read/cmds-proc/reply-ping win.
cat tests/lisp/stubs.lisp build/proxy-sub.lisp davega-shim/lisp/reader.lisp \
    tests/lisp/frames.lisp tests/lisp/harness.lisp tests/lisp/test_reader.lisp \
    > build/reader-test-bundle.lisp

fail=0
for b in lisp-test-bundle min-test-bundle proxy-test-bundle reader-test-bundle; do
  echo "--- $b"
  out=$(docker run --rm -v "$PWD/build:/work" "$IMG" \
        repl --terminate --src "/work/$b.lisp" 2>&1) || true
  echo "$out" | grep -E '  (PASS|FAIL)|passed|FAILED' || echo "$out" | tail -5
  echo "$out" | grep -q "all lisp tests passed" || { echo "FAILED: $b" >&2; fail=1; }
done
exit $fail
