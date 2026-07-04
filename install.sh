#!/usr/bin/env bash
# VHF clear Audio replay – Installation
# Richtet Pakete, ALSA/udev, Programme, Ablage und systemd-Dienste ein.
# Vorab: Kompatibilitaetscheck (Raspberry Pi / Linux / systemd).
#
#   sudo ./install.sh [--check] [--skip-deps] [--no-enable] [--force]
#
#   --check       nur Kompatibilitaetscheck, nichts installieren
#   --skip-deps   apt-Paketinstallation ueberspringen
#   --no-enable   Dienste nur installieren, nicht starten/aktivieren
#   --force       Kompatibilitaetswarnungen ignorieren (trotzdem installieren)
#   -h, --help    diese Hilfe
set -euo pipefail

# ---- Optionen ---------------------------------------------------------------
CHECK_ONLY=0; SKIP_DEPS=0; NO_ENABLE=0; FORCE=0
for a in "$@"; do
  case "$a" in
    --check)     CHECK_ONLY=1 ;;
    --skip-deps) SKIP_DEPS=1 ;;
    --no-enable) NO_ENABLE=1 ;;
    --force)     FORCE=1 ;;
    -h|--help)   sed -n '2,12p' "$0"; exit 0 ;;
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

# ---- Repo-Verzeichnis (unabhaengig vom cwd) ---------------------------------
SRC="$(cd "$(dirname "$0")" && pwd)"
for d in bin etc systemd; do
  [ -d "$SRC/$d" ] || die "Ordner '$d' fehlt neben install.sh – bitte im Repo-Wurzelverzeichnis ausfuehren."
done

# ---- Root sicherstellen (ausser reiner --check-Lauf) ------------------------
if [ "$CHECK_ONLY" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then exec sudo -E bash "$0" "$@"; fi
  die "Bitte als root bzw. mit sudo ausfuehren."
fi

# ---- Kompatibilitaetscheck --------------------------------------------------
step "Kompatibilitaetscheck"
GATE=0   # zaehlt Warnungen, die --force erfordern

# Betriebssystem
[ "$(uname -s)" = "Linux" ] || die "Nur unter Linux (Raspberry Pi OS). Erkannt: $(uname -s)."
ok "Linux ($(uname -m))"

# systemd
command -v systemctl >/dev/null 2>&1 || die "systemd (systemctl) nicht gefunden – wird zwingend benoetigt."
ok "systemd vorhanden"

# Raspberry Pi?
MODEL=""
[ -r /proc/device-tree/model ] && MODEL="$(tr -d '\0' </proc/device-tree/model)"
if [ -z "$MODEL" ] && [ -r /proc/cpuinfo ]; then
  MODEL="$(grep -m1 -E 'Model|Raspberry' /proc/cpuinfo | cut -d: -f2- | sed 's/^ *//')"
fi
if printf '%s' "$MODEL" | grep -qi 'raspberry pi'; then
  ok "Raspberry Pi erkannt: $MODEL"
else
  warn "Kein Raspberry Pi erkannt${MODEL:+ ($MODEL)} – getestet ist Raspberry Pi OS."
  GATE=$((GATE+1))
fi

# OS-Version (nur Info/Warnung)
if [ -r /etc/os-release ]; then
  . /etc/os-release
  case "${ID:-}${ID_LIKE:-}" in
    *debian*|*raspbian*) ok "OS: ${PRETTY_NAME:-debian-basiert}${VERSION_CODENAME:+ ($VERSION_CODENAME)}"
      [ "${VERSION_CODENAME:-}" = "trixie" ] || info "Getestet auf 'trixie' – Abweichung ist meist unkritisch." ;;
    *) warn "Kein Debian/Raspbian erkannt (${PRETTY_NAME:-unbekannt}) – ungetestet."; GATE=$((GATE+1)) ;;
  esac
else
  warn "/etc/os-release fehlt – OS unbekannt."; GATE=$((GATE+1))
fi

# Paketmanager (nur wenn Deps installiert werden sollen)
if [ "$SKIP_DEPS" -eq 0 ] && ! command -v apt-get >/dev/null 2>&1; then
  die "apt-get nicht gefunden. Pakete manuell installieren und mit --skip-deps starten."
fi

# USB-Audio-Adapter (informativ, blockiert nicht – kann spaeter gesteckt werden)
if command -v lsusb >/dev/null 2>&1; then
  if lsusb | grep -qi '0d8c:0014'; then ok "VHF-USB-Audio-Adapter (C-Media 0d8c:0014) gefunden."
  else warn "C-Media 0d8c:0014 nicht gesteckt – anderer Adapter? etc/85-vhf-audio.rules + asound.conf ggf. anpassen."; fi
else
  info "lsusb nicht verfuegbar – Adapter-Pruefung uebersprungen."
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ "$GATE" -gt 0 ]; then warn "$GATE Warnung(en) – Installation nur mit --force moeglich."; exit 1; fi
  ok "System ist kompatibel."; exit 0
fi
if [ "$GATE" -gt 0 ] && [ "$FORCE" -eq 0 ]; then
  die "$GATE Kompatibilitaetswarnung(en). Mit --force trotzdem installieren."
fi
[ "$GATE" -gt 0 ] && warn "Fortsetzung trotz Warnungen (--force)."

# ---- 1) Pakete --------------------------------------------------------------
if [ "$SKIP_DEPS" -eq 0 ]; then
  step "1/6  Pakete installieren"
  apt-get update
  apt-get install -y sox ffmpeg alsa-utils python3-numpy curl
  ok "sox, ffmpeg, alsa-utils, python3-numpy, curl"
else
  step "1/6  Pakete – uebersprungen (--skip-deps)"
fi

# ---- 2) ALSA / udev / modprobe ---------------------------------------------
step "2/6  ALSA-Capture, udev, modprobe"
if [ -e /etc/asound.conf ] && [ ! -e /etc/asound.conf.pre-vhf ] \
   && ! cmp -s "$SRC/etc/asound.conf" /etc/asound.conf; then
  cp -a /etc/asound.conf /etc/asound.conf.pre-vhf
  info "Vorhandene /etc/asound.conf gesichert nach /etc/asound.conf.pre-vhf"
fi
install -m644 "$SRC/etc/asound.conf"          /etc/asound.conf
install -m644 "$SRC/etc/85-vhf-audio.rules"   /etc/udev/rules.d/85-vhf-audio.rules
install -m644 "$SRC/etc/alsa-vhf-index.conf"  /etc/modprobe.d/alsa-vhf-index.conf
ok "asound.conf, udev-Regel, modprobe-Index installiert"

# ---- 3) Programme -----------------------------------------------------------
step "3/6  Programme nach /usr/local/bin"
install -m755 "$SRC/bin/vhf-recorder.sh" "$SRC/bin/vhf-classify.py" "$SRC/bin/vhf-web.py" /usr/local/bin/
ok "vhf-recorder.sh, vhf-classify.py, vhf-web.py"

# ---- 4) Konfiguration -------------------------------------------------------
step "4/6  Konfiguration /etc/vhf/vhf.conf"
install -d -m755 /etc/vhf
if [ -e /etc/vhf/vhf.conf ]; then
  info "Vorhandene /etc/vhf/vhf.conf bleibt unveraendert."
else
  install -m644 "$SRC/etc/vhf.conf.example" /etc/vhf/vhf.conf
  ok "Vorlage nach /etc/vhf/vhf.conf kopiert (shipname=auto)."
fi

# ---- 5) Ablage & Rechte -----------------------------------------------------
step "5/6  Ablage /srv/music/VHF-Aufnahmen"
install -d /srv/music/VHF-Aufnahmen
if getent group audio >/dev/null 2>&1; then
  chgrp -R audio /srv/music/VHF-Aufnahmen
  chmod -R g+rws /srv/music/VHF-Aufnahmen
  ok "Gruppe 'audio', group-writable + setgid gesetzt."
else
  warn "Gruppe 'audio' fehlt – Web-Dienst laeuft evtl. nicht ohne root. chgrp uebersprungen."
fi

# ---- 6) Dienste -------------------------------------------------------------
step "6/6  systemd-Dienste"
install -m644 "$SRC"/systemd/*.service "$SRC"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
udevadm control --reload-rules 2>/dev/null || true
ok "Units installiert, daemon-reload, udev-Regeln neu geladen."
if [ "$NO_ENABLE" -eq 0 ]; then
  systemctl enable --now vhf-recorder vhf-web vhf-cleanup.timer
  ok "vhf-recorder, vhf-web, vhf-cleanup.timer aktiviert und gestartet."
else
  info "Dienste installiert, aber nicht gestartet (--no-enable)."
fi

# ---- Abschluss --------------------------------------------------------------
step "Fertig"
info "Weboberflaeche:  http://$(hostname).local:8088/"
info "Status:          systemctl status vhf-recorder vhf-web"
warn "USB-Karten-Index (hw:3) und udev-ID greifen erst nach einem Reboot zuverlaessig."
