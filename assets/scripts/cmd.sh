#!/usr/bin/env bash
D="$(cd "$(dirname "$0")" && pwd)"
# cmd.sh <video> <comando> <args> <mark> [max] : escribe un slash-command en opencode, marca y maneja hasta que pida intervención
cd "${TUT_ROOT:-$PWD}"
"$D"/ty.py "$2" && sleep 1.5 && "$D"/ty.py " $3" && sleep 1 && xdotool key Return
"$D"/rec.sh mark "$1" "$4"; sleep 3
"$D"/drive.sh "${5:-3000}" | grep -v '^ERROR' | tail -4
"$D"/oclog.py --n 2 | cut -c1-900
