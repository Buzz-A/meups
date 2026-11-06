#!/bin/bash
# check.sh video.mp4 out.jpg t1 t2 ... -> tira de frames 270x480 com linhas de margem (285/1635)
v=$1; o=$2; shift 2; i=0; fs=()
for t in "$@"; do ffmpeg -v error -y -ss $t -i "$v" -frames:v 1 -vf "drawbox=y=285:w=iw:h=3:color=lime:t=fill,drawbox=y=1635:w=iw:h=3:color=lime:t=fill,scale=270:480" /tmp/claude-0/ck_$i.png; fs+=(/tmp/claude-0/ck_$i.png); i=$((i+1)); done
ffmpeg -v error -y $(for f in "${fs[@]}"; do echo -i $f; done) -filter_complex "hstack=inputs=${#fs[@]}" "$o"
