#!/bin/bash
# Meldet die NETZ-Erreichbarkeit der HomePods (v4+v6 AirPlay-Port 7000) nach
# /run/vhf/pods-net {"bb":0/1,"sb":0/1,"ts":...} fuers Panel.
# KEIN Auto-Restart von OwnTone mehr: die HomePods schlafen und antworten nur auf
# echtes AirPlay (nicht auf TCP-Proben) -> OwnTone listet sie mal (nicht), und ein
# Neustart bei jeder Abwesenheit fuehrte zur Restart-Schleife + Ton-Ausfall. OwnTone
# entdeckt die Pods selbst wieder; ein manueller `systemctl restart owntone` reicht
# im seltenen Haenger-Fall.
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
prev=""
while true; do
    bb=0; sb=0
    reachable ShiPod-BB.local && bb=1
    reachable ShiPod-SB.local && sb=1
    echo "{\"bb\":$bb,\"sb\":$sb,\"ts\":$(date +%s)}" > "$NET"

    if [ "$bb$sb" != "$prev" ]; then
        logger -t vhf-podwatch "HomePods Netz-Erreichbarkeit: BB=$bb SB=$sb"
        prev="$bb$sb"
    fi
    sleep 20
done
