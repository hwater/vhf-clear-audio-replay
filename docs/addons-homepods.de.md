# Add-on: HomePod- / AirPlay-2-Ausgabe

*🇩🇪 Deutsch · [🇬🇧 English](addons-homepods.md)*

> **Optional.** Der Nachhör-Kern (Aufnahme + Web-Replay) läuft ohne dieses Add-on.
> Hier kommt hinzu: erkannter *echter* Funk wird nach einer einstellbaren Verzögerung
> kurz auf AirPlay-2-Lautsprecher (z. B. HomePods) „übernommen" und danach wieder
> freigegeben – so bleiben die Lautsprecher sonst für iPhone-Musik frei.

Dateien: [`addons/homepods/`](../addons/homepods/)

```
addons/homepods/
├── bin/
│   ├── vhf-playout.sh    echten Funk-Clip kurz auf die AirPlay-Ausgänge spielen
│   ├── vhf-shipods.sh    Ausgänge ausgewählt halten + Zustand melden
│   └── vhf-podwatch.sh   Netz-Erreichbarkeit überwachen, OwnTone selbstheilen
└── systemd/
    ├── vhf-shipods.service / .timer
    └── vhf-podwatch.service
```

## Voraussetzung: pyatv (nicht OwnTone!)

Die Funk-Übernahme streamt über **[pyatv](https://pyatv.dev)** (RAOP/AirPlay) **direkt**
auf die HomePods. **Bewusst nicht OwnTone:** OwnTone (v29.x) stürzt beim AirPlay-Streaming
zu genau diesen HomePods reproduzierbar ab bzw. hängt (bekannte upstream-Bugs; ein in
HomeKit aufgelöstes Stereopaar wird als Einzelgeräte mit AirPlay 1 behandelt). pyatv
streamt stabil, ganz ohne OwnTone.

```bash
# pyatv in ein venv installieren
sudo python3 -m venv /opt/pyatv-venv
sudo /opt/pyatv-venv/bin/pip install pyatv
```

`vhf-playout.sh` spielt **Dual-Mono** (beide Pods parallel denselben Clip) — für
Funksprache völlig ausreichend. OwnTone darf weiterlaufen (Messe-Ausgang / Pod-Erkennung),
wird aber für die HomePod-Wiedergabe **nicht** mehr gebraucht.

## Geräte-IDs anpassen (Pflicht!)

`vhf-playout.sh` enthält feste **pyatv/AirPlay-Identifier** der HomePods:

```bash
BB=FE:A2:7C:85:A9:5C     # ShiPod BB
SB=A2:AE:9B:32:35:0A     # ShiPod SB
```

Deine findest du mit:

```bash
/opt/pyatv-venv/bin/atvremote scan
```

→ pro Gerät die MAC-artige Zeile unter **„Identifiers"** nehmen. Die HomePods brauchen für
RAOP i.d.R. **keine Kopplung** (`Pairing: NotNeeded`), sofern in der Home-App
„Lautsprecher- & TV-Zugriff" auf „Jeder im selben Netzwerk" steht.

## Funktionsweise

- **`vhf-playout.sh <mp3> [now]`** – wählt die AirPlay-Ausgänge, setzt die Lautstärke
  (`/var/lib/vhf/hpvol`), spielt genau einen Clip über OwnTone und gibt die Ausgänge
  danach wieder frei. Ohne `now`: wartet die Verzögerung aus `/var/lib/vhf/delay`
  (Default 7 s) ab und respektiert das Mute-Flag `/run/vhf/mute`.
- **`vhf-shipods.*`** – ein Timer hält die AirPlay-2-Ausgänge *ausgewählt* (AirPlay-2
  verliert die Auswahl bei OwnTone-Neustart) und meldet den Zustand nach
  `/run/vhf/shipods.state`.
- **`vhf-podwatch.*`** – prüft die WLAN-Erreichbarkeit der Pods (mDNS + AirPlay-Port
  7000) und startet OwnTone *einmalig* neu (Cooldown 5 min), wenn beide wieder im Netz
  sind, OwnTone sie aber verloren hat.

## Installation

```bash
sudo install -m755 addons/homepods/bin/*.sh /usr/local/bin/
sudo install -m644 addons/homepods/systemd/* /etc/systemd/system/
sudo mkdir -p /var/lib/vhf
echo 7  | sudo tee /var/lib/vhf/delay     # Verzögerung Sekunden
echo 60 | sudo tee /var/lib/vhf/hpvol     # HomePod-Lautstärke 0..100
sudo systemctl daemon-reload
sudo systemctl enable --now vhf-shipods.timer vhf-podwatch
```

Sobald `vhf-playout.sh` als `/usr/local/bin/vhf-playout.sh` **ausführbar** vorhanden
ist, ruft der `vhf-recorder` es bei erkannter Sprache automatisch auf – keine Änderung
am Recorder nötig.

## Deaktivieren

```bash
sudo systemctl disable --now vhf-shipods.timer vhf-podwatch
sudo rm /usr/local/bin/vhf-playout.sh    # Recorder überspringt die Übernahme dann wieder
```

## Hinweis / Umfang

Dieses Add-on deckt die **Nachhör-Übernahme** (einzelner Clip → HomePods) ab. Das
größere Live-/AirPlay-/Ducking-System (Live-Monitor, `vhf-mixer`, `shairport-sync`,
Messe-Lautsprecher) aus dem ursprünglichen `wilhelmina-audio`-Setup ist hier bewusst
**nicht** enthalten – es kann später als weiteres Add-on ergänzt werden.
