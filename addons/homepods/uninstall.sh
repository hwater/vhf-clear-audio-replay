#!/usr/bin/env bash
# Add-on HomePod-/AirPlay-2-Ausgabe – Deinstallation
# Stoppt/entfernt Playout/ShiPods/Podwatch. Einstellungen bleiben, ausser --purge.
#
#   sudo ./addons/homepods/uninstall.sh [--purge] [--force]
#
#   --purge       zusaetzlich /var/lib/vhf (delay/hpvol) loeschen
#   --force       (nur Einheitlichkeit; fragt ohnehin nicht nach)
#   -h, --help    diese Hilfe
set -euo pipefail

PURGE=0
for a in "$@"; do case "$a" in
  --purge) PURGE=1 ;;
  --force) : ;;
  -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
  *) echo "Unbekannte Option: $a  (--help)"; exit 2 ;;
esac; done

if [ -t 1 ]; then C_G=$'\033[32m'; C_C=$'\033[36m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else C_G=; C_C=; C_Y=; C_R=; C_B=; C_0=; fi
ok(){ printf '  %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
info(){ printf '  %sℹ%s %s\n' "$C_C" "$C_0" "$*"; }
err(){ printf '  %s✗%s %s\n' "$C_R" "$C_0" "$*" >&2; }
step(){ printf '\n%s%s%s\n' "$C_B" "$*" "$C_0"; }
die(){ err "$*"; exit 1; }

[ "$(uname -s)" = "Linux" ] || die "Nur unter Linux ausfuehren. Erkannt: $(uname -s)."
command -v systemctl >/dev/null 2>&1 || die "systemd (systemctl) nicht gefunden."
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "Bitte als root bzw. mit sudo ausfuehren."
  exec sudo -E bash "$0" "$@"
fi

step "HomePods-Add-on entfernen"
systemctl disable --now vhf-shipods.timer vhf-podwatch 2>/dev/null || true
systemctl stop vhf-shipods.service 2>/dev/null || true
rm -f /etc/systemd/system/vhf-shipods.service \
      /etc/systemd/system/vhf-shipods.timer \
      /etc/systemd/system/vhf-podwatch.service
systemctl daemon-reload
systemctl reset-failed vhf-shipods vhf-podwatch 2>/dev/null || true
rm -f /usr/local/bin/vhf-playout.sh /usr/local/bin/vhf-shipods.sh /usr/local/bin/vhf-podwatch.sh
ok "HomePod-Dienste und -Programme entfernt (Recorder ueberspringt die Uebernahme wieder)."

if [ "$PURGE" -eq 1 ]; then
  rm -rf /var/lib/vhf
  ok "/var/lib/vhf (delay/hpvol) geloescht."
else
  info "/var/lib/vhf (delay/hpvol) bleibt. (--purge entfernt es)"
fi
