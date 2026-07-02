#!/bin/bash
# Spielt EINEN Funk-Clip auf den Messe-Ausgang (ALSA 'vhfoutplug', dmix auf der
# C-Media-Karte). Wird vom Panel genutzt, wenn KEINE HomePods an Bord sind
# (dann tritt dieses Skript an die Stelle von vhf-playout.sh).
#   - nur eine Wiedergabe gleichzeitig (flock)
#   - setzt /run/vhf/playing (Basename) fuers VU-Overlay im Panel
#   - Lautstaerke steuert der ALSA-Mixer 'Speaker' (Messe-Regler im Panel)
mp3="$1"
[ -f "$mp3" ] || exit 0
mkdir -p /run/vhf
exec 9>/run/vhf/messe-play.lock
flock -n 9 || exit 0                      # laeuft schon eine Wiedergabe -> raus

base=$(basename "$mp3")
echo "${base%.mp3}" > /run/vhf/playing
cleanup(){ rm -f /run/vhf/playing; }
trap cleanup EXIT
trap 'cleanup; exit' INT TERM

ffmpeg -hide_banner -loglevel error -i "$mp3" -f s16le -ar 44100 -ac 2 - 2>/dev/null \
  | aplay -q -D vhfoutplug -f S16_LE -r 44100 -c 2 2>/dev/null
