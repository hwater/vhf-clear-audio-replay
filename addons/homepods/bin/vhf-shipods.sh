#!/bin/bash
# Haelt die ShiPods als OwnTone-Ausgang ausgewaehlt UND meldet Zustandswechsel.
# Pro ShiPod: ok (da+gewaehlt) / reselected (war abgewaehlt -> neu gewaehlt) /
# missing (nicht in OwnTone -> HomePod offline/Netz). Aenderungen -> journal +
# /run/vhf/shipods.state (Panel liest den Live-Zustand direkt aus OwnTone).
O=http://localhost:3689
STATE=/run/vhf/shipods.state
mkdir -p /run/vhf
outs=$(curl -s "$O/api/outputs" 2>/dev/null) || exit 0
declare -A NAME=([279973827291484]="ShiPod BB" [178870811768074]="ShiPod SB")
new=""
for id in 279973827291484 178870811768074; do
    s=$(echo "$outs" | python3 -c "import sys,json;d=json.load(sys.stdin);print(next((o['selected'] for o in d['outputs'] if o['id']=='$id'),'missing'))" 2>/dev/null || echo err)
    if [ "$s" = "missing" ]; then
        new="$new ${NAME[$id]}=FEHLT"
    elif [ "$s" = "False" ]; then
        curl -s -X PUT "$O/api/outputs/$id" -d '{"selected":true}' >/dev/null
        new="$new ${NAME[$id]}=neu-gewaehlt"
    else
        new="$new ${NAME[$id]}=ok"
    fi
done
prev=$(cat "$STATE" 2>/dev/null)
if [ "$new" != "$prev" ]; then
    echo "ShiPod-Status geaendert:$new (vorher:${prev:-?})"
    echo "$new" > "$STATE"
fi
