#!/usr/bin/env bash
# VHF clear Audio replay – Gesamt-Deinstallation
# Entfernt HomePods-Add-on, Bedienpanel und Nachhoer-Kern (in dieser Reihenfolge).
# Aufnahmen/Einstellungen bleiben, ausser mit --purge.
#
#   sudo ./uninstall-all.sh [--purge] [--force]
#
#   --purge     zusaetzlich Aufnahmen (/srv/music/VHF-Aufnahmen), /etc/vhf, /var/lib/vhf loeschen
#   --force     nicht nachfragen
#   -h, --help  diese Hilfe
set -euo pipefail

PURGE=0; FORCE=0
for a in "$@"; do case "$a" in
  --purge) PURGE=1 ;;
  --force) FORCE=1 ;;
  -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
  *) echo "Unbekannte Option: $a  (--help)"; exit 2 ;;
esac; done

if [ -t 1 ]; then C_B=$'\033[1m'; C_R=$'\033[31m'; C_0=$'\033[0m'; else C_B=; C_R=; C_0=; fi
step(){ printf '\n%s══ %s ══%s\n' "$C_B" "$*" "$C_0"; }

[ "$(uname -s)" = "Linux" ] || { echo "Nur unter Linux ausfuehren. Erkannt: $(uname -s)."; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "Bitte mit sudo ausfuehren."; exit 1; }
  exec sudo -E bash "$0" "$@"
fi

if [ "$FORCE" -eq 0 ]; then
  printf 'Entfernt HomePods-Add-on, Bedienpanel und Nachhoer-Kern.\n'
  [ "$PURGE" -eq 1 ] && printf '%sAchtung: --purge loescht auch Aufnahmen, /etc/vhf und /var/lib/vhf.%s\n' "$C_R" "$C_0"
  printf 'Fortfahren? [j/N] '
  read -r ans || ans=""
  case "$ans" in j|J|y|Y) ;; *) echo "Abgebrochen."; exit 0 ;; esac
fi
PURGE_ARG=(); [ "$PURGE" -eq 1 ] && PURGE_ARG=(--purge)

step "1) HomePods-Add-on"
bash "$SRC/addons/homepods/uninstall.sh" --force ${PURGE_ARG[@]+"${PURGE_ARG[@]}"}

step "2) Bedienpanel (:8090)"
bash "$SRC/addons/control-panel/uninstall.sh" --force

step "3) Nachhoer-Kern"
bash "$SRC/uninstall.sh" --force ${PURGE_ARG[@]+"${PURGE_ARG[@]}"}

step "Gesamt-Deinstallation abgeschlossen"
