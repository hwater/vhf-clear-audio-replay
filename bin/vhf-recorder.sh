#!/bin/bash
# VOX-Mitschnitt: eine MP3 pro Funkspruch. Liest geteilt via 'vhf' (dsnoop+plug).
DEV="vhf"
DIR="/srv/music/VHF-Aufnahmen"
MINDUR=1.0        # kuerzere Schnipsel (Stoerblips) verwerfen
THRESH="3%"       # VOX-Schwelle (analog zum Live-Gate ~0.03)
TRAIL=1.5         # Sek. Stille bis Spruch als beendet gilt
MAXDUR=${VHF_MAXDUR:-90}   # Sicherheits-Limit: laenger = offener Squelch/Dauerstoerung -> verwerfen
# Stoerungs-Filter ueber Sprach-Rhythmus (Modulation der Huellkurve, gain-unabhaengig):
# Sprache liegt im Band MI_LO..MI_HI + mod4>=MOD4; Traeger/Rauschen ausserhalb.
# Werte im Log: /run/vhf/classify.log. Enger stellen = mehr Stoerungen fangen (aber
# Risiko echten Funk zu verlieren); weiter = sicherer, laesst mehr durch.
export VHF_MI_LO=0.55
export VHF_MI_HI=1.65
export VHF_MOD4=0.30
mkdir -p "$DIR"
echo "VHF-Recorder gestartet -> $DIR (thresh=$THRESH)"
while true; do
    ts=$(date +%Y-%m-%d_%H-%M-%S)
    wav="/tmp/vhf-rec-$ts.wav"
    # blockiert bis Sprache anliegt; nimmt auf; stoppt nach TRAIL Stille
    sox -q -t alsa "$DEV" -c 1 -r 44100 -b 16 "$wav" \
        highpass 250 lowpass 3400 \
        silence 1 0.1 "$THRESH" 1 "$TRAIL" "$THRESH" trim 0 "$MAXDUR" 2>/dev/null || { sleep 1; rm -f "$wav"; continue; }
    dur=$(soxi -D "$wav" 2>/dev/null || echo 0)
    # Limit erreicht? -> Dauer-Signal, kein normaler Funkspruch -> verwerfen
    if awk -v d="$dur" -v m="$MAXDUR" 'BEGIN{exit !(d>=m-0.5)}'; then
        echo "Dauer-Signal >= ${MAXDUR}s verworfen (Squelch offen / Dauerstoerung?)"
        rm -f "$wav"; sleep 1; continue
    fi
    if awk -v d="$dur" -v m="$MINDUR" 'BEGIN{exit !(d>=m)}'; then
        mp3="$DIR/VHF_${ts}.mp3"
        ffmpeg -hide_banner -loglevel error -y -i "$wav" -af "afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11" -ac 1 -c:a libmp3lame -b:a 96k "$mp3" 2>/dev/null
        echo "aufgenommen: $(basename "$mp3") (${dur}s)"
        # Im Hintergrund: klassifizieren. Echter Funk -> behalten (im Web-Replay
        # sichtbar). Stoerung -> verstecken (.noise-*, im Web ausklappbar).
        # OwnTone-/HomePod-Aufrufe nur, wenn das HomePod-Add-on installiert ist
        # (vhf-playout.sh vorhanden). Der Nachhoer-Kern laeuft ohne das Add-on.
        ( PLAYOUT=/usr/local/bin/vhf-playout.sh
          if /usr/local/bin/vhf-classify.py "$mp3"; then
              if [ -x "$PLAYOUT" ]; then
                  echo 0 > /run/vhf/mute   # eingehender echter Funk schaltet "Funk nachhoeren" aus
                  curl -s -X PUT "http://localhost:3689/api/update" >/dev/null 2>&1 || true
                  "$PLAYOUT" "$mp3"
              fi
          else
              mv -f "$mp3" "$DIR/.noise-VHF_${ts}.mp3"
              echo "aussortiert (Stoerung): VHF_${ts}.mp3"
              [ -x "$PLAYOUT" ] && curl -s -X PUT "http://localhost:3689/api/update" >/dev/null 2>&1 || true
          fi ) &
    fi
    rm -f "$wav"
done
