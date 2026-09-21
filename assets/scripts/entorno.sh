#!/usr/bin/env bash
# entorno.sh start|chrome|stop|status : X11 anidado para grabar bajo Wayland
#
# POR QUÉ: bajo Wayland (COSMIC/GNOME modernos) x11grab captura NEGRO y xdotool/wmctrl
# no ven las ventanas nativas. Xephyr levanta un X11 real dentro de una ventana: ahí
# adentro la skill funciona sin cambios.
set -uo pipefail
DISP="${TUT_DISPLAY:-:2}"
GEOM="${TUT_GEOM:-1920x1080}"

# matar por ejecutable, NUNCA `pkill -f <patrón>`: el patrón aparece en la cmdline de
# este propio script y se mata a sí mismo (exit 144).
kill_by_exe() {
  local pat="$1" exe
  for p in $(pgrep -f "$pat" 2>/dev/null); do
    exe=$(readlink -f "/proc/$p/exe" 2>/dev/null) || continue
    case "$exe" in *"$2"*) kill "$p" 2>/dev/null ;; esac
  done
}

case "${1:-status}" in
  start)
    pkill -x Xephyr 2>/dev/null; pkill -x openbox 2>/dev/null; sleep 1
    setsid Xephyr "$DISP" -screen "$GEOM" -title "GRABACION-TUTORIAL" \
      </dev/null >/tmp/xephyr.log 2>&1 &
    sleep 3
    xdpyinfo -display "$DISP" >/dev/null 2>&1 || { echo "FALLO Xephyr"; tail -5 /tmp/xephyr.log; exit 1; }
    setsid env DISPLAY="$DISP" openbox </dev/null >/tmp/openbox.log 2>&1 &
    sleep 2
    # layout único: con us,latam,us xdotool escribe @ en vez de "
    DISPLAY="$DISP" setxkbmap -layout latam 2>/dev/null
    # kitty y alacritty NO sirven: exigen OpenGL 3.3 y Xephyr no da GPU (el proceso
    # vive pero nunca crea ventana). xterm no usa GPU.
    cols=$(( ${GEOM%x*} / 10 - 2 )); rows=$(( ${GEOM#*x} / 20 - 1 ))
    setsid env DISPLAY="$DISP" xterm -fa 'Monospace' -fs 16 -bg black -fg white \
      -geometry "${cols}x${rows}+0+0" +sb </dev/null >/tmp/xterm.log 2>&1 &
    sleep 3
    win=$(DISPLAY="$DISP" xdotool search --onlyvisible --class xterm 2>/dev/null | head -1)
    printf 'ok  DISPLAY=%s  %s\n' "$DISP" "$GEOM"
    printf '    export DISPLAY=%s\n' "$DISP"
    [ -n "$win" ] && printf '    export OC_WIN=0x%08x\n' "$win"
    ;;
  chrome)
    shift
    url="${1:-about:blank}"
    # El popup de Google Translate NO se apaga con --disable-features (cambió de nombre):
    # hay que desactivarlo en las preferencias del perfil, antes de lanzar.
    mkdir -p /tmp/chrome-tutorial/Default
    python3 - <<'PREF'
import json, pathlib
f = pathlib.Path("/tmp/chrome-tutorial/Default/Preferences")
d = {}
if f.exists():
    try: d = json.loads(f.read_text())
    except Exception: d = {}
d.setdefault("translate", {})["enabled"] = False
d["translate_blocked_languages"] = ["en", "es"]
d.setdefault("browser", {})["has_seen_welcome_page"] = True
d.setdefault("profile", {})["exit_type"] = "Normal"
f.write_text(json.dumps(d))
PREF
    # CLAVE: bajo Wayland, Chrome ignora DISPLAY y abre en Ozone/Wayland (o sea, en el
    # escritorio real, no en Xephyr). Hay que forzar x11 Y limpiar WAYLAND_DISPLAY.
    setsid env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE DISPLAY="$DISP" \
      google-chrome --ozone-platform=x11 --disable-gpu \
      --user-data-dir=/tmp/chrome-tutorial --no-first-run --no-default-browser-check \
      --disable-features=Translate,TranslateUI --disable-infobars --hide-crash-restore-bubble \
      --window-position=0,0 --window-size="${GEOM%x*},${GEOM#*x}" --start-maximized \
      "$url" </dev/null >/tmp/chrome.log 2>&1 &
    sleep 15
    w=$(DISPLAY="$DISP" xdotool search --onlyvisible --name 'Google Chrome' 2>/dev/null | head -1)
    if [ -n "$w" ]; then
      DISPLAY="$DISP" wmctrl -i -r "$w" -b add,maximized_vert,maximized_horz 2>/dev/null
      printf 'ok  chrome  win=0x%08x\n' "$w"
    else
      echo "chrome no abrió ventana; ver /tmp/chrome.log"; exit 1
    fi
    ;;
  stop)
    kill_by_exe chrome-tutorial chrome
    pkill -x xterm 2>/dev/null; pkill -x openbox 2>/dev/null; pkill -x Xephyr 2>/dev/null
    sleep 1; echo "entorno bajado"
    ;;
  status)
    pgrep -x Xephyr >/dev/null && echo "Xephyr  ARRIBA ($DISP)" || echo "Xephyr  abajo"
    pgrep -x openbox >/dev/null && echo "openbox ARRIBA" || echo "openbox abajo"
    if xdpyinfo -display "$DISP" >/dev/null 2>&1; then
      echo "ventanas en $DISP:"
      DISPLAY="$DISP" xdotool search --onlyvisible --name '.' 2>/dev/null | while read -r w; do
        printf '  0x%08x  %s\n' "$w" "$(DISPLAY=$DISP xdotool getwindowname "$w" 2>/dev/null)"
      done
    fi
    ;;
  *) sed -n '2,6p' "$0" ;;
esac
