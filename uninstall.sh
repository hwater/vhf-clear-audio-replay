#!/usr/bin/env bash
# VHF clear Audio replay – Deinstallation
# Stoppt/entfernt Dienste, Programme und Konfig. Aufnahmen bleiben erhalten,
# ausser mit --purge. Vorab: kurzer Kompatibilitaetscheck (Linux/systemd).
#
#   sudo ./uninstall.sh [--purge] [--force]
#
#   --purge     zusaetzlich Aufnahmen (/srv/music/VHF-Aufnahmen) und /etc/vhf loeschen
#   --force     nicht nachfragen
#   -h, --help  diese Hilfe
set -euo pipefail

# ---- Optionen ---------------------------------------------------------------
PURGE=0; FORCE=0
for a in "$@"; do
  case "$a" in
    --purge) PURGE=1 ;;
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $a  (--help)"; exit 2 ;;
  esac
done

# ---- Ausgabe-Helfer ---------------------------------------------------------
if [ -t 1 ]; then C_G=$'\033[32m'; C_C=$'\033[36m'; C_Y=$'\033[33m'; C_R=$'\033[31m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else C_G=; C_C=; C_Y=; C_R=; C_B=; C_0=; fi
ok(){   printf '  %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
info(){ printf '  %sℹ%s %s\n' "$C_C" "$C_0" "$*"; }
warn(){ printf '  %s!%s %s\n' "$C_Y" "$C_0" "$*"; }
err(){  printf '  %s✗%s %s\n' "$C_R" "$C_0" "$*" >&2; }
step(){ printf '\n%s%s%s\n' "$C_B" "$*" "$C_0"; }
die(){  err "$*"; exit 1; }

# ---- Root sicherstellen -----------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then exec sudo -E bash "$0" "$@"; fi
  die "Bitte als root bzw. mit sudo ausfuehren."
fi

# ---- Kompatibilitaetscheck (schlank) ----------------------------------------
step "Kompatibilitaetscheck"
[ "$(uname -s)" = "Linux" ] || die "Nur unter Linux ausfuehren. Erkannt: $(uname -s)."
command -v systemctl >/dev/null 2>&1 || die "systemd (systemctl) nicht gefunden."
ok "Linux + systemd"

# ---- Bestaetigung -----------------------------------------------------------
if [ "$FORCE" -eq 0 ]; then
  printf '\nEntfernt Dienste, Programme und Konfiguration von VHF clear Audio replay.\n'
  if [ "$PURGE" -eq 1 ]; then printf '%sAchtung: --purge loescht auch alle Aufnahmen und /etc/vhf.%s\n' "$C_R" "$C_0"; fi
  printf 'Fortfahren? [j/N] '
  read -r ans || ans=""
  case "$ans" in j|J|y|Y) ;; *) echo "Abgebrochen."; exit 0 ;; esac
fi

# ---- 1) Dienste stoppen/deaktivieren ---------------------------------------
step "1/4  Dienste stoppen"
systemctl disable --now vhf-recorder vhf-web vhf-cleanup.timer 2>/dev/null || true
systemctl stop vhf-cleanup.service 2>/dev/null || true
ok "vhf-recorder, vhf-web, vhf-cleanup gestoppt/deaktiviert."

# ---- 2) Unit-Dateien --------------------------------------------------------
step "2/4  Unit-Dateien entfernen"
rm -f /etc/systemd/system/vhf-recorder.service \
      /etc/systemd/system/vhf-web.service \
      /etc/systemd/system/vhf-cleanup.service \
      /etc/systemd/system/vhf-cleanup.timer
systemctl daemon-reload
systemctl reset-failed vhf-recorder vhf-web vhf-cleanup 2>/dev/null || true
ok "systemd-Units entfernt, daemon-reload."

# ---- 3) Programme -----------------------------------------------------------
step "3/4  Programme entfernen"
rm -f /usr/local/bin/vhf-recorder.sh /usr/local/bin/vhf-classify.py /usr/local/bin/vhf-web.py
ok "vhf-recorder.sh, vhf-classify.py, vhf-web.py entfernt."

# ---- 4) ALSA / udev / modprobe ---------------------------------------------
step "4/4  ALSA/udev/modprobe zuruecksetzen"
rm -f /etc/udev/rules.d/85-vhf-audio.rules /etc/modprobe.d/alsa-vhf-index.conf
udevadm control --reload-rules 2>/dev/null || true
if [ -e /etc/asound.conf.pre-vhf ]; then
  mv -f /etc/asound.conf.pre-vhf /etc/asound.conf
  info "Vorherige /etc/asound.conf aus Sicherung wiederhergestellt."
else
  rm -f /etc/asound.conf
  info "/etc/asound.conf entfernt."
fi
ok "udev-Regel, modprobe-Index entfernt."

# ---- Optional: Aufnahmen & Konfig -------------------------------------------
if [ "$PURGE" -eq 1 ]; then
  step "--purge  Aufnahmen & Konfiguration loeschen"
  rm -rf /srv/music/VHF-Aufnahmen /etc/vhf
  rm -rf /run/vhf
  ok "/srv/music/VHF-Aufnahmen, /etc/vhf und /run/vhf geloescht."
else
  step "Behalten"
  info "Aufnahmen bleiben unter /srv/music/VHF-Aufnahmen."
  info "Konfiguration bleibt unter /etc/vhf/. (--purge entfernt beides)"
fi

step "Deinstallation abgeschlossen"
