#!/bin/bash
# Ueberwacht die NETZ-Erreichbarkeit der HomePods (das war die Ausfallursache:
# Pods faller aus dem WLAN -> OwnTone sieht sie als "not connectable").
#  - schreibt /run/vhf/pods-net  {"bb":0/1,"sb":0/1,"ts":...}  fuers Panel
#  - selbstheilend: sind beide erreichbar, aber OwnTone hat sie nicht (oder OwnTones
#    HTTP-API haengt) -> OwnTone EINMAL neu starten (Cooldown 5 min, kein Dauer-Restart)
O=http://localhost:3689
NET=/run/vhf/pods-net
mkdir -p /run/vhf
# WLAN-Interface fuer IPv6-Link-Local-Zone (fe80::...%IFACE); auto, sonst wlan0.
IFACE="${VHF_IFACE:-$(ip -o -4 route show to default 2>/dev/null | awk '{print $5; exit}')}"
IFACE="${IFACE:-wlan0}"

reachable(){ # AirPlay-Port 7000 ueber IPv4 ODER IPv6 (HomePods sind oft nur v6 erreichbar!)
    local h="$1" ip
    ip=$(avahi-resolve -4 -n "$h" 2>/dev/null | awk '{print $2}')
    [ -n "$ip" ] && timeout 2 bash -c "echo >/dev/tcp/$ip/7000" 2>/dev/null && return 0
    ip=$(avahi-resolve -6 -n "$h" 2>/dev/null | awk '{print $2}')
    [ -n "$ip" ] || return 1
    case "$ip" in fe80:*) ip="$ip%$IFACE";; esac   # link-local braucht Zone
    timeout 2 bash -c "echo >/dev/tcp/$ip/7000" 2>/dev/null
}
# WICHTIG: Timeout am curl! Ohne --max-time blockiert dieser Aufruf endlos, wenn
# OwnTones API haengt (accepted, aber keine Antwort) -> die ganze Schleife friert ein
# und heilt nie. Mit Timeout liefert er "0" -> Selbstheilung greift auch beim API-Haenger.
shipods_count(){ curl -s --connect-timeout 3 --max-time 5 "$O/api/outputs" \
    | python3 -c "import sys,json;print(sum(1 for o in json.load(sys.stdin).get('outputs',[]) if o['name'].startswith('ShiPod')))" 2>/dev/null || echo 0; }

prev=""; last_restart=0
while true; do
    bb=0; sb=0
    reachable ShiPod-BB.local && bb=1
    reachable ShiPod-SB.local && sb=1
    echo "{\"bb\":$bb,\"sb\":$sb,\"ts\":$(date +%s)}" > "$NET"

    if [ "$bb$sb" != "$prev" ]; then
        logger -t vhf-podwatch "HomePods Netz-Erreichbarkeit: BB=$bb SB=$sb"
        prev="$bb$sb"
    fi

    # Selbstheilung: beide im Netz, aber OwnTone hat sie nicht -> neu erkennen
    if [ "$bb" = 1 ] && [ "$sb" = 1 ] && [ "$(shipods_count)" != "2" ]; then
        now=$(date +%s)
        if [ $((now - last_restart)) -gt 300 ]; then
            logger -t vhf-podwatch "Pods erreichbar, aber nicht in OwnTone -> restart owntone"
            systemctl restart owntone
            last_restart=$now
            sleep 25
        fi
    fi
    sleep 20
done
