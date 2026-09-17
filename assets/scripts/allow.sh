#!/usr/bin/env bash
# allow.sh : responde "Allow always" + Confirm en el diálogo de permiso de opencode
# (el log avisa antes de que el diálogo se dibuje: esperar; Left/Right hacen wrap, no usar Left)
wmctrl -i -a ${OC_WIN:?definí OC_WIN con el id de ventana (wmctrl -l)}; sleep 2.5
xdotool key Right; sleep 0.9; xdotool key Return; sleep 1.5; xdotool key Return; sleep 0.8
