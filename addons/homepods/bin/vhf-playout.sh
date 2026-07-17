#!/bin/bash
# VHF-Uebernahme via pyatv (RAOP) — spielt EINEN Funk-Clip auf die ShiPods (HomePods)
# und ueberlaesst sie sonst der iPhone-/Mac-Musik.
#
# ERSATZ fuer den frueheren OwnTone-Weg: OwnTone (v29.x) crasht/hangt beim
# AirPlay-Streaming zu genau diesen HomePods (bekannte upstream-Bugs, Stereopaar als
# Einzelgeraete -> AirPlay-1). pyatv streamt direkt per RAOP, ohne OwnTone -> stabil.
# Dual-Mono: beide Pods bekommen parallel denselben Clip (fuer Funksprache ok).
#
# Aufruf: vhf-playout.sh <mp3> [now]     ("now" = sofort, ohne Delay/Mute)
# Braucht pyatv im venv unter /opt/pyatv-venv (siehe docs/addons-homepods).
ATV=/opt/pyatv-venv/bin/atvremote
BB=FE:A2:7C:85:A9:5C      # ShiPod BB  (pyatv/AirPlay-Identifier, aus `atvremote scan`)
SB=A2:AE:9B:32:35:0A      # ShiPod SB
VOL=$(cat /var/lib/vhf/hpvol 2>/dev/null || echo 40)   # Panel-Regler (0..100)
mp3="$1"
MODE="$2"
[ -f "$mp3" ] || exit 0
[ -x "$ATV" ] || { echo "pyatv fehlt ($ATV)"; exit 0; }

if [ "$MODE" != "now" ]; then
    # Stummschaltung: Funk wird aufgenommen + im VU angezeigt, aber NICHT uebernommen.
    [ "$(cat /run/vhf/mute 2>/dev/null)" = "1" ] && exit 0
    DELAY=$(cat /var/lib/vhf/delay 2>/dev/null || echo 7)   # einstellbare Verzoegerung
    sleep "$DELAY" 2>/dev/null || sleep 7
    [ "$(cat /run/vhf/mute 2>/dev/null)" = "1" ] && exit 0  # waehrend Wartezeit gemutet?
fi

# nur EINE Uebernahme gleichzeitig
exec 9>/run/vhf/playout.lock
flock -n 9 || exit 0

base=$(basename "$mp3"); base="${base%.mp3}"
mkdir -p /run/vhf; echo "$base" > /run/vhf/playing   # Flag fuers VU-Overlay im Panel

kids=""
cleanup(){ [ -n "$kids" ] && kill $kids 2>/dev/null; rm -f /run/vhf/playing; }
trap cleanup EXIT
trap 'cleanup; exit' INT TERM

# Parallel auf beide Pods streamen; Lautstaerke in derselben Session vor dem Clip setzen.
"$ATV" --id "$BB" set_volume="$VOL" stream_file="$mp3" >/dev/null 2>&1 & kids="$kids $!"
"$ATV" --id "$SB" set_volume="$VOL" stream_file="$mp3" >/dev/null 2>&1 & kids="$kids $!"
wait
