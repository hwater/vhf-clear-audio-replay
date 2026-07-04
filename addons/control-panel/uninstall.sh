#!/usr/bin/env bash
# Add-on Bedienpanel (:8090) – Deinstallation
# Stoppt/entfernt Panel, Live-Monitor, Pegelmessung und Messe-Helfer.
#
#   sudo ./addons/control-panel/uninstall.sh [--force]
#
#   --force       (nur der Einheitlichkeit halber; fragt ohnehin nicht nach)
#   -h, --help    diese Hilfe
set -euo pipefail

for a in "$@"; do case "$a" in
  --force) : ;;
  -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
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

step "Bedienpanel (:8090) entfernen"
systemctl disable --now vhf-control vhf-level vhf-monitor 2>/dev/null || true
rm -f /etc/systemd/system/vhf-control.service \
      /etc/systemd/system/vhf-level.service \
      /etc/systemd/system/vhf-monitor.service
systemctl daemon-reload
systemctl reset-failed vhf-control vhf-level vhf-monitor 2>/dev/null || true
rm -f /usr/local/bin/vhf-control.py /usr/local/bin/vhf-level.py \
      /usr/local/bin/vhf-monitor.sh /usr/local/bin/vhf-messe-play.sh
ok "Panel-Dienste und -Programme entfernt."
info "/etc/vhf/vhf.conf bleibt (wird auch vom Nachhoer-Kern genutzt)."
