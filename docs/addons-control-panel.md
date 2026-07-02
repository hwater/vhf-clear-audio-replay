# Add-on: Bedienpanel (:8090)

*🇩🇪 Deutsch*

> **Optional.** Ein maritimes Touch-Bedienpanel für Handy/Tablet, das die
> VHF-Funktionen an einem Ort bündelt: Funk-Pegelanzeige, Messe-Live-Monitor,
> Aufnahmen-Liste (bindet die Nachhör-Liste :8088 als iframe ein) und – falls
> HomePods an Bord sind – die HomePod-Übernahme.
>
> **Ohne HomePods** zeigt und steuert das Panel automatisch **nur den
> Messe-Lautsprecher** (siehe `homepods`-Einstellung unten).

Dateien: [`addons/control-panel/`](../addons/control-panel/)

```
addons/control-panel/
├── bin/
│   ├── vhf-control.py    das Panel (Port 8090)
│   ├── vhf-monitor.sh    latenzarmer Live-Monitor: VHF → Messe-Lautsprecher (~100 ms)
│   └── vhf-level.py      Pegelmessung → /run/vhf/level (Quelle fürs VU-Meter)
└── systemd/
    ├── vhf-control.service
    ├── vhf-monitor.service
    └── vhf-level.service
```

## Konfiguration: Schiffsname & HomePod-Modus

Das Panel (und die Nachhör-Liste :8088) lesen `/etc/vhf/vhf.conf`
(siehe [`etc/vhf.conf.example`](../etc/vhf.conf.example)) — **ohne Neustart**:

```ini
shipname = Wilhelmina      # Titelzeile beider Oberflächen
homepods = auto            # auto | on | off
```

- `homepods = auto` — HomePod-Übernahme erscheint, sobald ShiPod-Ausgänge in
  OwnTone erkannt werden (Standard).
- `homepods = on` — immer anzeigen.
- `homepods = off` — nie anzeigen: das Panel nutzt **nur den Messe-Lautsprecher**;
  Titel-Unterzeile wird zu „VHF-MONITOR · MESSE".

```bash
sudo mkdir -p /etc/vhf
sudo cp etc/vhf.conf.example /etc/vhf/vhf.conf
sudo nano /etc/vhf/vhf.conf        # shipname/homepods anpassen
```

## Was das Panel nutzt

| Funktion | Abhängigkeit |
|---|---|
| Funk-Pegel (VU) | `vhf-level` schreibt `/run/vhf/level` |
| Messe-Live-Monitor (An/Aus + Lautstärke) | `vhf-monitor` + ALSA-Mixer `Speaker` (Karte 3) |
| Aufnahmen-Liste | Nachhör-Kern `vhf-web` (:8088, als iframe) |
| HomePod-Übernahme / „Funk wiederholen" | **HomePod-Add-on** (OwnTone, `vhf-playout.sh`, `vhf-shipods`) — siehe [addons-homepods.md](addons-homepods.md) |

Ohne das HomePod-Add-on bleibt das Panel voll nutzbar (Messe-Betrieb); die
HomePod-Karte wird bei `homepods = off` bzw. `auto` (ohne erkannte Pods) ausgeblendet.

## Installation

```bash
# Panel + Messe-Helfer
sudo install -m755 addons/control-panel/bin/vhf-control.py \
                   addons/control-panel/bin/vhf-monitor.sh \
                   addons/control-panel/bin/vhf-level.py   /usr/local/bin/
sudo install -m644 addons/control-panel/systemd/* /etc/systemd/system/

# Konfiguration
sudo mkdir -p /etc/vhf && sudo cp etc/vhf.conf.example /etc/vhf/vhf.conf

sudo systemctl daemon-reload
sudo systemctl enable --now vhf-control vhf-level
# Messe-Live-Monitor nach Bedarf (kann auch im Panel getoggelt werden):
sudo systemctl enable --now vhf-monitor
```

Panel öffnen: **http://<pi>.local:8090/**

## Deaktivieren

```bash
sudo systemctl disable --now vhf-control vhf-level vhf-monitor
sudo rm /etc/systemd/system/vhf-{control,level,monitor}.*
sudo rm /usr/local/bin/vhf-{control.py,level.py,monitor.sh}
```

## Hinweis / Umfang

Der latenzarme Messe-Monitor (`vhf-monitor`) und die Pegelmessung (`vhf-level`)
lesen die gemeinsame ALSA-Capture-Quelle `vhf` (dsnoop) des Nachhör-Kerns. Der
Messe-**Ausgang** nutzt die C-Media-Karte (Karte 3). Das größere
AirPlay-/Ducking-System (`vhf-mixer`, `shairport-sync`) ist hier **nicht**
enthalten.
