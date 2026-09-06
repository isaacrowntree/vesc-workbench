#!/usr/bin/env bash
# Reproducible check: does the VESC UART protocol the DAVEGA depends on differ
# between FW 6.00 (last version DAVEGA supports) and 7.x (master)?
#   ./tests/protocol-diff.sh
set -euo pipefail
FAIL=0
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

for ref in 6.00 master; do
  curl -sL "https://raw.githubusercontent.com/vedderb/bldc/$ref/comm/commands.c" -o "$T/cmd_$ref.c"
  curl -sL "https://raw.githubusercontent.com/vedderb/bldc/$ref/datatypes.h"      -o "$T/dt_$ref.h"
  [ -s "$T/cmd_$ref.c" ] || { echo "fetch failed for $ref" >&2; exit 1; }
done

echo "== packet ids the DAVEGA uses"
for ref in 6.00 master; do
  printf '%-7s ' "$ref"
  grep -oE 'COMM_(FW_VERSION|GET_VALUES)[[:space:]]*=[[:space:]]*[0-9]+' "$T/dt_$ref.h" \
    | head -2 | tr '\n' ' '
  echo
done
echo "(6.00 uses implicit enum ordinals; COMM_GET_VALUES is the 5th entry = 4)"

echo
echo "== COMM_GET_VALUES payload layout"
for ref in 6.00 master; do
  awk '/case COMM_GET_VALUES:/{f=1} f{print} f&&/break;/{exit}' "$T/cmd_$ref.c" \
    | grep -oE 'buffer_append_[a-z0-9_]+\(send_buffer,[^;]*' \
    | sed -E 's/buffer_append_([a-z0-9_]+)\(send_buffer, *([^,]+).*/\1  \2/' > "$T/gv_$ref.txt"
  printf '%-7s %s fields\n' "$ref" "$(wc -l < "$T/gv_$ref.txt" | tr -d ' ')"
done
if diff -q "$T/gv_6.00.txt" "$T/gv_master.txt" >/dev/null; then
  echo "RESULT: payload IDENTICAL"
else
  echo "RESULT: payload DIFFERS"
  diff -u "$T/gv_6.00.txt" "$T/gv_master.txt" || true
  FAIL=1
fi

echo
echo "== COMM_FW_VERSION response structure"
for ref in 6.00 master; do
  awk '/case COMM_FW_VERSION:/{f=1} f{print} f&&/break;/{exit}' "$T/cmd_$ref.c" \
    | grep -oE 'send_buffer\[ind\+\+\] = [A-Za-z_>()-]+|memcpy[^;]*|strcpy[^;]*|buffer_append_[a-z0-9_]+\([^;]*' > "$T/fw_$ref.txt"
done
if diff -q "$T/fw_6.00.txt" "$T/fw_master.txt" >/dev/null; then
  echo "RESULT: structure IDENTICAL"
else
  echo "RESULT: structure DIFFERS (expected: 7.x adds a hw-crc word)"
  diff -u "$T/fw_6.00.txt" "$T/fw_master.txt" || true
fi

echo
echo "== version constants (the only runtime difference)"
for ref in 6.00 master; do
  printf '%-7s ' "$ref"
  curl -sL "https://raw.githubusercontent.com/vedderb/bldc/$ref/conf_general.h" \
    | grep -E '#define FW_VERSION_(MAJOR|MINOR)' | tr -s ' \t' ' ' | tr '\n' ' '
  echo
done

# Only the GET_VALUES payload is load-bearing for the shim; a difference there
# invalidates the project's central claim and must fail the build.
exit $FAIL
