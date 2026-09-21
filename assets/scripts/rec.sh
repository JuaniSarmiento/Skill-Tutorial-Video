#!/usr/bin/env bash
# rec.sh start <name> | mark <name> <texto> | stop <name>
set -euo pipefail
export LC_NUMERIC=C
ROOT="${TUT_ROOT:-$PWD}/raw"; mkdir -p "$ROOT"
cmd=$1; name=$2
case $cmd in
  start)
    date +%s.%N > "$ROOT/$name.t0"
    : > "$ROOT/$name.marks"
    setsid ffmpeg -y -loglevel error -f x11grab -framerate 30 -video_size 1920x1080 -draw_mouse 0 -i "${DISPLAY:-:0}" \
      -c:v libx264 -preset ultrafast -crf 20 -pix_fmt yuv420p "$ROOT/$name.mkv" </dev/null >"$ROOT/$name.log" 2>&1 &
    # OJO: $! es el pid de setsid, NO el de ffmpeg. Si setsid forkea, matar $! deja
    # a ffmpeg huérfano grabando para siempre. Buscamos el ffmpeg real por su archivo.
    sleep 1
    real=$(pgrep -f "x11grab.*$name\\.mkv" | head -1)
    echo "${real:-$!}" > "$ROOT/$name.pid"; echo "rec $name pid $(cat "$ROOT/$name.pid")";;
  mark)
    t0=$(cat "$ROOT/$name.t0"); now=$(date +%s.%N)
    printf '%.1f\t%s\n' "$(echo "$now - $t0" | bc)" "${*:3}" >> "$ROOT/$name.marks"; tail -1 "$ROOT/$name.marks";;
  stop)
    kill -INT "$(cat "$ROOT/$name.pid")" 2>/dev/null || true; sleep 2
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$ROOT/$name.mkv";;
esac
