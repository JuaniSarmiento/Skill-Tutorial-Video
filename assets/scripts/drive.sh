#!/usr/bin/env bash
D="$(cd "$(dirname "$0")" && pwd)"
# drive.sh [max_s] : vigila opencode, aprueba SOLO permisos seguros, y frena ante
# pregunta, fin de turno, permiso riesgoso o timeout.
#
# El filtro decide sobre el texto COMPLETO del permiso (ocwatch.py ya no lo trunca).
# Antes decidía sobre 300 caracteres: un comando peligroso más allá del corte pasaba
# y se aprobaba con "allow always". Un guardrail que falla abierto es peor que ninguno,
# porque te hace dejar la máquina sola.
cd "${TUT_ROOT:-$PWD}"
end=$(( $(date +%s) + ${1:-900} ))
offset=""

# Lista blanca primero: si el permiso NO es claramente inofensivo, se frena.
# Es al revés que la lista negra original, que sólo frenaba lo que alguien se acordó
# de escribir. Todo lo que no está acá lo mirás vos.
SEGURO='^(ls|pwd|cat|head|tail|wc|echo|printf|uname|which|whoami|date|node|npm|npx|git (status|log|diff|add|commit|init|branch)|mkdir|touch|cp|mv|tsc|wrangler|curl -s|grep|rg|find [^|]*-name)'

# Y una lista negra explícita por si algo pasa la blanca combinado con otra cosa.
RIESGOSO='rm[[:space:]]+-[rf]|rm[[:space:]]+--recursive|\bsudo\b|git[[:space:]]+(-C[[:space:]]+\S+[[:space:]]+)?(push|reset|clean)|curl[^|]*\|[[:space:]]*(ba)?sh|wget[^|]*\|[[:space:]]*(ba)?sh|chmod[[:space:]]+(-R[[:space:]]+)?777|mkfs|dd[[:space:]]+if=|>[[:space:]]*/dev/|-delete\b|>>?[[:space:]]*~?/?\.(bashrc|zshrc|profile|ssh)|\.ssh|credentials|\.env\b'

while :; do
  left=$(( end - $(date +%s) )); [ $left -le 0 ] && { echo "TIMEOUT"; break; }

  if [ -n "$offset" ]; then
    out=$("$D"/ocwatch.py "$left" --offset "$offset")
  else
    out=$("$D"/ocwatch.py "$left")
  fi
  # el offset se arrastra entre vueltas: sin esto se pierde todo lo que pasa
  # durante los ~5 s que tarda allow.sh, incluido un segundo pedido de permiso.
  nuevo=$(echo "$out" | sed -n 's/^OFFSET=//p' | tail -1)
  [ -n "$nuevo" ] && offset="$nuevo"

  echo "$out" | grep -v '^OFFSET=' | head -3

  if echo "$out" | grep -qE '^PERMISO'; then
    cuerpo=$(echo "$out" | grep '^PERMISO' | sed 's/^PERMISO: //')

    if echo "$cuerpo" | grep -qiE "$RIESGOSO"; then
      echo "PERMISO RIESGOSO, freno:"; echo "  ${cuerpo:0:400}"; break
    fi
    if echo "$cuerpo" | grep -q 'external_directory' && ! echo "$cuerpo" | grep -q '"/tmp/\*"\]'; then
      echo "PERMISO DIR EXTERNO, freno:"; echo "  ${cuerpo:0:400}"; break
    fi
    # los comandos vienen entre comillas dentro del payload; sacamos cada uno y
    # exigimos que TODOS empiecen con algo de la lista blanca.
    cmds=$(echo "$cuerpo" | grep -oE '"[^"]{2,400}"' | tr -d '"')
    todo_ok=1
    while IFS= read -r c; do
      [ -z "$c" ] && continue
      echo "$c" | grep -qE "$SEGURO" || { todo_ok=0; echo "NO RECONOZCO: $c"; }
    done <<< "$cmds"
    if [ "$todo_ok" -ne 1 ]; then
      echo "PERMISO NO RECONOCIDO COMO SEGURO, freno"; break
    fi

    "$D"/allow.sh; echo "  -> aprobado (allow once)"; continue
  fi
  break
done
