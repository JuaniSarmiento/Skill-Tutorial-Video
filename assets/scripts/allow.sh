#!/usr/bin/env bash
# allow.sh [--always] : responde el diálogo de permiso de opencode.
#
# Por defecto "Allow once". La versión original apretaba SIEMPRE "Allow always", así que
# un falso negativo del filtro no aprobaba un comando: habilitaba una categoría entera
# para el resto de la sesión, sin que volvieras a ver un diálogo.
# (el log avisa antes de que el diálogo se dibuje: esperar; Left/Right hacen wrap, no usar Left)
wmctrl -i -a ${OC_WIN:?definí OC_WIN con el id de ventana (wmctrl -l)}; sleep 2.5
if [ "${1:-}" = "--always" ]; then
  xdotool key Right; sleep 0.9        # Right = "Allow always"
else
  :                                   # sin mover = "Allow once", la opción por defecto
fi
xdotool key Return; sleep 1.5; xdotool key Return; sleep 0.8
