#!/usr/bin/env bash
# VHF clear Audio replay – Gesamt-Installation
# Nachhoer-Kern + Bedienpanel (:8090). HomePods nur mit --with-homepods
# (braucht OwnTone + manuelle Geraete-IDs). Jeder Schritt prueft vorab die
# Kompatibilitaet (Raspberry Pi / Linux / systemd).
#
#   sudo ./install-all.sh [--with-homepods] [--skip-deps] [--no-enable] [--force]
#
#   --with-homepods  auch das HomePod-/AirPlay-2-Add-on installieren
#   --skip-deps      apt-Paketinstallation ueberspringen (Kern)
#   --no-enable      Dienste nur installieren, nicht starten
#   --force          Kompatibilitaetswarnungen ignorieren
#   -h, --help       diese Hilfe
set -euo pipefail

WITH_HP=0; CORE_ARGS=(); ADDON_ARGS=()
for a in "$@"; do case "$a" in
  --with-homepods) WITH_HP=1 ;;
  --skip-deps)     CORE_ARGS+=(--skip-deps) ;;
  --no-enable)     CORE_ARGS+=(--no-enable); ADDON_ARGS+=(--no-enable) ;;
  --force)         CORE_ARGS+=(--force);     ADDON_ARGS+=(--force) ;;
  -h|--help)       sed -n '2,13p' "$0"; exit 0 ;;
  *) echo "Unbekannte Option: $a  (--help)"; exit 2 ;;
esac; done

if [ -t 1 ]; then C_B=$'\033[1m'; C_C=$'\033[36m'; C_0=$'\033[0m'; else C_B=; C_C=; C_0=; fi
step(){ printf '\n%s══ %s ══%s\n' "$C_B" "$*" "$C_0"; }
info(){ printf '  %sℹ%s %s\n' "$C_C" "$C_0" "$*"; }

[ "$(uname -s)" = "Linux" ] || { echo "Nur unter Linux (Raspberry Pi). Erkannt: $(uname -s)."; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "Bitte mit sudo ausfuehren."; exit 1; }
  exec sudo -E bash "$0" "$@"
fi

step "1) Nachhoer-Kern"
bash "$SRC/install.sh" ${CORE_ARGS[@]+"${CORE_ARGS[@]}"}

step "2) Bedienpanel (:8090)"
bash "$SRC/addons/control-panel/install.sh" ${ADDON_ARGS[@]+"${ADDON_ARGS[@]}"}

if [ "$WITH_HP" -eq 1 ]; then
  step "3) HomePods-Add-on"
  bash "$SRC/addons/homepods/install.sh" ${ADDON_ARGS[@]+"${ADDON_ARGS[@]}"}
else
  step "3) HomePods-Add-on – ausgelassen"
  info "Mit --with-homepods mitinstallieren (setzt OwnTone + Geraete-IDs voraus)."
fi

step "Gesamt-Installation fertig"
info "Panel:      http://$(hostname).local:8090/"
info "Nachhoeren: http://$(hostname).local:8088/"
