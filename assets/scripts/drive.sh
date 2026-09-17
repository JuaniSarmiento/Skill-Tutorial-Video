#!/usr/bin/env bash
D="$(cd "$(dirname "$0")" && pwd)"
# drive.sh [max_s] : vigila opencode, aprueba permisos seguros solo, y frena ante pregunta, fin de turno, permiso riesgoso o timeout
cd "${TUT_ROOT:-$PWD}"
end=$(( $(date +%s) + ${1:-900} ))
while :; do
  left=$(( end - $(date +%s) )); [ $left -le 0 ] && { echo "TIMEOUT"; break; }
  out=$("$D"/ocwatch.py $left)
  echo "$out" | head -3
  if echo "$out" | grep -qE '^PERMISO'; then
    if echo "$out" | grep -q 'external_directory' && ! echo "$out" | grep -q '"/tmp/\*"\]'; then echo "PERMISO DIR EXTERNO, freno"; break; fi
    if echo "$out" | grep -qiE 'rm -r|sudo|git push|git reset|curl .*\| *(ba)?sh|chmod 777|mkfs|dd if=|> */dev/'; then
      echo "PERMISO RIESGOSO, freno"; break
    fi
    "$D"/allow.sh; echo "  -> aprobado"; continue
  fi
  break
done
