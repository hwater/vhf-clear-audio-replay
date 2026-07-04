#!/usr/bin/env bash
# Add-on HomePod-/AirPlay-2-Ausgabe – Installation
# Installiert Playout/ShiPods/Podwatch + Dienste. Setzt OwnTone voraus.
#
#   sudo ./addons/homepods/install.sh [--no-enable] [--force]
#
#   --no-enable   Dienste nur installieren, nicht starten
#   --force       Warnungen (z. B. OwnTone fehlt) ignorieren
#   -h, --help    diese Hilfe
set -euo pipefail

NO_ENABLE=0; FORCE=0
for a in "$@"; do case "$a" in
  --no-enable) NO_ENABLE=1 ;;
  --force) FORCE=1 ;;
  -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
  *) echo "Unbekannte Option: $a  (--help)"; exit 2 ;;
esac; done

if [ -t 1 ]; then C_G=$'\033[32m'; C_C=$'\033[36m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else C_G=; C_C=; C_Y=; C_R=; C_B=; C_0=; fi
ok(){ printf '  %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
info(){ printf '  %sℹ%s %s\n' "$C_C" "$C_0" "$*"; }
warn(){ printf '  %s!%s %s\n' "$C_Y" "$C_0" "$*"; }
err(){ printf '  %s✗%s %s\n' "$C_R" "$C_0" "$*" >&2; }
step(){ printf '\n%s%s%s\n' "$C_B" "$*" "$C_0"; }
die(){ err "$*"; exit 1; }

SRC="$(cd "$(dirname "$0")" && pwd)"
[ -d "$SRC/bin" ] && [ -d "$SRC/systemd" ] || die "bin/ oder systemd/ fehlt neben install.sh."

# --- Kompatibilitaet / Voraussetzungen (vor sudo) ----------------------------
step "HomePods-Add-on – Kompatibilitaetscheck"
[ "$(uname -s)" = "Linux" ] || die "Nur unter Linux (Raspberry Pi). Erkannt: $(uname -s)."
command -v systemctl >/dev/null 2>&1 || die "systemd (systemctl) nicht gefunden."
ok "Linux + systemd"
if systemctl list-unit-files 2>/dev/null | grep -q '^owntone' || [ -e /etc/owntone.conf ]; then
  ok "OwnTone erkannt."
else
  warn "OwnTone nicht gefunden – Voraussetzung fuer die AirPlay-2-Ausgabe (docs/addons-homepods.de.md)."
  [ "$FORCE" -eq 1 ] || die "Abbruch. Erst OwnTone einrichten oder mit --force fortfahren."
fi
[ -x /usr/local/bin/vhf-recorder.sh ] || warn "Recorder nicht gefunden – Playout wird nicht automatisch aufgerufen (zuerst Haupt-install.sh)."

# --- Root --------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "Bitte als root bzw. mit sudo ausfuehren."
  exec sudo -E bash "$0" "$@"
fi

# --- Programme ---------------------------------------------------------------
step "Programme nach /usr/local/bin"
install -m755 "$SRC"/bin/*.sh /usr/local/bin/
ok "vhf-playout.sh, vhf-shipods.sh, vhf-podwatch.sh"

# --- Laufzeit-Defaults -------------------------------------------------------
step "Einstellungen /var/lib/vhf"
install -d -m755 /var/lib/vhf
[ -e /var/lib/vhf/delay ] || { echo 7  >/var/lib/vhf/delay; ok "delay=7 s angelegt."; }
[ -e /var/lib/vhf/hpvol ] || { echo 60 >/var/lib/vhf/hpvol; ok "hpvol=60 angelegt."; }
[ -e /var/lib/vhf/delay ] && [ -e /var/lib/vhf/hpvol ] && info "Vorhandene Werte bleiben."

# --- Dienste -----------------------------------------------------------------
step "systemd-Dienste"
install -m644 "$SRC"/systemd/*.service "$SRC"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
ok "vhf-shipods(.timer), vhf-podwatch installiert."
if [ "$NO_ENABLE" -eq 0 ]; then
  systemctl enable --now vhf-shipods.timer vhf-podwatch
  ok "Dienste aktiviert und gestartet."
else info "Dienste installiert, aber nicht gestartet (--no-enable)."; fi

step "Wichtig: Geraete-IDs anpassen"
warn "OwnTone-Ausgangs-IDs deiner HomePods eintragen:"
info "  IDs anzeigen:  curl -s http://localhost:3689/api/outputs | python3 -m json.tool"
info "  Anpassen in:   /usr/local/bin/vhf-playout.sh  (BB/SB)"
info "                 /usr/local/bin/vhf-shipods.sh  /usr/local/bin/vhf-podwatch.sh"
