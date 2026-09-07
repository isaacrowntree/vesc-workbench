#!/usr/bin/env bash
# Run the shim's pure LispBM logic in the upstream LispBM REPL (Docker/OrbStack).
# Tests BOTH the readable source and the minified artifact that actually ships.
set -euo pipefail
# up to the repo root: this script lives at lisp/tests/
cd "$(dirname "$0")/../.."

if ! docker info >/dev/null 2>&1; then
  echo "docker not available - skipping lisp tests (start Docker/OrbStack)" >&2
  exit 0
fi

IMG=lacroix-lispbm
if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  echo "building $IMG (first run only)..."
  docker build -q -f lisp/tests/Dockerfile.lispbm -t "$IMG" lisp/tests >/dev/null
fi

mkdir -p build
python3 lisp/minify.py lisp/src/davega_shim.lisp build/davega_shim.min.lisp

cat lisp/tests/stubs.lisp lisp/src/payload.lisp lisp/tests/test_payload.lisp \
    > build/lisp-test-bundle.lisp

python3 - <<'PY'
import pathlib
mini = pathlib.Path("build/davega_shim.min.lisp").read_text()
idx = mini.find("(uart-start")
assert idx > 0, "minified output missing (uart-start"
pathlib.Path("build/min-test-bundle.lisp").write_text(
    pathlib.Path("lisp/tests/stubs.lisp").read_text() + "\n" + mini[:idx] + "\n"
    + pathlib.Path("lisp/tests/test_payload.lisp").read_text())
PY

# the proxy has its own bundle
sed 's/@@CANID@@/124/' lisp/src/proxy.lisp > build/proxy-sub.lisp
cat lisp/tests/stubs.lisp build/proxy-sub.lisp lisp/tests/frames.lisp \
    lisp/tests/test_proxy.lisp > build/proxy-test-bundle.lisp

# integration: the real reader driven through a fake UART. The harness comes
# after the proxy core so its uart-read/cmds-proc/reply-ping win.
cat lisp/tests/stubs.lisp build/proxy-sub.lisp lisp/src/reader.lisp \
    lisp/tests/frames.lisp lisp/tests/harness.lisp lisp/tests/test_reader.lisp \
    > build/reader-test-bundle.lisp

# reader cost bench: same wire, different read strategies
cat lisp/tests/stubs.lisp build/proxy-sub.lisp lisp/src/reader.lisp \
    lisp/tests/frames.lisp lisp/tests/harness.lisp lisp/tests/bench_reader.lisp \
    > build/reader-bench-bundle.lisp

# the flight recorder, driven through a scripted ride
cat lisp/tests/logger_stubs.lisp lisp/src/logger.lisp \
    lisp/tests/test_logger.lisp > build/logger-test-bundle.lisp

fail=0
for b in lisp-test-bundle min-test-bundle proxy-test-bundle reader-test-bundle reader-bench-bundle logger-test-bundle; do
  echo "--- $b"
  out=$(docker run --rm -v "$PWD/build:/work" "$IMG" \
        repl --terminate -H 2097152 -M 262144 --src "/work/$b.lisp" 2>&1) || true
  echo "$out" | grep -E '  (PASS|FAIL)|passed|FAILED' || echo "$out" | tail -5
  echo "$out" | grep -q "all lisp tests passed" || { echo "FAILED: $b" >&2; fail=1; }
done
exit $fail
