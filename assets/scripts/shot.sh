#!/usr/bin/env bash
# shot.sh <name> [scale]  -> captura pantalla a scratchpad
S=${SHOTS:-/tmp/tutorial-shots}; mkdir -p $S
ffmpeg -y -loglevel error -f x11grab -video_size 1920x1080 -i "${DISPLAY:-:0}" -frames:v 1 -vf scale=${2:-960}:-1 $S/$1.png && echo $S/$1.png
