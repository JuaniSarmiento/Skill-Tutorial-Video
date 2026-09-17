#!/usr/bin/env bash
D="$(cd "$(dirname "$0")" && pwd)"
set -u
R="$D/rec.sh"; N=v01-active-stack
W=0x036000ac
dn(){ for i in $(seq 1 $1); do xdotool key Down; sleep 0.035; done; }
go(){ xdotool key ctrl+l; sleep 0.3; xdotool type --delay 6 "$1"; xdotool key Return; sleep 4; xdotool mousemove 60 600 click 1; xdotool mousemove 1915 600; }
wmctrl -i -a $W; sleep 0.5
go https://github.com/Group-Active-IA/active-stack; xdotool key Home; sleep 1
$R start $N; sleep 1
$R mark $N "p00 home del repo"; sleep 7
for p in $(seq 1 22); do dn 14; sleep 0.4; $R mark $N "p$(printf %02d $p) readme"; sleep 8; done
go https://github.com/Group-Active-IA/active-stack/blob/main/internal/catalog/harnesses.yaml
$R mark $N "p30 harnesses.yaml"; sleep 7
dn 14; sleep 0.4; $R mark $N "p31 harnesses.yaml scroll"; sleep 7
go https://github.com/Group-Active-IA/active-stack/releases
$R mark $N "p40 releases"; sleep 8
$R stop $N
