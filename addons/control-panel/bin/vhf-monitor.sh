#!/bin/bash
# Latenzarmer Live-Monitor: VHF (dsnoop 'vhf') -> Sprachband + VOX-Gate
# -> direkt auf den C-Media-Ausgang (card 3). Kein AirPlay, ~100 ms.
THRESH=0.04; RANGE=0.001; RATIO=9; ATTACK=5; RELEASE=250
MAKEUP=2; HP=200; LP=3500
OUT="plughw:3,0"
echo "VHF-Monitor(live, gated) -> $OUT"
/usr/bin/ffmpeg -hide_banner -loglevel warning -nostats \
    -f alsa -ac 1 -i vhf \
    -af "highpass=f=${HP},lowpass=f=${LP},agate=threshold=${THRESH}:range=${RANGE}:ratio=${RATIO}:attack=${ATTACK}:release=${RELEASE}:makeup=${MAKEUP},alimiter=limit=0.95" \
    -ar 44100 -ac 2 -f s16le -flush_packets 1 pipe:1 \
  | /usr/bin/aplay -q -D "$OUT" -f S16_LE -r 44100 -c 2
