#!/bin/bash
# VHF-Uebernahme (HomePods) — schlanker Client: reicht den Clip an den residenten
# pyatv-Daemon `vhf-playd` weiter (der haelt pyatv warm -> schneller Ton-Start).
# Interface unveraendert: vhf-playout.sh <mp3> [now]   ("now" = sofort, ohne Delay/Mute).
# Der Daemon uebernimmt Mute/Delay/Einmal-Wiedergabe und setzt /run/vhf/playing.
mp3="$1"
MODE="${2:-auto}"
[ -f "$mp3" ] || exit 0
mkdir -p /run/vhf
# atomar schreiben, damit der Daemon nie eine halbe Zeile liest
printf '%s\t%s\n' "$MODE" "$mp3" > /run/vhf/playreq.tmp && mv -f /run/vhf/playreq.tmp /run/vhf/playreq
