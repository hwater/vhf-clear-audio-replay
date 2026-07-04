#!/usr/bin/env bash
# Add-on Bedienpanel (:8090) – Installation
# Installiert Panel, Live-Monitor, Pegelmessung, Messe-Helfer + Dienste.
#
#   sudo ./addons/control-panel/install.sh [--no-enable] [--force]
#
#   --no-enable   Dienste nur installieren, nicht starten
#   --force       Warnungen ignorieren
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

SRC="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$SRC/../.." && pwd)"
[ -d "$SRC/bin" ] && [ -d "$SRC/systemd" ] || die "bin/ oder systemd/ fehlt neben install.sh."

# --- Kompatibilitaet (vor sudo, damit Nicht-Linux sofort abbricht) -----------
step "Bedienpanel (:8090) – Kompatibilitaetscheck"
[ "$(uname -s)" = "Linux" ] || die "Nur unter Linux (Raspberry Pi). Erkannt: $(uname -s)."
command -v systemctl >/dev/null 2>&1 || die "systemd (systemctl) nicht gefunden."
ok "Linux + systemd"
[ -x /usr/local/bin/vhf-web.py ] || { warn "Nachhoer-Kern (vhf-web.py) nicht gefunden – bitte zuerst das Haupt-install.sh."; [ "$FORCE" -eq 1 ] || die "Abbruch. Mit --force trotzdem installieren."; }

# --- Root --------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "Bitte als root bzw. mit sudo ausfuehren."
  exec sudo -E bash "$0" "$@"
fi

# --- Programme ---------------------------------------------------------------
step "Programme nach /usr/local/bin"
install -m755 "$SRC/bin/vhf-control.py" "$SRC/bin/vhf-monitor.sh" \
              "$SRC/bin/vhf-level.py"   "$SRC/bin/vhf-messe-play.sh" /usr/local/bin/
ok "vhf-control.py, vhf-monitor.sh, vhf-level.py, vhf-messe-play.sh"

# --- Konfiguration -----------------------------------------------------------
step "Konfiguration /etc/vhf/vhf.conf"
install -d -m755 /etc/vhf
if [ -e /etc/vhf/vhf.conf ]; then info "Vorhandene /etc/vhf/vhf.conf bleibt unveraendert."
elif [ -e "$ROOT/etc/vhf.conf.example" ]; then
  install -m644 "$ROOT/etc/vhf.conf.example" /etc/vhf/vhf.conf; ok "Vorlage kopiert."
else warn "etc/vhf.conf.example nicht gefunden – Konfig manuell anlegen."; fi

# --- Dienste -----------------------------------------------------------------
step "systemd-Dienste"
install -m644 "$SRC"/systemd/*.service /etc/systemd/system/
systemctl daemon-reload
ok "vhf-control, vhf-level, vhf-monitor installiert."
if [ "$NO_ENABLE" -eq 0 ]; then
  systemctl enable --now vhf-control vhf-level vhf-monitor
  ok "Dienste aktiviert und gestartet."
else info "Dienste installiert, aber nicht gestartet (--no-enable)."; fi

step "Fertig"
info "Panel: http://$(hostname).local:8090/"
