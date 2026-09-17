#!/usr/bin/env bash
# answer.sh <idx> [idx...] : responde las preguntas del diálogo question de opencode (índices 1-based) y confirma
wmctrl -i -a ${OC_WIN:?definí OC_WIN con el id de ventana (wmctrl -l)}; sleep 2.5
for i in "$@"; do
  for _ in $(seq 2 "$i"); do xdotool key Down; sleep 0.4; done
  sleep 0.6; xdotool key Return; sleep 1.2
done
xdotool key Return; sleep 0.8
