#!/bin/bash
# VHF-Uebernahme: spielt EINEN Funk-Clip kurz auf die ShiPods (HomePods) und
# gibt sie danach wieder frei. So greift der Pi die HomePods nur fuer echten
# Funk und ueberlaesst sie sonst der iPhone-Musik.
#   auswaehlen + eingestellte Lautstaerke -> abspielen -> warten -> stop -> abwaehlen
O=http://localhost:3689
BB=279973827291484
SB=178870811768074
VOL=$(cat /var/lib/vhf/hpvol 2>/dev/null || echo 60)
mp3="$1"
MODE="$2"          # "now" = Funkwiederholung: sofort, ohne Delay, auch bei Stumm
[ -f "$mp3" ] || exit 0

if [ "$MODE" != "now" ]; then
    # Stummschaltung: Funk wird aufgenommen + im VU-Meter angezeigt, aber NICHT
    # auf die HomePods uebernommen.
    [ "$(cat /run/vhf/mute 2>/dev/null)" = "1" ] && exit 0
    # einstellbare Verzoegerung vor der Uebernahme (Default 7s, Panel-Slider)
    DELAY=$(cat /var/lib/vhf/delay 2>/dev/null || echo 7)
    sleep "$DELAY" 2>/dev/null || sleep 7
    [ "$(cat /run/vhf/mute 2>/dev/null)" = "1" ] && exit 0   # waehrend Wartezeit gemutet?
fi

DIR=$(dirname "$mp3")
orig=$(basename "$mp3")
TMP=""
if [[ "$orig" == .noise-* ]]; then
    # verworfene (versteckte) Aufnahme: sichtbare Temp-Kopie, damit OwnTone sie findet
    TMP="$DIR/tmpreplay_$$.mp3"
    cp -f "$mp3" "$TMP"
    curl -s -X PUT "$O/api/update" >/dev/null
    base="tmpreplay_$$"
else
    base="${orig%.mp3}"
fi

cleanup(){ rm -f /run/vhf/playing
    [ -n "$TMP" ] && { rm -f "$TMP"; curl -s -X PUT "$O/api/update" >/dev/null 2>&1; }; }
trap cleanup EXIT
trap 'cleanup; exit' INT TERM

# nur eine Uebernahme gleichzeitig
exec 9>/run/vhf/playout.lock
flock 9

# frisch aufgenommene Datei ist evtl. noch nicht indexiert -> kurz retrien
ID=""
for try in $(seq 1 12); do
    ID=$(curl -s "$O/api/search?type=tracks&expression=path%20includes%20%22${base}%22" \
         | python3 -c "import sys,json;i=json.load(sys.stdin)['tracks']['items'];print(i[0]['id'] if i else '')" 2>/dev/null)
    [ -n "$ID" ] && break
    sleep 0.5
done
[ -z "$ID" ] && exit 0

# Busy-Flag fuers Panel (Spinner); cleanup-Trap (oben) entfernt es + die Temp-Kopie
echo "$base" > /run/vhf/playing

# ShiPods greifen + Lautstaerke setzen, Clip abspielen
for id in $BB $SB; do
    curl -s -X PUT "$O/api/outputs/$id" -d "{\"selected\":true,\"volume\":$VOL}" >/dev/null
done
curl -s -X POST "$O/api/queue/items/add?uris=library:track:$ID&playback=start&clear=true" >/dev/null
curl -s -X PUT "$O/api/player/play" >/dev/null

# warten bis der Clip durch ist (Sicherheits-Cap 90s)
sleep 1
for i in $(seq 1 178); do
    st=$(curl -s "$O/api/player" | python3 -c "import sys,json;print(json.load(sys.stdin)['state'])" 2>/dev/null)
    [ "$st" = "stop" ] && break
    sleep 0.5
done

# HomePods wieder freigeben (iPhone kann weiter)
curl -s -X PUT "$O/api/player/stop" >/dev/null
for id in $BB $SB; do
    curl -s -X PUT "$O/api/outputs/$id" -d '{"selected":false}' >/dev/null
done
