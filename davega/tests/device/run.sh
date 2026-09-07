#!/usr/bin/env bash
# Run the dashboard end to end in the MicroPython the DAVEGA runs.
#
# Same argument as lisp/tests/run-lisp-tests.sh: test the code in the
# interpreter that will execute it, not in a host language that resembles it.
set -euo pipefail
cd "$(dirname "$0")/../../.."          # repo root

IMG=davega-micropython
DOCKERFILE=davega/tests/device/Dockerfile.micropython

if ! docker info >/dev/null 2>&1; then
  echo "docker not available - skipping device tests (start Docker/OrbStack)" >&2
  exit 0
fi

if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  echo "building $IMG (first run only, a few minutes)..."
  docker build -q -f "$DOCKERFILE" -t "$IMG" davega/tests/device >/dev/null
fi

# A generous heap on purpose. The board has 98 kB and this host does not, so
# absolute byte counts never carried across anyway - what the suite asserts is
# that a settled frame allocates nothing lasting, and a soak long enough to
# show that needs room the default heap does not have.
exec docker run --rm -v "$PWD":/work -w /work "$IMG" \
  -X heapsize=64M davega/tests/device/test_device.py
