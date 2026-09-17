#!/usr/bin/env bash
# bot.sh <name> : captura solo la mitad inferior del panel de chat (donde aparecen permisos/preguntas)
S=${SHOTS:-/tmp/tutorial-shots}; mkdir -p $S
ffmpeg -y -loglevel error -f x11grab -video_size 1920x1080 -i :1 -frames:v 1 -vf "crop=1380:620:0:420,scale=690:-1" $S/$1.png && echo $S/$1.png
